# AXONE

Axone is a ROS-like framework for distributed computing implemented in Python. It implement a shared memory model for communication between nodes on a single system. No outside communication is supported at this time.

The package provide basic functionnalities similar to ROS, such as:

- Publisher/Subscriber: A node can publish data to a topic, and other nodes can subscribe to this topic to receive the data.
- Service/Client: A node can provide a service, and other nodes can call this service.
- Parameter server: A node can store parameters on the parameter server, and other nodes can retrieve them.

## Installation

Axone can be installed locally using pip:

```bash
pip install -e .
```
