import logging
import os
import socket
import struct
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from axone.axone_struct import standard_data_decoding, standard_data_encoding


def send_msg(sock, msg) -> None:
    try:
        # Prefix each message with a 4-byte length (network byte order)
        msg = struct.pack('>I', len(msg)) + msg
        sock.sendall(msg)
    except socket.timeout:
        logging.error("Socket operation timed out")
    except OSError as e:
        logging.error(f"Socket error: {e}")


def recvall(sock, n) -> None | bytearray:
    data = bytearray()
    try:
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
    except socket.timeout:
        logging.error("Socket read operation timed out")
    except OSError as e:
        logging.error(f"Socket error during recv: {e}")
    return data


def recv_msg(sock) -> None | bytearray:
    # Read message length and unpack it into an integer
    raw_msglen = recvall(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    # Read the message data
    return recvall(sock, msglen)


class ServiceServer:
    def __init__(
        self,
        services,  # dict[callable | str, dict[str, str | list[str]]],
        node_uuid: str,
    ) -> None:
        self._server_port = None
        self.sock = None
        self.node_uuid = node_uuid

        # format the services dictionary
        self._services_map = {}
        for service, arguments in services.items():
            if callable(service):
                self._services_map[service.__name__] = {"func": service, "arguments": arguments}
            elif isinstance(service, str):
                # ? What is the point of this?
                self._services_map[service] = {"func": services[service], "arguments": arguments}
            else:
                raise TypeError(f"service {service} is not a string or a function.")

        # print(self._services_map)

    @property
    def services_keys(self) -> list[str]:
        return list(self._services_map.keys())

    @property
    def server_port(self) -> int:
        if sys.platform != 'win32':
            # Use the node_uuid as the server port when using UNIX sockets
            self._server_port = self.node_uuid
        else:
            if self._server_port is None:
                self._server_port = self.find_free_port()
        return self._server_port

    def find_free_port(self) -> int:
        with socket.socket() as s:
            s.bind(('', 0))  # Bind to a free port provided by the host OS.
            return int(s.getsockname()[1])  # Return the port number assigned.

    def find_and_call_service(self, data: bytearray) -> tuple[bool, None | Any]:
        # Determine the function to call
        # decoded_data = data.decode("utf-8")

        # if "(" not in decoded_data:
        #     logging.error("Invalid data format")
        #     return False, None

        # service_name, arguments = decoded_data.split("(", 1)
        # arguments = arguments[:-1].split(",")

        # decoded_data = data  # .decode("utf-8")
        decoded_data = standard_data_decoding(data)
        service_name = decoded_data.pop("func", None)
        if service_name is None:
            logging.error("Invalid data format. No service name provided.")
            return False, None

        # Everything but the function name
        arguments = decoded_data

        logging.info(f"Calling service '{service_name}' with arguments: {arguments}")

        if not arguments:
            arguments = []

        if service_name not in self._services_map.keys():
            logging.error(f"Service {service_name} not found in {self._services_map.keys()}")
            return False, None

        func = self._services_map[service_name]["func"]
        logging.debug(f"Function to call: {func}")

        if len(self._services_map[service_name]["arguments"]) != len(arguments):
            logging.error(
                f"Incompatible number of arguments for service {service_name}, "
                + f"expected {len(self._services_map[service_name]['arguments'])},"
                + f" got {len(arguments)}"
            )
            return False, None

        # Select arguments based on the function signature
        arguments = [arguments[k] for k in self._services_map[service_name]["arguments"]]

        # Call the function
        try:
            logging.debug(f"Calling service {service_name} with arguments {arguments}")
            ret = func(*arguments)
            logging.info(f"Service {service_name} returned {ret}")
            return True, ret
        except Exception as e:
            logging.error(
                f"Error occured when calling service {service_name}:\n{e}",
                exc_info=True,
            )
            return False, None

    def start(self) -> None:
        if sys.platform != 'win32':
            family = socket.AF_UNIX
            server_address = f'/tmp/{self.server_port}_socket'

            # Make sure the socket does not already exist
            try:
                os.unlink(server_address)
            except OSError:
                if os.path.exists(server_address):
                    raise
            logging.info(f'starting up on UNIX socket {server_address}')
        else:
            family = socket.AF_INET
            server_address = ('localhost', int(self.server_port))
            logging.info('starting up on TCP socket {}:{}'.format(*server_address))

        # Create a UDS socket
        self.sock = socket.socket(family, socket.SOCK_STREAM)

        # Bind the socket to the address
        self.sock.bind(server_address)

        # Set a timeout on the socket
        self.sock.settimeout(1.0)

        # Initialize a Thread to listen to the memory events
        # Initialize a Thread to cleanup the memory periodically
        self._server_should_run = True
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._executor.submit(self._server)

    def stop(self) -> None:
        self._server_should_run = False

    def _server(self) -> None:
        """
        Periodic server functions
        """
        # Listen for incoming connections
        self.sock.listen(1)

        while self._server_should_run:
            try:
                connection, client_address = self.sock.accept()
                with connection:  # Ensures the socket is closed after block execution
                    logging.info(f'Connection from {client_address}')
                    while True:
                        data = recv_msg(connection)
                        if data:
                            logging.info(f'Received {data!r}')
                            ret, out = self.find_and_call_service(data)
                            logging.info('Sending data back to the client')
                            send_msg(connection, standard_data_encoding(ret=ret, out=out))
                        else:
                            logging.info(f'No more data from {client_address}')
                            break
            except socket.timeout:
                continue  # Handle specific exceptions as needed
            except Exception as e:
                logging.error(f"Server error: {e}", exc_info=True)
                break  # Or handle as appropriate
        logging.info("Node server stopped")


if __name__ == "__main__":
    from axone.custom_logger import setup_logger

    setup_logger(debug=True)

    def print_message(message: str) -> None:
        print(message)

    def print_secondary(message: str) -> None:
        print(message)

    def simple_addition(a, b) -> None:
        return a + b

    logging.basicConfig(level=logging.INFO)
    server = ServiceServer(
        services={
            print_message: {"message": "str"},
            print_secondary: ["message"],
            simple_addition: ["a", "b"],
        },
        node_uuid="uds",
    )
    server.start()
    input("Press Enter to stop the server")
    server.stop()
    logging.info("Server stopped")
