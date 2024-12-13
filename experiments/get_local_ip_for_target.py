import socket


def get_local_ip_for_target(target_ip: str) -> str:
    """Get the local IP address that can communicate with the target IP."""
    try:
        # Create a temporary socket
        temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to the target IP on an arbitrary port
        temp_socket.connect((target_ip, 1))
        # Get the local IP address used for this connection
        local_ip = temp_socket.getsockname()[0]
        # Close the temporary socket
        temp_socket.close()
        return local_ip
    except Exception as e:
        raise RuntimeError(f"Cannot determine local IP address for target {target_ip}: {e}")


# Example usage
target_ip = "192.168.144.43"
local_ip = get_local_ip_for_target(target_ip)
print(f"Local IP address for communicating with {target_ip} is {local_ip}")
