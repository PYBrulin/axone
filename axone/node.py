from concurrent.futures import ThreadPoolExecutor
from threading import Thread
import random
import string
import json, logging
import time
from .shared_memory_dict import SharedMemoryDict
from typing import Any, Optional, List, Tuple, Dict, Union, Callable, TypeVar

logger = logging.getLogger(__name__)


class Node:
    def __init__(
        self,
        name: str = None,
        memory_endpoint: str = "",
        memory_size: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.memory_endpoint = memory_endpoint
        self.memory_size = memory_size

        self._memory = SharedMemoryDict(
            name=self.memory_endpoint, size=self.memory_size
        )
        self._node_id = self._get_node_id()

        self.parameters = parameters
        # Ensure parameters are json serializable
        if self.parameters is not None:
            self.parameters = json.dumps(self.parameters)

        # Register node on the memory
        self._register_node()

        # self._publishers = {}
        # self._subscribers = {}
        # self._executor = ThreadPoolExecutor(max_workers=10)
        # # self._executor.submit(self._listen)

    def _get_node_id(self) -> str:
        """Generate a unique node id."""
        return "".join(random.choices(string.ascii_letters + string.digits, k=10))

    def _register_node(self) -> None:
        """Register node on the memory."""
        # # Ensure "__nodes" key exists
        # if "__nodes" not in self._memory:
        #     self._memory["__nodes"] = []

        # # Register node within __nodes if not already registered
        # if self._node_id not in self._memory["__nodes"]:
        #     logger.info(f"Registering node {self._node_id} on the memory.")
        #     self._memory["__nodes"] += [
        #         {
        #             self._node_id: {
        #                 "name": self.name,
        #             }
        #         }
        #     ]
        # else:
        #     logger.error(f"Node {self._node_id} already registered on the memory.")

        # Ensure "__nodes" key exists
        if "__nodes" not in self._memory:
            self._memory["__nodes"] = {}

        # Register node within __nodes if not already registered
        if self._node_id not in self._memory["__nodes"]:
            logger.info(f"Registering node {self._node_id} on the memory.")
            self._memory["__nodes"] = self._memory["__nodes"].update(
                {
                    self._node_id: {
                        "name": self.name,
                    }
                }
            )
            print(self._memory["__nodes"])
            # print(self._memory["__nodes"][self._node_id])

        else:
            logger.error(f"Node {self._node_id} already registered on the memory.")

        # Register node parameters
        # if self.parameters is not None:
        #     self._memory["__nodes"][self._node_id]["parameters"] = self.parameters


if __name__ == "__main__":
    node = Node(name="test")
    print(node._get_node_id())
