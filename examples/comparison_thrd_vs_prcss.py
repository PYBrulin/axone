import time

import numpy as np
from tqdm import tqdm

from axone.node import Node
from axone.node_process import NodeProcess


def get_stats(times):
    times = np.array(times)
    times_df = np.diff(times)
    return {
        "mean": np.mean(times_df),
        "std": np.std(times_df),
        "min": np.min(times_df),
        "max": np.max(times_df),
    }


# region Node
node = Node(
    name="example_publisher",
    memory_endpoint="ExampleNodeMemory",
    memory_size=4096,
)

# Register a rated publisher
node.publish_rate(
    "topic_published_rate",
    message={"message": f"Hello from topic_published_rate"},
    rate=3,
)

try:
    times = []
    for i in tqdm(range(1000)):
        time.sleep(0.01)
        times.append(time.time())

    print(get_stats(times))

except KeyboardInterrupt:
    print("KeyboardInterrupt")
    pass
finally:
    node._memory.shm.close()
    del node

# endregion

# region NodeProcess
node = NodeProcess(
    name="example_publisher",
    memory_endpoint="ExampleNodeMemory",
    memory_size=4096,
)

# Register a rated publisher
node.publish_rate(
    "topic_published_rate",
    message={"message": f"Hello from topic_published_rate"},
    rate=3,
)

try:
    times = []
    for i in tqdm(range(1000)):
        start = time.time()
        time.sleep(0.01)
        times.append(time.time())

    print(get_stats(times))

except KeyboardInterrupt:
    print("KeyboardInterrupt")
    pass
finally:
    node._memory.shm.close()
    del node

# endregion
