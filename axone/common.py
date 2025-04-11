import logging
import random
import socket
import string
import time
from typing import Optional, Tuple

import netifaces


def generate_uuid(input_string: str) -> str:
    """Generate a unique id"""
    # Generate a random string of 10 characters based on the input string
    random.seed(input_string)  # TODO: Meh. This is not bad but not good either.
    return "".join(random.choices(string.ascii_letters + string.digits + input_string, k=10))


def timeit_if_debug(func):
    def wrapper(*args, **kwargs):
        if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
            start_time = time.perf_counter_ns()
            result = func(*args, **kwargs)
            end_time = time.perf_counter_ns()
            millitime = (end_time - start_time) / 1_000_000
            # We expect the execution time to be less than 1 millisecond for most functions
            if millitime > 1:
                logging.error(f"{func.__name__}() execution time: {millitime} milliseconds")
            else:
                logging.debug(f"{func.__name__}() execution time: {millitime} milliseconds")
            return result
        else:
            return func(*args, **kwargs)

    return wrapper


def find_free_port(port_range: Optional[Tuple[int, int]] = None) -> int:
    """Find a free port on the host OS within the specified range.

    Args:
        port_range (Tuple[int, int], optional): The range where to find the available
            port. No restriction if set to None. Defaults to None.

    Returns:
        int: Selected port number.
    """
    _port_range = range(1024, 65535)  # Default range for dynamic ports.
    if port_range is not None:
        _port_range = range(port_range[0], port_range[1] + 1)

    ret = 0
    while ret not in _port_range:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(('', 0))  # Bind to a free port provided by the host OS.
            ret = int(s.getsockname()[1])  # Return the port number assigned.
    return ret


def get_ip_address_for_interface(interface: str) -> str:
    """Get the IP address of a specific network interface."""
    logging.debug(f"Getting IP address for interface {interface}")
    addresses = netifaces.ifaddresses(interface)
    logging.debug(f"Addresses: {addresses}")
    return addresses[netifaces.AF_INET][0]['addr']


if __name__ == "__main__":
    print(generate_uuid("Hello"))
    print(generate_uuid("Hello"))
    print(generate_uuid("Hello1"))

    print(generate_uuid("test_node_to_central"))
    print(generate_uuid("test_node2_to_central"))
