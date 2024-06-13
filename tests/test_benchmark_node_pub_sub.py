import pytest

from axone.axone_struct import AxoneStruct
from axone.node import AxoneNode
from axone.node_process import AxoneNodeProcess


@pytest.fixture
def test_topic() -> AxoneStruct:
    class TestTopic(AxoneStruct):
        a: bool = True
        b: bool = False
        c: int = 1
        d: int = 2
        e: float = 1.23456789
        f: float = 1e9
        g: float = 0.00001357
        h: str = "hello"

    return TestTopic()


@pytest.fixture
def publisher_node() -> AxoneNode:
    # Setup code for creating a AxoneNode instance
    node = AxoneNode(
        name="benchmark_axone_publisher",
        centralized_memory_endpoint="ExampleNodeMemory",
    )
    node.start()
    return node


@pytest.fixture
def subscriber_node() -> AxoneNode:
    # Setup code for creating a AxoneNode instance
    node = AxoneNode(
        name="benchmark_axone_subscriber",
        centralized_memory_endpoint="ExampleNodeMemory",
    )
    node.start()
    return node


@pytest.fixture
def publisher_node_process() -> AxoneNodeProcess:
    # Setup code for creating a AxoneNodeProcess instance
    node = AxoneNode(
        name="benchmark_axone_publisher_process",
        centralized_memory_endpoint="ExampleNodeMemory",
    )
    node.start()
    return node


@pytest.fixture
def subscriber_node_process() -> AxoneNodeProcess:
    # Setup code for creating a AxoneNodeProcess instance
    node = AxoneNode(
        name="benchmark_axone_subscriber_process",
        centralized_memory_endpoint="ExampleNodeMemory",
    )
    node.start()
    return node


def test_encode_benchmark(benchmark, test_topic, publisher_node) -> None:
    # Prepare the arguments for the method
    topic = test_topic

    # Benchmark the encode method
    benchmark.group = "Encode/Decode Operations"
    benchmark(topic.encode)


def test_decode_benchmark(benchmark, test_topic, publisher_node) -> None:
    # Prepare the arguments for the method
    topic = test_topic
    encoded_message = topic.encode()

    # Benchmark the decode method
    benchmark.group = "Encode/Decode Operations"
    benchmark(topic.decode, encoded_message)


def test_publish_once_benchmark(benchmark, test_topic, publisher_node) -> None:
    # Prepare the arguments for the method
    topic = test_topic
    rate = 1.0

    # Publish once to pre-initialize the topic
    publisher_node.publish_once(topic, rate)

    # Benchmark the publish_once method
    benchmark.group = "Publish Operations"
    benchmark(publisher_node.publish_once, topic, rate)

    publisher_node.stop()


def test_publish_once_process_benchmark(benchmark, test_topic, publisher_node_process) -> None:
    # Prepare the arguments for the method
    topic = test_topic
    rate = 1.0

    # Publish once to pre-initialize the topic
    publisher_node_process.publish_once(topic, rate)

    # Benchmark the publish_once method
    benchmark.group = "Publish Operations"
    benchmark(publisher_node_process.publish_once, topic, rate)

    publisher_node_process.stop()


def test_listen_once_benchmark(benchmark, test_topic, publisher_node, subscriber_node) -> None:
    # Prepare the arguments for the method
    topic = test_topic
    rate = 1.0

    # Publish once to pre-initialize the topic
    publisher_node.publish_once(topic, rate)

    # Benchmark the publish_once method with waiting for the receiver
    benchmark.group = "Listen Operations"
    benchmark(subscriber_node.listen_once, topic.__class__.__name__)

    publisher_node.stop()
    subscriber_node.stop()


def test_listen_once_process_benchmark(benchmark, test_topic, publisher_node, subscriber_node_process) -> None:
    # Prepare the arguments for the method
    topic = test_topic
    rate = 1.0

    # Publish once to pre-initialize the topic
    publisher_node.publish_once(topic, rate)

    # Benchmark the publish_once method with waiting for the receiver
    benchmark.group = "Listen Operations"
    benchmark(subscriber_node_process.listen_once, topic.__class__.__name__)

    publisher_node.stop()
    subscriber_node_process.stop()
