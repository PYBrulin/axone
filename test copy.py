from axone.node import Node

node = Node(
    name="example_publisher",
    memory_endpoint="ExampleNodeMemory",
    memory_size=4096,
)
node.publish_once(
    "topic_published_once",
    message={"data": f"Hello from topic_published_once"},
    rate=1,
)
