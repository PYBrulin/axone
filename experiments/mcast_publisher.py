import socket
import time


def udp_multicast_publisher(multicast_group: str, port: int):
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Set the time-to-live for messages to 1 so they do not go past the local network segment
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)

    message = "Hello, Multicast!"

    while True:
        # Send data to the multicast group
        sock.sendto(message.encode('utf-8'), (multicast_group, port))
        print(f"Sent message: {message} to {multicast_group}:{port}")
        time.sleep(1)  # Wait for 1 second before sending the next message


if __name__ == "__main__":
    udp_multicast_publisher("224.1.1.1", 5007)
