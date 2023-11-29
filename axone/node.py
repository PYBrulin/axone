import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Union

from .shared_memory_dict import SharedMemoryDict

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 5
MAX_RETRIES = 10


class Node:
    def __init__(self, **kwargs) -> None:
        """Initialize a node for the Axone framework.

        Args:
            name (str, optional): The name of the node. Defaults to "".
            memory_endpoint (str, optional): The name of the shared memory. Defaults to "".
            memory_size (Optional[int], optional): The size of the shared memory. Defaults to None.
            parameters (Optional[Dict[str, Any]], optional): The parameters of the node. Defaults to None.
            actions (Optional[Dict[str, Any]], optional): The actions of the node. Defaults to None.
            config_file (Optional[str], optional): The path to a config file which Can be used to load a common set of
                parameters for all nodes on the same system from a json file. Defaults to None.
            action_server_rate (float, optional): The rate at which the action server is checked for new actions.
                Defaults to 10Hz.

        Raises:
            ValueError: Whether a required parameter is missing.
            FileNotFoundError: if the config file is specified but does not exist.
        """
        self.config_file = kwargs.get("config_file", None)
        if self.config_file is not None:
            # Load the config file
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    try:
                        # Merge the config file with the kwargs
                        kwargs = {**kwargs, **json.load(f)}
                    except Exception as e:
                        raise ValueError(
                            f"Config file {self.config_file} is not a valid json file."
                        )
            else:
                raise FileNotFoundError(
                    f"Config file {self.config_file} does not exist."
                )

        self._name = kwargs.get("name", "")
        self._memory_endpoint = kwargs.get("memory_endpoint", "")
        self._memory_size = kwargs.get("memory_size", None)
        self._parameters = kwargs.get("parameters", None)
        self._actions = kwargs.get("actions", None)
        self._action_server_rate = 1 / float(
            kwargs.get("action_server_rate", 10)
        )

        # Check for required parameters
        if self.name == "":
            raise ValueError("Node name cannot be empty.")
        if self.memory_endpoint == "":
            raise ValueError("Memory endpoint cannot be empty.")

        # Store the kwargs for later use
        # In case of a restart, the node will be reinitialized with the same kwargs
        self.kwargs = kwargs

        # Initialize the shared memory
        self._memory = SharedMemoryDict(
            name=self.memory_endpoint, size=self.memory_size
        )

        # Generate a unique node id
        self._node_id = self._get_node_id()

        self._actions_map = {}

        # Initialize a Thread to listen to the memory events
        self._executor = ThreadPoolExecutor(max_workers=10)
        self._executor.submit(self._listen)

        # Initialize a Thread to listen to the actions
        if self.actions is not None:
            self._action_executor = ThreadPoolExecutor(max_workers=1)

        # Register node on the memory
        self._register_node()

        # Initialize a Thread to cleanup the memory periodically
        self._cleaner_executor = ThreadPoolExecutor(max_workers=10)
        self._cleaner_executor.submit(self._cleanup)

    @property
    def node_id(self) -> str:
        """Return the node id."""
        return self._node_id

    @property
    def name(self) -> str:
        """Return the node name."""
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        """Set the node name."""
        self._name = name
        self.kwargs["name"] = name

    @property
    def memory_endpoint(self) -> str:
        """Return the memory endpoint."""
        return self._memory_endpoint

    @memory_endpoint.setter
    def memory_endpoint(self, memory_endpoint: str) -> None:
        """Set the memory endpoint."""
        self._memory_endpoint = memory_endpoint
        self.kwargs["memory_endpoint"] = memory_endpoint

    @property
    def memory_size(self) -> Optional[int]:
        """Return the memory size."""
        return self._memory_size

    @memory_size.setter
    def memory_size(self, memory_size: Optional[int]) -> None:
        """Set the memory size."""
        self._memory_size = memory_size
        self.kwargs["memory_size"] = memory_size

    @property
    def parameters(self) -> Optional[Dict[str, Any]]:
        """Return the node parameters."""
        return self._parameters

    @parameters.setter
    def parameters(self, parameters: Optional[Dict[str, Any]]) -> None:
        """Set the node parameters."""
        self._parameters = parameters
        self.kwargs["parameters"] = parameters

    @property
    def actions(self) -> Optional[Dict[str, Any]]:
        """Return the node actions."""
        return self._actions

    @actions.setter
    def actions(self, actions: Optional[Dict[str, Any]]) -> None:
        """Set the node actions."""
        self._actions = actions
        self.kwargs["actions"] = actions

    @property
    def action_server_rate(self) -> float:
        """Return the action server rate."""
        return self._action_server_rate

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
        if self.node_id not in db:
            logger.info(f"Registering node {self.node_id} on the memory.")
            db[self.node_id] = {
                "name": self.name,
            }
        else:
            logger.warning(
                f"Node {self.node_id} already registered on the memory."
            )

        # Register node parameters
        if self.parameters is not None:
            db[self.node_id]["parameters"] = self.parameters

        # Register node actions
        self._setup_actions(db)

        # Write back to memory
        self._memory["__nodes"] = db

    def restart(self) -> None:
        """Restart the node."""
        logger.info(f"Restarting node {self.node_id}:{self.name}.")

        # Restart the node
        self._memory.shm.close()
        self._memory.shm.unlink()  # Call unlink only once to release the shared memory

        # Reinitialize the node
        self.__init__(**self.kwargs)  # ?

    # region Publisher functions
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
            "__source": self.node_id,
            "__timestamp": time.time(),
            "__rate": -1 if rate is None else rate,  # -1 means publish once
        }

        # Check if the topic is available
        if self._memory.get(topic, default={}).get("__source") == self.node_id:
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
                f"Topic {topic} is not available for node {self.node_id}:{self.name} to publish."
            )

    def register_publish(
        self, topic: str, message: Any, rate: float = 0
    ) -> None:
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

    # endregion

    # region Subscriber functions
    def register_subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a topic."""
        # Initialize a Thread to listen to the topic periodically
        self._executor.submit(self._listen, topic, callback)

    def _listen(self, topic: str, callback: Callable) -> None:
        """Listen to a topic."""
        _last_message = None
        _retry = 0
        while True:
            db = self._memory.get(topic, default={})

            if db:  # Topic is available
                if db != _last_message:
                    _last_message = db
                    _retry = 0
                    callback(db)
                else:
                    _retry = min(MAX_RETRIES, _retry + 1)

                timestamp = db.get("__timestamp", 0)
                rate = db.get("__rate", -1)

                # Sleep until the next message
                if rate > 0 and _retry < MAX_RETRIES:
                    # Try to align the subscription with the publishing rate as much as possible
                    time.sleep(
                        max(0, 1 / float(rate) - time.time() + timestamp)
                    )
                else:
                    # If rate is not specified, then sleep for 0.1 second
                    time.sleep(0.1)

            else:  # No topic with this name is available
                pass
                # logger.error(
                #     f"No topic with name {topic} has been puclished for node {self.node_id}:{self.name} to subscribe."
                # )

    # endregion

    # region Actions: Service/Client functions

    # Actions are specific calls that can be made to the underlying program that runs the node
    # The actions are registered as a dictionary of key-value pairs
    # The key is the name of the action
    # The value is a dictionary of the arguments name and type of the action
    # Example: Two actions are registered for a node : "move" and "stop"
    # actions = {
    #     "move": {
    #         "x": ArgumentType.FLOAT,
    #         "y": ArgumentType.FLOAT,
    #         "z": ArgumentType.FLOAT,
    #     },
    #     "stop": {},
    # }
    # The available actions for each nodes are registered on the __nodes dictionary under the key "actions" for each node
    # Example:
    # __nodes = {
    #     "node_id": {
    #         "name": "node_name",
    #         "actions": {
    #             "move": {
    #                 "x": ArgumentType.FLOAT,
    #                 "y": ArgumentType.FLOAT,
    #                 "z": ArgumentType.FLOAT,
    #             },
    #             "stop": {},
    #         },
    #     },
    # }

    def _setup_actions(
        self,
        database: Optional[Dict[str, Any]],
    ) -> None:
        """Register node actions."""

        # Ensure the __actions buffer is intialized
        if not "__actions" in self._memory:
            self._memory["__actions"] = []

        if self.actions is not None:
            self._action_executor.submit(self._listen_action)

            # format the actions dictionary
            self._actions_map = {}
            _actions = {}
            for action in self.actions.keys():
                if callable(action):
                    self._actions_map[action.__name__] = action
                    _actions[action.__name__] = self.actions[action]
                elif isinstance(action, str):
                    # ? What is the point of this?
                    self._actions_map[action] = self.actions[action]
                    _actions[action] = self.actions[action]
                else:
                    raise TypeError(
                        f"Action {action} is not a string or a function."
                    )

            # Inform the memory of the actions available for this node
            if database is None:
                db = self._memory.get("__nodes", default={})
            else:
                db = database
            db[self.node_id]["actions"] = _actions
            if database is None:
                self._memory["__nodes"] = db

    def _listen_action(self) -> None:
        """Listen to actions."""
        # Listening and processing actions might take some time
        # Therefore, to not block the memory, we first need to fetch and remove
        # all actions directed to this node from the memory, all in a single
        # operation. Then, we can process the actions

        while True:
            action_buffer = []

            # if not "__actions" in self._memory:
            #     continue

            # TODO: Find a way to do this in a single operation (Some sort of atomic operation)
            # It currently fetch the same actions multiple times
            # Alternatives! ===================================================

            action_buffer = self._memory.split_actions_db(self.node_id)

            # action_buffer = []
            # remaining_actions = []
            # for action in self._memory.get('__actions', default=[]):
            #     # Note: two operations means that other node can acquire the lock in between
            #     if action["__dst"] == self.node_id:
            #         action_buffer.append(action)
            #     else:
            #         remaining_actions.append(action)
            # self._memory['__actions'] = remaining_actions
            # Alternatives! ===================================================
            # action_buffer = list(
            #     filter(
            #         lambda x: x["__dst"] == self.node_id,
            #         self._memory.get('__actions', default=[]),
            #     )
            # )
            # self._memory['__actions'] = list(
            #     filter(
            #         lambda x: x["__dst"] != self.node_id,
            #         self._memory.get('__actions', default=[]),
            #     )
            # )
            # =================================================================
            # actions = self._memory.get('__actions', default=[])
            # action_buffer, self._memory['__actions'] = [
            #     x for x in actions if x["__dst"] == self.node_id
            # ], [x for x in actions if x["__dst"] != self.node_id]
            # =================================================================

            if action_buffer:
                logger.debug(
                    f"Processing {len(action_buffer)} actions for node {self.node_id}:{self.name}:\n\t"
                    + "\n\t".join([str(_) for _ in action_buffer])
                )

            for action in action_buffer:
                # Find the appropriate callback for the action
                # Get the first key in action that does not start with "__"
                callback = self._actions_map.get(
                    next(
                        filter(lambda x: not x.startswith("__"), action.keys())
                    ),
                    None,
                )

                if callback is None:
                    # Action is not available
                    continue
                else:
                    logger.debug(
                        f"Executing action {action} for node {self.node_id}:{self.name} with callback {callback.__name__}."
                    )

                    # Execute the action
                    response = callback(**action[callback.__name__])

                    # If the action has a response, then send the response back to the source node
                    if (
                        response is not None
                        and action.get("__ans", None) is not None
                    ):
                        self.call_action(
                            dest_node=action.get("__src"),
                            action=action.get("__ans"),
                            **response,
                        )

            # Sleep for a while before checking for new actions
            time.sleep(self.action_server_rate)

    def call_action(
        self,
        dest_node: str,
        action: str,
        answer: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Call an action on a node."""
        # Check if the action is available
        # We need to check if the node is available first, otherwise the action
        #  buffer will get congested with inexistent action calls
        if action in self.list_node_actions(dest_node):
            # Action is available
            properties = {
                "__dst": dest_node,
                "__src": self.node_id,
                "__timestamp": time.time(),
            }

            # Add the name of the answer action if any
            if answer is not None:
                if callable(answer):
                    properties["__ans"] = answer.__name__
                elif isinstance(answer, str):
                    properties["__ans"] = answer
                else:
                    logger.error(
                        f"Answer action {answer} is not a string or a function. Answer action will be ignored."
                    )

            # db["__actions"] += [{action: kwargs} | properties]

            # Replace any previous call to the same action that has not been executed yet
            self._memory["__actions"] = [
                _action
                for _action in self._memory.get("__actions", [])
                if not (
                    _action.get("__dst") == dest_node
                    and _action.get("__src") == self.node_id
                    and action in _action.keys()
                )
            ] + [{action: kwargs} | properties]
            # # Write back to memory
            # self._memory["__actions"] = db["__actions"]

            logger.debug(
                f"Called action {action} on node {dest_node}.",
            )
        else:
            # Action is not available
            logger.error(
                f"Action {action} cannot be called on node {dest_node} because it is not available."
            )

    def find_node_by_name(self, name: str) -> List[str]:
        """Search for a node by name."""
        nodes = self._memory.get("__nodes", default={})
        return [node for node in nodes if nodes[node]["name"] == name]

    def list_node_actions(self, node_id: str) -> Dict[str, Any]:
        """List the actions available for a node."""
        return (
            self._memory.get("__nodes", {}).get(node_id, {}).get("actions", {})
        )

    # endregion

    # region Parameters: Parameter Server functions
    def update_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update node parameters."""
        db = self._memory.get("__nodes", default={})

        if self.node_id not in db:
            # ! This case might happen if the server had to restart unexpectedly
            return

        db[self.node_id]["parameters"] = parameters
        self._memory["__nodes"] = db

    def get_parameters(self, node_id: str) -> Dict[str, Any]:
        """Get node parameters."""
        db = self._memory.get("__nodes", default={})
        return db.get(node_id, {}).get("parameters", {})

    # endregion

    # region Centralized cleanup functions
    # As nodes act as a federated system, it is important to have a decentralized
    #  cleanup mechanism accross all nodes to avoid memory leaks.
    # The cleanup mechanism is based on the following assumptions:
    # 1. All nodes are responsible for cleaning up the shared memory
    # 2. Every node might get disconnected from the shared memory at any time
    # 3. Rated topics should be used within their timespan to avoid memory leaks
    # 4. Topics published only once should be used within a limited timespan to avoid memory leaks
    # 5. Actions should be executed as soon as possible to avoid memory leaks
    def _cleanup(self) -> None:
        """
        Cleanup the structure periodically.
        All nodes should call this function periodically to clean up the memory.
        """
        while True:
            logger.debug("Cleaning up memory.")

            # Ensure this node is still registered
            if self.node_id not in self._memory.get("__nodes", {}):
                logging.critical(
                    f"Node {self.node_id}:{self.name} has been disconnected from the memory. Re-registering the node."
                )
                self._register_node()

            # Cleanup unused topics
            # TODO: This would require some sort of heartbeat mechanism
            # self._cleanup_nodes()

            # Cleanup unused topics
            self._cleanup_topics()

            # Cleanup unused actions
            self._cleanup_actions()

            # Sleep for a while before cleaning up again
            time.sleep(DEFAULT_TIMEOUT)

    def _cleanup_topics(self) -> None:
        """Cleanup unused topics."""
        # A topic is considered stale if it has not been updated for more than
        # DEFAULT_TIMEOUT seconds or if the source node is not registered
        db = self._memory.items()
        for topic in db.keys():
            if topic.startswith("__"):
                # Skip internal data strtuctures
                continue
            if (
                db[topic].get("__timestamp", 0)
                + 1 / float(db[topic].get("__rate", 0))
                + DEFAULT_TIMEOUT
                < time.time()
            ) or (db[topic].get("__source") not in db.get("__nodes", {})):
                # Remove the topic
                logger.debug(f"Removing topic {topic} from the memory.")
                self._memory.pop(topic)

    def _cleanup_actions(self) -> None:
        """Cleanup unused actions."""
        # An action is considered stale if it has not been executed for more than DEFAULT_TIMEOUT seconds
        db = self._memory.items()
        db["__actions"] = [
            _action
            for _action in db["__actions"]
            if _action.get("__timestamp", 0) + DEFAULT_TIMEOUT > time.time()
        ]

        # Rewrite the actions buffer
        self._memory["__actions"] = db["__actions"]

    # endregion
