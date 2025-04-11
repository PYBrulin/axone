import logging
import socket

from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf
from zeroconf._exceptions import NonUniqueNameException

from axone.common import get_ip_address_for_interface


class ZeroconfListener(ServiceListener):
    def __init__(self) -> None:
        self.nodes = {}

    def remove_service(self, zeroconf, type, name) -> None:
        logging.debug(f"Service {name} removed")
        if name in self.nodes:
            del self.nodes[name]

    def add_service(self, zeroconf, type, name) -> None:
        info = zeroconf.get_service_info(type, name)
        if info:
            logging.debug(f"Service {name} added, service info: {info}")
            self.nodes[name] = info

    def update_service(self, zeroconf, type, name) -> None:
        info = zeroconf.get_service_info(type, name)
        if info:
            logging.debug(f"Service {name} updated, service info: {info}")
            self.nodes[name] = info


class ZeroconfNode:
    def __init__(self, name: str, node_id: str, port: int, interface: str = "lo", **kwargs) -> None:
        self.node_name = name
        self.node_id = node_id
        self.service_port = port
        self.zeroconf = Zeroconf()
        self.listener = ZeroconfListener()
        self.service_type = "_axone._tcp.local."
        self.browser = ServiceBrowser(self.zeroconf, self.service_type, self.listener)
        self.service_name = f"{self.node_name}.{self.service_type}"
        self.service_address = None
        self.hide_services = kwargs.get("hide_services", False)
        self.interface = interface
        self.topics = kwargs.get("topics", [])

        # Advertised properties of the node
        self.properties = {"node_id": self.node_id}

        if self.topics:
            self.properties = {**self.properties, **{"topics": ",".join(self.topics)}}

        _services = kwargs.get("services", {})
        if not self.hide_services and _services:
            self.services = []
            for service, _ in _services.items():
                if callable(service):
                    self.services.append(service.__name__)
                elif isinstance(service, str):
                    self.services.append(service)  # ? What is the point of this?
                else:
                    raise TypeError(f"service {service} is not a string or a function.")
            self.properties = {**self.properties, **{"services": ",".join(self.services)}}

        self.service_address = get_ip_address_for_interface(self.interface)
        self.info = ServiceInfo(
            self.service_type,
            self.service_name,
            addresses=[socket.inet_aton(self.service_address)],
            port=self.service_port,
            properties=self.properties,
        )

    @property
    def discovered_nodes(self) -> dict[str, ServiceInfo]:
        """Listed discovered nodes"""
        return self.listener.nodes

    def advertise(self) -> None:
        """Advertise the node using zeroconf"""
        try:
            self.zeroconf.register_service(self.info)
            logging.info(f"Node {self.node_name} advertised on zeroconf")
        except NonUniqueNameException:
            logging.warning(f"Service name {self.service_name} is not unique. Trying a new name.")
            self._handle_non_unique_name_exception()

    def _handle_non_unique_name_exception(self) -> None:
        """Handle NonUniqueNameException by modifying the service name to make it unique"""
        counter = 1
        while True:
            new_service_name = f"{self.node_name}-{counter}.{self.service_type}"
            self.service_address = get_ip_address_for_interface(self.interface)
            new_info = ServiceInfo(
                self.service_type,
                new_service_name,
                addresses=[socket.inet_aton(self.service_address)],
                port=self.service_port,
                properties=self.properties,
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
        """Stop advertising the node using zeroconf"""
        self.zeroconf.unregister_service(self.info)
        self.zeroconf.close()
        logging.info(f"Node {self.node_name} stopped advertising on zeroconf")

    def update_topics(self, published_topics: list[str]) -> None:
        """Update the topics in the zeroconf properties"""
        try:
            self.topics = published_topics
            if self.topics:
                self.properties = {**self.properties, **{"topics": ",".join(self.topics).encode("utf-8")}}
            elif hasattr(self.properties, "topics"):
                del self.properties["topics"]
            self.info._set_properties(self.properties)
            # I should not be using the above private method, but i couldn't find any alternative and it works for this use.
            # I am enclosing this method in a try/except for safety because of this.
            self.zeroconf.update_service(self.info)
            logging.info(f"Updated topics for node {self.node_name} on zeroconf: {self.topics}")
        except Exception as e:
            logging.error(f"Unable to update advertised topics: {e}", exc_info=True)
