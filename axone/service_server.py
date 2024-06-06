import logging
import os
import socket
import struct
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any


class ServiceServer:
    def __init__(self, services) -> None:
        self._server_port = None
        self.sock = None

        self.services = services
        # format the services dictionary
        self._services_map = {}
        _services = {}
        for service, arguments in self.services.items():
            if callable(service):
                self._services_map[service.__name__] = service
                _services[service.__name__] = self.services[service]
            elif isinstance(service, str):
                # ? What is the point of this?
                self._services_map[service] = self.services[service]
                _services[service] = self.services[service]
            else:
                raise TypeError(f"service {service} is not a string or a function.")

        print(self._services_map)

    @property
    def server_port(self) -> int:
        if self._server_port is None:
            self._server_port = self.find_free_port()
        return self._server_port

    def send_msg(self, sock, msg) -> None:
        # Prefix each message with a 4-byte length (network byte order)
        msg = struct.pack('>I', len(msg)) + msg
        sock.sendall(msg)

    def recv_msg(self, sock) -> None | bytearray:
        # Read message length and unpack it into an integer
        raw_msglen = self.recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        return self.recvall(sock, msglen)

    def recvall(self, sock, n) -> None | bytearray:
        # Helper function to recv n bytes or return None if EOF is hit
        data = bytearray()
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data

    def find_free_port(self) -> int:
        with socket.socket() as s:
            s.bind(('', 0))  # Bind to a free port provided by the host OS.
            return int(s.getsockname()[1])  # Return the port number assigned.

    def find_and_call_service(self, data: bytearray) -> tuple[bool, None | Any]:
        print("Here?")
        # Determine the function to call
        decoded_data = data.decode("utf-8")
        print(decoded_data)

        if "(" not in decoded_data:
            logging.error("Invalid data format")
            return False, None

        service_name, arguments = decoded_data.split("(", 1)
        print(service_name, arguments)
        arguments = arguments[:-1].split(", ")
        print(service_name, arguments)

        logging.warning(f"Service name: {service_name}, arguments: {arguments}")

        if not arguments:
            arguments = []

        if service_name not in self.services:
            logging.error(f"Service {service_name} not found")
            return False, None

        if service_name in self.services:
            func = list(self.services[service_name].keys())[0]

            if len(self.services[service_name]) != len(arguments):
                logging.error(
                    f"Incompatible number of arguments for service {service_name}, "
                    + f"expected {len(self.services[service_name])},"
                    + f" got {len(arguments)}"
                )
                return False, None

            # Call the function
            try:
                ret = func(*arguments)
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
            server_address = '/tmp/uds_socket'

            # Make sure the socket does not already exist
            try:
                os.unlink(server_address)
            except OSError:
                if os.path.exists(server_address):
                    raise
            logging.info(f'starting up on {server_address}')
        else:
            family = socket.AF_INET
            server_address = ('localhost', int(self.server_port))
            logging.info('starting up on {}:{}'.format(*server_address))

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
                try:
                    logging.info(f'connection from {client_address}')

                    # Receive the data in small chunks and retransmit it
                    while True:
                        data = self.recv_msg(connection)
                        if data:
                            logging.info(f'received {data!r}')

                            # Process the data
                            ret, out = self.find_and_call_service(data)

                            if ret:
                                logging.info('sending data back to the client')
                                data = out.encode("utf-8")
                                data = struct.pack('>I', ret) + data  # Add the return status on top of the data
                            else:
                                data = struct.pack('>I', ret)

                            self.send_msg(connection, data)
                        else:
                            logging.info(f'no more data from {client_address}')
                            break

                finally:
                    # Clean up the connection
                    connection.close()
            except TimeoutError:
                pass
            except Exception as e:
                logging.error(
                    f"Error occured when listening for node {self.node_id}:{self.name}:\n{e}",
                    exc_info=True,
                )
                break
        logging.info("Node server stopped")


if __name__ == "__main__":

    def print_message(message: str) -> None:
        print(message)

    def print_secondary(message: str) -> None:
        print(message)

    logging.basicConfig(level=logging.INFO)
    server = ServiceServer(
        services={
            print_message: {"message": "str"},
            print_secondary: ["message"],
        }
    )
    server.start()
    input("Press Enter to stop the server")
    server.stop()
    logging.info("Server stopped")
