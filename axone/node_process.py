from multiprocessing import Process

from .node import Node
from .shared_memory_dict import SharedMemoryDict


class NodeProcess(Node):
    """NodeProcess is a node that executes inside a process."""

    def __init__(self, name: str, **kwargs):
        """Initialize the node."""
        super().__init__(name, **kwargs)

    def start(self):
        """Start the node."""
        # Initialize a Process to run the node
        self._executor = Process(target=self.run)
        self._executor.start()

    def run(self):
        """Run the node."""
        # Initialize the shared memory
        self._memory = SharedMemoryDict(
            name=self.memory_endpoint, size=self.memory_size
        )

        # Register node on the memory
        self._register_node()
        self._federated_server()

    def stop(self):
        """Stop the node."""
        self._executor.terminate()
        self._executor.join()

    def join(self):
        """Join the node."""
        self._executor.join()
