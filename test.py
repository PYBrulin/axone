from axone.node import Node
import time, json
import logging

logging.basicConfig(level=logging.DEBUG)

node_1 = Node(
    name="Node_1",
    memory_endpoint="MemoryEndpoint",
    memory_size=1024,
    parameters={"param_1": 1, "param_2": 2},
)
print(node_1._node_id)
node_2 = Node(
    name="Node_2",
    memory_endpoint="MemoryEndpoint",
    memory_size=1024,
    parameters={"param_3": 1, "param_4": 2},
)
print(node_2._node_id)

# While not KeyboardInterrupt:
try:
    for _ in range(5):
        print(f"Memory content : {node_1._memory}")
        # print(json.dumps(node._memory))
        time.sleep(1)
except KeyboardInterrupt:
    print("KeyboardInterrupt")
    pass
finally:
    node_1._memory.shm.close()
    node_1._memory.shm.unlink()  # Call unlink only once to release the shared memory
    del node_1
    del node_2
