import logging
import socket
import time

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

logging.basicConfig(level=logging.INFO)


class ZeroconfListener(ServiceListener):
    def __init__(self):
        self.nodes = {}

    def remove_service(self, zeroconf, type, name):
        logging.info(f"Service {name} removed")
        if name in self.nodes:
            del self.nodes[name]

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            logging.info(f"Service {name} added, service info: {info}")
            self.nodes[name] = info

    def update_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            logging.info(f"Service {name} updated, service info: {info}")
            self.nodes[name] = info


def main():
    zeroconf = Zeroconf()
    listener = ZeroconfListener()
    browser = ServiceBrowser(zeroconf, ["_axone._tcp.local.", "_axone._udp.local."], listener)  # noqa F841

    try:
        while True:
            time.sleep(1)
            # flush the terminal
            print("\033c", end="")

            if not listener.nodes:
                print("No nodes discovered yet...")
            else:
                print("Discovered node:")
                for name, info in listener.nodes.items():
                    if name.endswith("._axone._tcp.local."):
                        print(
                            f" {name},"
                            + f" Address: {socket.inet_ntoa(info.addresses[0])},"
                            + f" Port: {info.port}, Properties: {info.properties}"
                        )
                print('\nDiscovered topics:')
                for name, info in listener.nodes.items():
                    if name.endswith("._axone._udp.local."):
                        print(
                            f" {name},"
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
