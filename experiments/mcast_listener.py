import logging
import socket
import struct


def udp_multicast_listener(multicast_group: str, port: int, interface_ip: str = '0.0.0.0'):
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Set socket options to allow multiple sockets to use the same address and port
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind the socket to the port
    sock.bind((interface_ip, port))

    # Tell the kernel that we want to join the multicast group on the specified interface
    group = socket.inet_aton(multicast_group)
    mreq = struct.pack('4s4s', group, socket.inet_aton(interface_ip))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    logging.info(f"Listening on multicast group {multicast_group}:{port} on interface {interface_ip}")

    while True:
        # Receive data from the socket
        data, addr = sock.recvfrom(1024)  # Buffer size is 1024 bytes
        logging.info(f"Received message: {data.decode('utf-8')} from {addr}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    udp_multicast_listener("224.1.1.1", 5007, "0.0.0.0")
