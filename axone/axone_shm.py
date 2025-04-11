import logging
import time

from axone.axone_struct import AxoneStruct
from axone.common import generate_uuid
from axone.shared_memory import AxoneSharedMemory


class CentralizedNode:
    """Class to handle the centralized node.

    Updates when the node becomes available or unavailable to the network
    and provide the list of available nodes when requested
    """

    def __init__(self, name: str, node_id: str, **kwargs) -> None:
        self.node_name = name
        self.node_id = node_id

        self.endpoint = kwargs.get("centralized_memory_endpoint", "")
        assert self.endpoint != self.node_id, "Memory endpoint cannot be the same as the node id."
        self.size = kwargs.get("centralized_memory_size", 1024)
        if not self.endpoint:
            raise ValueError("Memory endpoint cannot be empty.")

        self.memory = AxoneSharedMemory(
            name=generate_uuid(self.endpoint),
            size=self.size,
            centralized=True,
        )

    def advertise(self) -> None:
        """Advertise the node to the centralized memory."""

        # Check if the node is already registered
        if self.memory[self.node_id] is not None:
            logging.warning(f"Node {self.node_name} is already registered.")

        self.memory[self.node_id] = self.node_name


class SelfNode:
    """Class the node use to advertise itself.

    Updates periodically to advertise itself:
    - name
    - timestamp
    - services
    - parameters
    - ? subscriptions
    """

    class NodeStatus(AxoneStruct):
        name: str
        timestamp: float
        services: list[str]
        services_server_port: int | str
        # parameters: Dict[str, Any]

    def __init__(self, name: str, node_id: str, **kwargs) -> None:
        self.node_name = name
        self.node_id = node_id

        self.services_names = kwargs.get("services_names", [])  # String representation of the available services
        self.services_names = ",".join(self.services_names) if self.services_names else ""
        self.services_server_port = (
            0 if not self.services_names else kwargs.get("services_server_port", 0)
        )  # Port to access the services

        self.topics = kwargs.get("topics", [])  # List of topics the node publishes

        self.node_status = self.NodeStatus()

        self.memory = AxoneSharedMemory(
            name=self.node_id,
            size=1024,
            struct=self.node_status,
            centralized=False,  # Only this node has write access
        )

    def advertise(self) -> None:
        """Advertise the node to the centralized memory."""
        self.memory['name'] = self.node_name
        self.memory['timestamp'] = time.time()
        self.memory['services'] = self.services_names
        self.memory['services_port'] = self.services_server_port
        # self.memory['parameters'] = {}
        self.memory['topics'] = self.topics

    def update_timestamp(self) -> None:
        """Update the timestamp of the node."""
        self.memory['timestamp'] = time.time()

    def add_topic(self, topic: str) -> None:
        """Add a topic to the node."""
        self.topics.append(topic)
        self.advertise()

    def remove_topic(self, topic: str) -> None:
        """Remove a topic from the node."""
        self.topics.remove(topic)
        self.advertise()

    def update_topics(self, topics: list[str]) -> None:
        """Update the topics of the node."""
        self.topics = topics
        self.advertise()
