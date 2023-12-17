import json
import logging  # noqa
import os
import time
from typing import NoReturn

from custom_logger import setup_logger

from axone.node import Node

setup_logger(debug=False)


class SimpleServerNode:
    """Simple server example node to display the content of the shared memory"""

    def __init__(self) -> None:
        # Register node
        self.node = Node(
            name="simple_server",
            memory_endpoint="ExampleNodeMemory",
            memory_size=4096,
        )
        self.node.start()
        self.highest_rate = 1

    def run(self) -> NoReturn:
        try:
            while True:
                # Clear the terminal before printing the memory content
                os.system("cls||clear")

                # Read the memory content
                db = dict(self.node._memory)
                print("Memory content :")
                print(
                    json.dumps(
                        db,
                        sort_keys=True,
                        indent=4,
                    )
                )

                #! memory size is only updated when the memory is written
                # print(f"Memory size : {self.node._memory.size}")

                # Find the highest rated topic and try to match its frequency
                # with the loop frequency
                self.highest_rate = 1
                for topic in db.keys():
                    if isinstance(db[topic], dict):
                        rate = db[topic].get("__r", 0)
                        if rate > self.highest_rate:
                            self.highest_rate = rate

                print(f"Highest rate : {self.highest_rate}")

                time.sleep(1 / float(self.highest_rate))  # 10Hz
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            pass
        finally:
            self.node._memory.shm.close()
            del self.node


if __name__ == "__main__":
    ssn = SimpleServerNode()
    ssn.run()
