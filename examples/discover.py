"""Simple zeroconf browser to list discoverable AxoneNode and their topics."""

import logging
import socket
import time

from zeroconf import ServiceBrowser, Zeroconf

from axone.zeroconf_node import ZeroconfListener

logging.basicConfig(level=logging.INFO)


def main() -> None:
    zeroconf = Zeroconf()
    listener = ZeroconfListener()
    browser = ServiceBrowser(zeroconf, ["_axone._tcp.local.", "_axone._udp.local."], listener)  # noqa F841

    try:
        while True:
            time.sleep(1)
            print("\033c", end="")  # flush the terminal

            if not listener.nodes:
                print("No nodes discovered yet...")
            else:
                print("Discovered node:")
                for name, info in listener.nodes.items():
                    if name.endswith("._axone._tcp.local."):
                        print(
                            f"{info.port} - {name}\n\t"
                            + f" Address: {socket.inet_ntoa(info.addresses[0])},"
                            + f" Port: {info.port}, Properties: {info.properties}"
                        )

                print('\nDiscovered topics:')
                for name, info in listener.nodes.items():
                    if name.endswith("._axone._udp.local."):
                        print(
                            f"{info.port} - {name}\n\t"
                            + f" Address: {socket.inet_ntoa(info.addresses[0])},"
                            + f" Port: {info.port}, Properties: {info.properties}"
                        )

            print("\nPress Ctrl-C to exit...")

    except KeyboardInterrupt:
        pass
    finally:
        zeroconf.close()


if __name__ == "__main__":
    main()
