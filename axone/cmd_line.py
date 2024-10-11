import argparse
import cmd
import logging
import os
import time

from axone.custom_logger import setup_logger
from axone.node_process import AxoneNodeProcess


class AxoneCommandLine(cmd.Cmd):
    prompt = '> '

    def __init__(self, completekey='tab', stdin=None, stdout=None, **kwargs) -> None:
        super().__init__(completekey, stdin, stdout)

        # Display starting configuration from argparse
        logging.info("Starting Axone command line interface with the following configuration: ")
        for key, value in kwargs.items():
            logging.info(f"│ {key}: {value}")

        # Start the Axone node in a background thread
        # Note: we have to use the NodeProcess class because the command line interface use the blocking input() function
        self.node = AxoneNodeProcess(**kwargs)
        self.node.start()

    def do_clear(self, arg) -> None:
        """Clear the screen."""
        os.system("cls||clear")

    def do_exit(self, arg) -> None:
        """Exit the command line interface."""
        return

    def do_config(self, arg) -> None:
        """Display the node configuration and allow passing subarguments
        such as get and set to access the configuration."""
        args = arg.split()
        if not len(args):
            logging.info("Usage: config [get|set]")
            return

        command = args[0]

        logging.debug(f"args: {args}")
        if command == "get":
            logging.info("Node configuration:")
            logging.info(f"Name            : {self.node.name}")
            # ! Unavailable in NodeProcess
            # logging.info(f"Memory endpoint : {self.node.centralized_node.endpoint}")
            # logging.info(f"Memory size     : {self.node.centralized_node.size}")

        elif command == "set":
            logging.info("Set configuration")
        else:
            logging.info("Usage: config [get|set]")

    def do_list(self, arg) -> None:
        """List all connected nodes."""
        node_list = self.node.list_nodes()
        logging.info("Node lists:\n\t" + "\n\t".join(f"{node_id}: {node_name}" for node_id, node_name in node_list.items()))

    def complete_find(self, text, line, begidx, endidx) -> list[str]:
        return [
            node_name for node_name in self.node.list_nodes().values() if node_name is not None and node_name.startswith(text)
        ]

    def do_find(self, arg) -> None:
        """Find a node by name."""
        args = arg.split()
        if not len(args):
            logging.info("Usage: find <node_name>")
            return

        node_name = args[0]
        node = self.node.find_node_by_name(node_name)
        if node is not None:
            logging.info(f"Found node: {node_name}")
            node_config = self.node.get_node_configuration(node_name)
            if node_config is None:
                logging.error(f"Node {node_name} has no configuration. It may have been disconnected.")
                return
            logging.info("Configuration:\n\t" + "\n\t".join(f"{k}: {v}" for k, v in node_config.items()))
            logging.info(f"Services available: {self.node.is_node_advertising_services(node_name)}")
        else:
            logging.info(f"Node {node_name} not found.")

    def complete_topic(self, text, line, begidx, endidx) -> list[str]:  # -> list:
        commands = ["echo", "list", "subscribe"]  # , "unsubscribe"]
        return [command for command in commands if command.startswith(text)]

    def do_topic(self, arg) -> None:
        """Topic commands."""
        args = arg.split()
        if not len(args):
            logging.info("Usage: topic [echo|list|subscribe]")
            return

        command = args[0]

        if command == "echo":
            if len(args) > 1:
                topic_name = args[1]
                logging.debug(f"Echoing topic: {topic_name}")
                # Note: Forcing NodeProcess to use calling _listen_once() instead of listen_once_async()
                message = self.node._listen_once(topic_name)
                if message is not None:
                    logging.info(f"Received message:\n{message}")
            else:
                logging.info("Usage: topic echo <topic_name>")

        elif command == "list":
            topics = {}
            # Find all onine nodes, and get their topics
            for node_id, node_name in self.node.list_nodes().items():
                if node_name is not None:
                    published_topics = self.node.get_node_topics(node_name)
                    for topic in published_topics:
                        topics[topic] = node_name

            # Print each topic with the source node
            logging.info("Topics:")
            for topic, node_name in topics.items():
                logging.info(f"\t{topic} from {node_name}")

        elif command == "subscribe":
            if len(args) > 1:
                topic_name = args[1]
                logging.debug(f"Echoing topic: {topic_name}")
                self.node.subscribe(topic_name)
                # TODO: This would probably be better to have this somewhere else (in a separate thread maybe)
                try:
                    rate = 1
                    while True:
                        message = self.node.listen_once(topic_name)
                        if message is not None:
                            logging.info(f"Received message: {message}")
                            # Try to fetch the rate from the topic
                            rate = message.get("rate_", 1)
                            rate = 1 if rate < 0 else 1 / rate
                        time.sleep(rate)
                except KeyboardInterrupt:
                    logging.info("Exiting topic")
            else:
                logging.info("Usage: topic subscribe <topic_name>")

        else:
            logging.info("Usage: topic [echo|list|subscribe]")

    def complete_service(self, text, line, begidx, endidx) -> list[str]:  # -> list:
        commands = ["list", "call"]
        return [command for command in commands if command.startswith(text)]

    def do_service(self, arg) -> None:
        """List all services."""
        args = arg.split()
        if not len(args):
            logging.info("Usage: service [list|call]")
            return

        command = args[0]

        if command == "list":
            if len(args) > 1:
                node_name = args[1]
                services = self.node.is_node_advertising_services(node_name)
                logging.info(f"Services available on node {node_name}: {services}")
            else:
                logging.info("Usage: service list <node_name>")

        elif command == "call":
            if len(args) > 1:
                service_name = args[1]
                logging.debug(f"Calling service: {service_name}")
                response = self.node.call_service(service_name)
                logging.info(f"Response: {response}")
            else:
                logging.info("Usage: service call <service_name>")

        else:
            logging.info("Usage: service [list|call]")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='axone', description='Axone command line interface')
    parser.add_argument('-n', '--name', type=str, default='cmd_line_server', help='node name')
    parser.add_argument(
        '-e', '--centralized_memory_endpoint', type=str, default='ExampleNodeMemory', help='memory endpoint name'
    )
    parser.add_argument('-s', '--centralized_memory_size', type=int, default=4096, help='memory size')
    parser.add_argument('-f', '--config_file', type=str, default=None, help='configuration file')
    parser.add_argument('-d', '--debug', action='store_true', help='debug mode')
    args = parser.parse_args()
    kwargs = vars(args)

    setup_logger(debug=args.debug)

    cmd_line = AxoneCommandLine(**kwargs)
    try:
        cmd_line.cmdloop()
    except KeyboardInterrupt:
        print("Exiting...")
    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)
    finally:
        cmd_line.node.stop()
        print("Node stopped.")
