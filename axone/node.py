import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Union

from .shared_memory_dict import SharedMemoryDict

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 5


# class ArgumentType(enum.Enum):
#     """Argument type."""

#     STRING = 1, "str"
#     INTEGER = 2, 1
#     FLOAT = 3, 1.2
#     BOOLEAN = 4, True

#     def __init__(self, _value, _type) -> None:
#         self.value = _value
#         self.type = _type


class Node:
    def __init__(
        self,
        name: str = None,
        memory_endpoint: str = "",
        memory_size: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
        actions: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.memory_endpoint = memory_endpoint
        self.memory_size = memory_size

        self._memory = SharedMemoryDict(
            name=self.memory_endpoint, size=self.memory_size
        )
        self._node_id = self._get_node_id()

        # Register the nodes parameters
        # Parameters are variables that can be used by the underlying program that runs the node
        self.parameters = parameters
        # Ensure parameters are json serializable
        if self.parameters is not None:
            self.parameters = json.dumps(self.parameters)

        # Register the nodes actions
        # Actions arespecific calls that can be made to the underlying program that runs the node
        # The actions are registered as a dictionary of key-value pairs
        # The key is the name of the action
        # The value is a dictionary of the arguments name and type of the action
        # self.actions = actions
        # # Ensure parameters are json serializable
        # if self.actions is not None:
        #     self.actions = json.dumps(self.actions)

        # Register node on the memory
        self._register_node()

        self._executor = ThreadPoolExecutor(max_workers=10)
        # self._executor.submit(self._listen)

    def _get_node_id(self) -> str:
        """Generate a unique node id."""
        return (
            self.name
        )  # "".join(random.choices(string.ascii_letters + string.digits, k=10))

    def _register_node(self) -> None:
        """Register node on the memory."""
        # TODO:  https://stackoverflow.com/questions/16676177/setting-an-item-in-nested-dictionary-with-setitem
        db = self._memory.get("__nodes", default={})

        # Register node within __nodes if not already registered
        if self._node_id not in db:
            logger.info(f"Registering node {self._node_id} on the memory.")
            db[self._node_id] = {
                "name": self.name,
            }
        else:
            logger.error(f"Node {self._node_id} already registered on the memory.")

        # Register node parameters
        if self.parameters is not None:
            db[self._node_id]["parameters"] = self.parameters

        # Write back to memory
        self._memory["__nodes"] = db

    # %% Publish functions
    def publish_once(
        self,
        topic: str,
        message: Any,
        rate: Optional[Union[int, float]] = None,
    ) -> None:
        """Publish a message once on a topic."""
        # Ensure the topic is available
        # Compare the topic source with the node id
        # If the topic source is the node id, then the topic is available to this node
        # Else, the topic is not available to this node, then check if the topic hs reached a timeout
        # If the topic has reached a timeout, then the topic is available to this node
        # Else, the topic is not available to this node

        # Add properties
        properties = {
            "__source": self._node_id,
            "__timestamp": time.time(),
            "__rate": -1 if rate is None else rate,  # -1 means publish once
        }

        # Check if the topic is available
        if self._memory.get(topic, default={}).get("__source") == self._node_id:
            # Topic is available
            self._memory[topic] = message | properties
        elif (
            self._memory.get(topic, default={}).get("__timestamp", 0)
            + self._memory.get(topic, default={}).get("__rate", 0)
            < time.time() + DEFAULT_TIMEOUT
        ):
            # Topic is available after timeout
            self._memory[topic] = message | properties
        else:
            # Topic is not available
            logger.error(
                f"Topic {topic} is not available for node {self._node_id}:{self.name} to publish."
            )

    def register_publish(self, topic: str, message: Any, rate: float = 0) -> None:
        """Publish a message on a topic."""
        logging.debug("Registering publisher", topic, message, rate)
        # Initialize a Thread to publish to the topic periodically
        self._executor.submit(self._publish, topic, message, rate)

    def _publish(self, topic: str, message: Any, rate: float = 0) -> None:
        """Publish a message on a topic."""
        while True:
            logging.debug(
                "Publishing",
                topic,
                message if not callable(message) else message(),
                rate,
            )
            self.publish_once(
                topic,
                message if not callable(message) else message(),
                rate,
            )
            time.sleep(1 / float(rate))

    # %% Subscribe functions
    def register_subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a topic."""
        # Initialize a Thread to listen to the topic periodically
        self._executor.submit(self._listen, topic, callback)

    def _listen(self, topic: str, callback: Callable) -> None:
        """Listen to a topic."""
        _last_message = None
        _retry = 0  # TODO: Add a global variable for max counter
        while True:
            db = self._memory.get(topic, default={})

            if db:  # Topic is available
                if db != _last_message:
                    _last_message = db
                    _retry = 0
                    callback(db)
                else:
                    _retry = min(10, _retry + 1)

                timestamp = db.get("__timestamp", 0)
                rate = db.get("__rate", -1)

                # Sleep until the next message
                if rate > 0 and _retry < 10:
                    # Try to align the subscription with the publishing rate as much as possible
                    time.sleep(max(0, 1 / float(rate) - time.time() + timestamp))
                else:
                    # If rate is not specified, then sleep for 1 second
                    time.sleep(1)

            else:  # No topic with this name is available
                pass
                # logger.error(
                #     f"No topic with name {topic} has been puclished for node {self._node_id}:{self.name} to subscribe."
                # )

    # %% Action functions
    def register_action(self, action: str, callback: Callable) -> None:
        """Register an action."""
        # Initialize a Thread to listen to the action periodically
        self._executor.submit(self._listen_action, action, callback)

    def action(self, action: str, **kwargs: Any) -> None:
        """Call an action."""
        # Check if the action is available
        if self._memory.get(action, default={}).get("__source") == self._node_id:
            # Action is available
            self._memory[action] = kwargs.update(
                {
                    "__source": self._node_id,
                    "__timestamp": time.time(),
                }
            )
        else:
            # Action is not available
            logger.error(
                f"Action {action} is not available for node {self._node_id}:{self.name} to call."
            )

    def search_node_by_name(self, name: str) -> List[str]:
        """Search for a node by name."""
        nodes = self._memory.get("__nodes", default={})
        return [node for node in nodes if nodes[node]["name"] == name]
