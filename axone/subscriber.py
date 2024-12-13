import logging
import socket
import struct
import threading
import time
from multiprocessing.shared_memory import SharedMemory
from typing import Any, Callable, List, Optional

from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

from axone.axone_struct import AxoneStruct
from axone.utils import generate_uuid


class Subscription:
    def __init__(
        self,
        topic_name: str = "",
        rate: float = 1.0,
        method: str = "socket",
        retry_interval: float = 5.0,  # Retry interval in seconds
        max_retries: int = 10,  # Maximum number of retries
        multicast_group: str = "224.1.1.1",  # Multicast group address
        timeout: float = 2.0,  # Timeout for socket operations
    ) -> None:
        self._name: str = topic_name
        self._request_rate: float = rate
        self._topic_rate: float = None
        self._timestamp: float = 0
        self._last_timestamp: float = 0

        self._topic = AxoneStruct()
        self._callbacks = []

        self._uuid = generate_uuid(topic_name)
        self._method = method
        self._retry_interval = retry_interval
        self._socket = None
        self._max_retries = max_retries
        self._multicast_group = multicast_group
        self._multicast_port = 0
        self._multicast_interface_ip = ""
        self._joined_multicast = False  # Flag to indicate if multicast group is joined
        self._timeout = timeout
        self._stop_event = threading.Event()

        self._zeroconf = Zeroconf()
        self._service_browser = ServiceBrowser(self._zeroconf, "_axone._udp.local.", handlers=[self._on_service_state_change])

        if self._method == "shared_memory":
            self._connect_shared_memory()

    def _connect_shared_memory(self) -> None:
        """Connect to the shared memory of the topic."""
        try:
            self._memory = SharedMemory(name=self._uuid, create=False)
        except FileNotFoundError:
            logging.error(f"Shared memory {self._uuid} not found")
            self._memory = None

    def _start_listening_thread(self) -> None:
        """Start the listening thread."""
        self._stop_event.clear()
        self._listening_thread = threading.Thread(target=self._listen)
        self._listening_thread.start()

    def _listen(self) -> None:
        """Listen for incoming messages."""
        while not self._stop_event.is_set():
            try:
                self.subscribe()
            except Exception as e:
                logging.error(f"Error in subscription thread: {e}", exc_info=True)

    def _on_service_state_change(self, zeroconf, service_type, name, state_change):
        """Handle service state changes."""
        if state_change in (ServiceStateChange.Added, ServiceStateChange.Updated):
            self._handle_service_added_or_updated(zeroconf, service_type, name, state_change)
        elif state_change == ServiceStateChange.Removed:
            self._handle_service_removed(zeroconf, service_type, name)

    def _handle_service_added_or_updated(self, zeroconf, service_type, name, state_change):
        """Handle service added or updated state."""
        info = zeroconf.get_service_info(service_type, name)
        if info and info.properties.get(b'name').decode('utf-8') == self._name:
            new_multicast_group = socket.inet_ntoa(info.addresses[0])
            new_multicast_port = info.port
            new_multicast_ip_address = (
                info.properties.get(b'ip_address').decode('utf-8') if b'ip_address' in info.properties else None
            )
            # source = info.properties.get(b'source').decode('utf-8') if b'source' in info.properties else None
            # rate = float(info.properties.get(b'rate').decode('utf-8')) if b'rate' in info.properties else None

            logging.info(
                f"Service {name} at {new_multicast_ip_address}:{new_multicast_port} "
                + f"{'added' if state_change == ServiceStateChange.Added else 'updated'}"
            )
            if self._method == "socket":
                if (
                    new_multicast_group != self._multicast_group
                    or new_multicast_port != self._multicast_port
                    or self.get_local_ip_for_target(new_multicast_ip_address) != self._multicast_interface_ip
                ):
                    self._multicast_group = new_multicast_group
                    self._multicast_port = new_multicast_port
                    self._multicast_interface_ip = self.get_local_ip_for_target(new_multicast_ip_address)
                self._restart_socket()

    def get_local_ip_for_target(self, target_ip: str) -> str:
        """Get the local IP address that can communicate with the target IP."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as temp_socket:
                temp_socket.connect((target_ip, 1))
                local_ip = temp_socket.getsockname()[0]
            return local_ip
        except Exception as e:
            raise RuntimeError(f"Cannot determine local IP address for target {target_ip}: {e}")

    def _handle_service_removed(self, zeroconf, service_type, name):
        """Handle service removed state."""
        info = zeroconf.get_service_info(service_type, name)
        if info and info.properties.get(b'name').decode('utf-8') == self._name:
            logging.info(f"Service {name} removed")
            self._joined_multicast = False
            if self._socket:
                self._socket.close()
                self._socket = None

    def _restart_socket(self) -> None:
        """Restart the socket to rejoin the multicast group."""
        self._stop_event.set()
        if self._socket is not None:
            while self._listening_thread.is_alive():
                time.sleep(0.1)
        self._create_socket_with_retries()
        self._start_listening_thread()

    def _create_socket_with_retries(self) -> None:
        """Create a socket with retries."""
        retries = 0
        while retries < self._max_retries:
            try:
                self._create_socket()
                return
            except OSError as e:
                logging.warning(f"Failed to bind socket on attempt {retries + 1}/{self._max_retries}: {e}")
                retries += 1
                time.sleep(self._retry_interval)
        raise RuntimeError(f"Failed to bind socket after {self._max_retries} attempts")

    def _create_socket(self) -> None:
        """Create a socket and join the multicast group."""
        if self._multicast_port == 0:
            return
        if self._socket:
            self._socket.close()

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.settimeout(self._timeout)
        self._socket.bind(('', self._multicast_port))

        # mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        mreq = struct.pack(
            '4s4s',
            socket.inet_aton(self._multicast_group),
            socket.inet_aton(self._multicast_interface_ip) if self._multicast_interface_ip else socket.INADDR_ANY,
        )
        self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        logging.info(
            f"Listening on multicast group '{self._multicast_group}:{self._multicast_port}' "
            + f"on interface {self._multicast_interface_ip}"
        )
        self._joined_multicast = True

    @property
    def topic(self) -> str:
        """The string representation of the topic."""
        return str(self._topic)

    @property
    def name(self) -> str:
        """The topic name of the publisher."""
        return self._name

    @property
    def rate(self) -> float:
        """The rate at which the topic should be subscribed."""
        return (
            self._request_rate
            if (self._request_rate is not None and self._topic_rate is None)
            else (self._request_rate if (self._request_rate > self._topic_rate) else self._topic_rate)
        )

    @rate.setter
    def rate(self, value: float) -> None:
        """Change the request rate of the topic."""
        self._request_rate = value

    @property
    def timestamp(self) -> float:
        """The timestamp of the last update of the topic."""
        return self._timestamp

    @property
    def last_timestamp(self) -> float:
        """The timestamp of the previous update of the topic."""
        return self._last_timestamp

    @property
    def callbacks(self) -> List[Callable]:
        """The list of callbacks to call when a new message is received."""
        return self._callbacks

    def call(self, topic_struct) -> None:
        """Call all registered callbacks with the topic structure."""
        for callback in self._callbacks:
            try:
                if callable(callback):
                    callback(topic_struct)
            except Exception as e:
                logging.error(f"Error in callback {callback}: {e}")

    # @timeit_if_debug
    def subscribe(self) -> Any:
        """Get the latest message from the topic."""
        # print(f"Subscribing to {self._name}")
        self._last_timestamp = time.time()

        if self._method == "shared_memory":
            encoded = self._subscribe_shared_memory()
        elif self._method == "socket":
            encoded = self._subscribe_socket_with_retries()

        if encoded:
            logging.debug(f"Received message from {self._name}:{encoded}")
            self._topic.decode(encoded)
            self._timestamp = self._topic.timestamp_
            self._new_message = self._timestamp != self._last_timestamp
            self._last_timestamp = self._timestamp
            self._topic_rate = self._topic.rate_

            if self.callbacks:
                self.call(self._topic)

    def _subscribe_shared_memory(self) -> Optional[bytes]:
        """Subscribe to the shared memory."""
        if self._memory is None or self._memory.buf is None:
            return None
        return bytes(self._memory.buf[:])

    def _subscribe_socket_with_retries(self) -> Optional[bytes]:
        """Subscribe to the socket with retries."""
        if self._socket is None:
            return None
        retries = 0
        while retries < self._max_retries:
            try:
                return self._subscribe_socket()
            except (OSError, socket.timeout) as e:
                logging.warning(f"Socket error {self._name} on attempt {retries + 1}/{self._max_retries}: {e}")
                retries += 1
                time.sleep(self._retry_interval)
                self._create_socket_with_retries()
        logging.error(f"Failed to receive data after {self._max_retries} attempts")
        return None

    def _subscribe_socket(self) -> Optional[bytes]:
        """Subscribe to the socket."""
        if self._socket is None:
            return None
        try:
            data, _ = self._socket.recvfrom(2048)  # Adjust buffer size as needed
            return data
        except (OSError, socket.timeout) as e:
            if self._topic_rate is None or self._topic_rate < 0:
                # We are not expecting a specific rate, so just return None
                return None
            else:
                logging.error(f"Socket error {self._name}: {e}")
                raise

    def stop(self) -> None:
        """Stop the subscription."""
        self._stop_event.set()
        if self._method == "shared_memory" and self._memory is not None:
            try:
                self._memory.close()
            except FileNotFoundError:
                logging.error(f"Shared memory {self._uuid} not found")
        elif self._method == "socket" and self._socket is not None:
            self._socket.close()
        self._zeroconf.close()
        logging.debug(f"Subscription {self._name} deleted")
