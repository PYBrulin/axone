import socket
import struct


def udp_multicast_listener(multicast_group: str, port: int):
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Set socket options to allow multiple sockets to use the same address and port
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind the socket to the port
    sock.bind(('', port))

    # Tell the kernel that we want to join the multicast group
    group = socket.inet_aton(multicast_group)
    mreq = struct.pack('4sL', group, socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    print(f"Listening on multicast group {multicast_group}:{port}")

    while True:
        # Receive data from the socket
        data, addr = sock.recvfrom(1024)  # Buffer size is 1024 bytes
        print(f"Received message: {data} from {addr}")


if __name__ == "__main__":
    udp_multicast_listener("224.1.1.1", 48053)
