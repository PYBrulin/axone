import logging
import socket
import time
from typing import Dict

import netifaces
from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf
from zeroconf._exceptions import NonUniqueNameException


class ZeroconfListener(ServiceListener):
    def __init__(self) -> None:
        self.nodes = {}

    def remove_service(self, zeroconf, type, name) -> None:
        logging.info(f"Service {name} removed")
        if name in self.nodes:
            del self.nodes[name]

    def add_service(self, zeroconf, type, name) -> None:
        info = zeroconf.get_service_info(type, name)
        if info:
            logging.info(f"Service {name} added, service info: {info}")
            self.nodes[name] = info

    def update_service(self, zeroconf, type, name) -> None:
        info = zeroconf.get_service_info(type, name)
        if info:
            logging.info(f"Service {name} updated, service info: {info}")
            self.nodes[name] = info


class ZeroconfNode:
    def __init__(self, name: str, node_id: str, port: int, interface: str = "lo", **kwargs) -> None:
        self.node_name = name
        self.node_id = node_id
        self.service_port = port
        self.zeroconf = Zeroconf()
        self.listener = ZeroconfListener()
        self.service_type = "_axone._tcp.local."
        self.service_name = f"{self.node_name}.{self.service_type}"
        self.interface = interface
        self.topics = kwargs.get("topics", [])
        new_ip_address = self._get_ip_address(self.interface)
        self.info = ServiceInfo(
            self.service_type,
            self.service_name,
            addresses=[socket.inet_aton(new_ip_address)],
            port=self.service_port,
            properties={"node_id": self.node_id, "topics": ",".join(self.topics)},
        )

    def advertise(self) -> None:
        """Advertise the node using zeroconf."""
        try:
            self.zeroconf.register_service(self.info)
            logging.info(f"Node {self.node_name} advertised on zeroconf")
        except NonUniqueNameException:
            logging.warning(f"Service name {self.service_name} is not unique. Trying a new name.")
            self._handle_non_unique_name_exception()

    def _get_ip_address(self, interface: str) -> str:
        """Get the IP address of a specific network interface."""
        logging.debug(f"Getting IP address for interface {interface}")
        addresses = netifaces.ifaddresses(interface)
        logging.debug(f"Addresses: {addresses}")
        return addresses[netifaces.AF_INET][0]['addr']

    def _handle_non_unique_name_exception(self) -> None:
        """Handle NonUniqueNameException by modifying the service name to make it unique."""
        counter = 1
        while True:
            new_service_name = f"{self.node_name}-{counter}.{self.service_type}"
            new_ip_address = self._get_ip_address(self.interface)
            new_info = ServiceInfo(
                self.service_type,
                new_service_name,
                addresses=[socket.inet_aton(new_ip_address)],
                port=self.service_port,
                properties={"node_id": self.node_id, "topics": ",".join(self.topics)},
            )
            try:
                self.zeroconf.register_service(new_info)
                self.service_name = new_service_name
                self.info = new_info
                logging.info(f"Node {self.node_name} advertised with new name {self.service_name} on zeroconf")
                break
            except NonUniqueNameException:
                counter += 1

    def stop_advertising(self) -> None:
        """Stop advertising the node using zeroconf."""
        self.zeroconf.unregister_service(self.info)
        self.zeroconf.close()
        logging.info(f"Node {self.node_name} stopped advertising on zeroconf")

    def update_topics(self, topics: list[str]) -> None:
        """Update the topics in the zeroconf properties."""
        self.topics = topics
        self.info.properties["topics"] = ",".join(self.topics).encode("utf-8")
        logging.info(f"Updating service with new topics: {self.info.properties['topics']}")
        self.zeroconf.update_service(self.info)
        logging.info(f"Updated topics for node {self.node_name} on zeroconf: {self.topics}")

    def discover_nodes(self) -> Dict[str, ServiceInfo]:
        """Discover nodes using zeroconf."""
        ServiceBrowser(self.zeroconf, self.service_type, self.listener)
        time.sleep(2)  # Wait for discovery
        return self.listener.nodes
