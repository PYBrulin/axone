from multiprocessing import Process, Queue

from .node import Node
from .shared_memory_dict import SharedMemoryDict


class NodeProcess(Node):
    """NodeProcess is a node that executes inside a process."""

    def __init__(self, name: str, **kwargs):
        """Initialize the node."""
        super().__init__(name, **kwargs)

        # A communication bus is required to communicate between this instance and the Process self._executor
        # The communication bus is a Queue
        self._executor = None
        self._tx_queue = None
        self._rx_queue = None

    def start(self):
        """Start the node."""

        self._tx_queue = Queue()
        self._rx_queue = Queue()

        # Initialize a Process to run the node
        self._executor = Process(
            target=self.run, args=(self._tx_queue, self._rx_queue)
        )
        self._executor.start()

    def run(self, tx_queue, rx_queue):
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

    # region Federated server functions

    # endregion

    # region Publisher functions

    # endregion

    # region Subscriber functions

    # endregion

    # region services: Services: Request/Response functions

    # endregion

    # region Parameters: Parameter Server functions

    # endregion
