"""Example service client.

This script is an example of a client that can connect to the service server.
The server to test this with is initialized and run from the script
`axone/service_server.py`, which you can run directly to test the behaviour.
"""

import logging
import random
import socket
import string
import struct
import sys
import time

from axone.axone_struct import standard_data_decoding, standard_data_encoding
from axone.custom_logger import setup_logger

setup_logger(debug=True)


def send_msg(sock, msg):
    # Prefix each message with a 4-byte length (network byte order)
    msg = struct.pack('>I', len(msg)) + msg
    sock.sendall(msg)


def recv_msg(sock):
    # Read message length and unpack it into an integer
    raw_msglen = recvall(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    # Read the message data
    return recvall(sock, msglen)


def recvall(sock, n):
    # Helper function to recv n bytes or return None if EOF is hit
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data


if False:  # sys.platform != 'win32':
    family = socket.AF_UNIX
    server_address = '/tmp/uds_socket'
else:
    family = socket.AF_INET
    input_port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if input_port == 0:
        raise ValueError("Please provide a port number")
    server_address = ('localhost', input_port)

# Create a socket
sock = socket.socket(family, socket.SOCK_STREAM)

# Connect the socket to the port where the server is listening
logging.info(f'connecting to {server_address}')
sock.connect(server_address)

try:
    for i in range(30):
        # Send data
        # message = b'logging.info_message(This is the message.  It will be repeated.)'

        func_choice = random.randint(0, 3)
        print(func_choice)
        if func_choice == 0:
            message = standard_data_encoding(a=random.randint(1, 100000), b=random.random(), func="simple_addition")
        elif func_choice == 1:
            message = standard_data_encoding(
                message="".join(random.choices(string.ascii_letters + string.digits, k=50)), func="print"
            )
        elif func_choice == 2:
            message = standard_data_encoding(x=random.random(), y=random.random(), z=random.random(), func="move")
        elif func_choice == 3:
            message = standard_data_encoding(func="stop")

        logging.info(f'sending {message!r}')
        send_msg(sock, message)

        # Look for the response
        data = recv_msg(sock)
        logging.info(f'received {standard_data_decoding(data)!r}')

        time.sleep(0.2)
except Exception as e:
    logging.error(e)
finally:
    logging.info('closing socket')
    sock.close()
