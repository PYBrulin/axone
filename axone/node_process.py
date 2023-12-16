from node import Node


class NodeProcess(Node):
    """NodeProcess is a node that executes inside a process."""

    def __init__(self, name, process):
        """Initialize the node."""
        super().__init__(name)
        self.process = process

    def start(self):
        """Start the node."""
        self.process.start()

    def stop(self):
        """Stop the node."""
        self.process.terminate()
        self.process.join()

    def join(self):
        """Join the node."""
        self.process.join()
