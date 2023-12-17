from multiprocessing import Process

from .node import Node


class NodeProcess(Node):
    """NodeProcess is a node that executes inside a process."""

    def __init__(self, name: str, **kwargs):
        """Initialize the node."""
        super().__init__(name, **kwargs)

    def start(self):
        """Start the node."""
        self._executor = Process(target=self._federated_server)
        self._executor.start()

    def stop(self):
        """Stop the node."""
        self._executor.terminate()
        self._executor.join()

    def join(self):
        """Join the node."""
        self._executor.join()
