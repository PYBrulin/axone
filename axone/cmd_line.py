import argparse
import json
import logging
import os
import time

from axone.node import Node


class CmdLine:
    def __init__(self, **kwargs) -> None:
        self.node = Node(
            **kwargs,
        )
        self.node.start()
        self._highest_rate = 1

        self._available_commands = {
            "help": {
                "_cb": self.help,
                "_help": "Display this help message",
            },
            "clear": {
                "_cb": self.clear,
                "_help": "Clear the terminal",
            },
            "quit": {
                "_cb": self.quit,
                "_help": "Exit the program",
            },
            "config": {
                "show": {
                    "_cb": self.config_show,
                    "_help": "Display the node configuration",
                },
                "set": {
                    "_cb": self.config_set,
                    "_help": "Set the node configuration with standard arguments: [name, memory_endpoint, memory_size]",
                },
                "_help": "Node configuration management",
            },
            "memory": {
                "_cb": self.memory,
                "_help": "Display the memory content",
            },
            "watch": {
                "_cb": self.watch,
                "_help": "watch the memory content in real-time",
            },
            "rate": {
                "_cb": self.rate,
                "_help": "Display the highest rate",
            },
            "restart": {
                "_cb": self.restart,
                "_help": "Restart the node",
            },
            "node": {
                "info": {
                    "_cb": self.node_info,
                    "_help": "Display the node info",
                },
                "list": {
                    "_cb": self.node_list,
                    "_help": "Display the node list",
                },
                "_help": "Nodes management",
            },
            "topic": {
                "info": {
                    "_cb": self.topic_info,
                    "_help": "Display the topic info",
                },
                "list": {
                    "_cb": self.topic_list,
                    "_help": "Display the topic list",
                },
                "echo": {
                    "_cb": self.topic_echo,
                    "_help": "Subscribe to a topic and display its content in real time",
                },
                "_help": "Topics management",
            },
            "service": {
                "list": {
                    "_cb": self.service_list,
                    "_help": "Display the service list",
                },
                "call": {
                    "_cb": self.service_call,
                    "_help": "Call an service with arguments",
                },
                "_help": "Services management",
            },
        }

    def help(self, *args) -> None:
        args = args[0]

        # TODO: There is probably a cleaner way to do this

        # If args is provided, display help from the subcommand
        if len(args) == 1:
            if args[0] in self._available_commands:
                print("Available commands :")
                for j, subcommand in enumerate(self._available_commands[args[0]].items()):
                    if isinstance(subcommand[1], dict):
                        print(
                            (" │ " if j < len(self._available_commands[args[0]]) - 2 else " └ "),
                            end="",
                        )
                        print(f"{subcommand[0]:14s} : {subcommand[1]['_help']}")
            else:
                print(f"Unknown command '{args[0]}'")
            print("")
            return

        # Display help for all commands
        print("Available commands :")
        for i, command in enumerate(self._available_commands.items()):
            if isinstance(command[1], dict):
                print(
                    (" │ " if (i < len(self._available_commands) - 1 or len(command[1]) > 0) else " └ "),
                    end="",
                )
                print(f"{command[0]:17s} : {command[1]['_help']}")
                for j, subcommand in enumerate(command[1].items()):
                    if isinstance(subcommand[1], dict):
                        print(
                            (" │ " if (i < len(self._available_commands) - 1 or j < len(command[1]) - 2) else " └ "),
                            end="",
                        )
                        print(
                            " │ " if j < len(command[1]) - 2 else " └ ",
                            end="",
                        )
                        print(f"{subcommand[0]:14s} : {subcommand[1]['_help']}")
        print("")

    def clear(self, *args) -> None:
        os.system("cls||clear")

    def quit(self, *args) -> None:
        exit(0)

    def memory(self, *args) -> None:
        self.db = dict(self.node._memory)
        print(
            json.dumps(
                self.db,
                sort_keys=True,
                indent=4,
                separators=(", ", ": "),
            )
        )

    def rate(self, *args) -> None:
        print(f"Highest rate : {self._highest_rate}")

    def restart(self, *args) -> None:
        self.node.restart()

    def config_show(self, *args) -> None:
        print(f"Name : {self.node.name}")
        print(f"Memory endpoint : {self.node.memory_endpoint}")
        print(f"Memory size : {self.node.memory_size}")
        print(f"Memory block : {self.node._memory._memory_block}")

    def config_set(self, *args) -> None:
        args = args[0]

        if len(args) < 2:
            print("Missing arguments")
            return

        required_restart = False

        if args[0] == "name":
            if args[1] != self.node.name:
                required_restart = True
                self.node.name = args[1]
        elif args[0] == "endpoint":
            if args[1] != self.node.memory_endpoint:
                required_restart = True
                self.node.memory_endpoint = args[1]
        elif args[0] == "size":
            if args[1] != self.node.memory_size:
                required_restart = True
                self.node.memory_size = int(args[1])
        else:
            print(f"Unknown argument '{args[0]}'")
            return

        if required_restart:
            self.node.restart()

    # region Node
    def node_info(self, *args) -> None:
        args = args[0]

        if len(args) != 0:
            node = self.node._memory.get("__nds", {})[self.node.node_id]
            _nodes = self.node.find_node_by_name(args[0])
            if _nodes is None:
                print(f"Unknown node '{args[0]}'")
                return
            node = self.node._memory.get("__nds", {})[_nodes]
        else:
            print("Not enough arguments to call node info command. Usage: node info <node_name>")
            return

        for key, value in node.items():
            if isinstance(value, dict):
                print(f"{key}" + "─" * (20 - len(key) + 1) + "┐")
                for i, (subkey, subvalue) in enumerate(value.items()):
                    print(" │ " if i < len(value) - 1 else " └ ", end="")
                    print(f"{subkey:17s} : {subvalue}")
            else:
                if key.startswith("__"):
                    if key == "__t":
                        key = "Last timestamp"
                    if key == "__n":
                        key = "Node name"
                print(f"{key:20s} : {value}")

    def node_list(self, *args) -> None:
        """Display the list of nodes"""
        self.db = self.node._memory.get("__nds", {})
        if len(self.db) == 0:
            print("No nodes")
            return

        print(f"{'Nodes':^30s} │ {'Params':^10s} │ {'Services':^10s}")
        print("─" * 30 + "─┼─" + "─" * 10 + "─┼─" + "─" * 10)
        for node in self.db.keys():
            print(
                f"{self.db[node].get('__n', node):^30s}"
                + " │ "
                + (f"{len(self.db[node].get('__p', {})):^10d}" if self.db[node].get('__p', {}) else f"{'':^10s}")
                + " │ "
                + (f"{len(self.db[node].get('__s', {})):^10d}" if self.db[node].get('__s', {}) else f"{'':^10s}")
            )

    # endregion

    # region Topic

    def topic_info(self, *args) -> None:
        pass

    def topic_list(self, *args) -> None:
        """Display the list of topics"""
        # Topics are all the keys in the memory except the ones starting with "__"
        self.db = dict(self.node._memory)
        topics = [topic for topic in self.db.keys() if not topic.startswith("__") and topic != "nodes"]
        if len(topics) == 0:
            print("No topics published")
            return

        print("Topics :")
        for topic in topics:
            value = self.db[topic]
            if isinstance(value, dict):
                print(f"{topic}" + "─" * (20 - len(topic) + 1) + "┐")

                # Iterate over the subkeys sorted by keys
                for i, (subkey, subvalue) in enumerate(sorted(value.items(), key=lambda item: item[0])):
                    # Skip the rate
                    if subkey == "__r":
                        continue

                    print(
                        " │ " if i < len(value) - 1 else " └ ",
                        end="",
                    )

                    if subkey == "__t":
                        print(f"{'Last publication':17s} : ", end="")
                        print(f"{round(time.time() - subvalue, 3)} s ago", end="")
                        print(f" ({value.get('__r', -1)} Hz)")
                    elif subkey == '__s':
                        print(f"{'Publisher':17s} : {self.db['__nds'][subvalue]['__n']}")
                    else:
                        print(f"{subkey:17s} : {subvalue}")
            else:
                print(f"{topic:20s} : {value}")

    def topic_echo(self, *args) -> None:
        """Subscribe to a topic and display its content in real time"""
        args = args[0]
        if len(args) == 0:
            print("Missing topic name")
            return
        topic_name = args[0]

        if len(args) == 0:
            print("Missing topic name")
            return

        if not self.node._memory.get(topic_name, {}):
            print(f"Unknown topic '{topic_name}'")
            return

        try:
            # Implement a simple subscription to a topic
            # It does not rely on the node's subscription mechanism
            content = ""
            print("Press Ctrl+C to exit")
            while True:
                size = len(content.splitlines())
                if size > 0:
                    # Move the cursor to the beginning of the content
                    print(f"\033[{size}A", end="")
                    # Clear the remaining lines
                    print("\033[J", end="")
                    # I love ANSI escape codes :)

                topic = self.node._memory.get(topic_name, {})
                if topic:
                    content = json.dumps(
                        topic,
                        sort_keys=True,
                        indent=4,
                        separators=(", ", ": "),
                    )
                    print(content)

                    timestamp = topic.get("__timestamp", 0)
                    rate = topic.get("__r", -1)

                    # Sleep until the next message
                    if rate > 0:
                        # Try to align the subscription with the publishing rate as much as possible
                        time.sleep(
                            max(
                                0,
                                1 / float(rate) - max(0, time.time() - timestamp),
                            )
                        )
                    else:
                        # If rate is not specified, then sleep for 0.1 second
                        time.sleep(0.1)
                else:
                    print(f"Topic '{topic_name}' has been deleted")
                    break
        except KeyboardInterrupt:
            print("Interrupted")
            return

    # endregion

    # region service
    def service_list(self, *args) -> None:
        """Display the list of all registered services"""
        # services are registered within node declaration
        self.db = dict(self.node._memory.get('__nds', {}))

        # Remove all nodes in self.db that miss the 'services' key
        self.db = {k: v for k, v in self.db.items() if '__s' in v}

        # Remove all keys except the '__s' key
        self.db = {k: v['__s'] for k, v in self.db.items() if '__s' in v}

        if len(self.db) == 0:
            print("No services registered")
            return

        # Turn the values info function-like strings

        print("Registered services :")
        for key, value in self.db.items():
            if isinstance(value, dict):
                print(f"{key}")
                for i, (subkey, subvalue) in enumerate(value.items()):
                    print(" │ " if i < len(value) - 1 else " └ ", end="")
                    print(f"{subkey}({', '.join([f'{sk}: {sv}' for sk, sv in subvalue.items()])})")
            else:
                print(f"{key:20s} : {value}")

    def service_call(self, *args) -> None:
        """
        This method all passing a destination_node, a service_name and a dictionnary to call a service.
        Note that this node does not allow to receive answers from the service.

        Call to this function should be done as follow:
        service call destination_node service_name={key1:value1, key2:value2, key3:value3}
        """

        # Get the arguments
        args = args[0]
        print(args)

        # Check if the arguments are correct
        if len(args) == 0:
            print("Missing arguments")
            return

        # Get the destination node
        destination_node = args[0]
        destination_node_id = self.node.find_node_by_name(destination_node)
        if destination_node_id is None:
            print(f"Unknown node '{args[0]}'")
            return
        destination_node = self.node._memory.get("__nds", {})[destination_node_id]

        # Get the service name and arguments
        service_name, service_args = args[1].split("=", 1)
        print(f"Calling service '{service_name}' on node '{destination_node}' with arguments '{service_args}'")

        # Check if the service has been advertised by the destination node
        if service_name not in destination_node.get("__s", {}):
            print(
                f"Service '{service_name}' is not registered on node '{destination_node}'. " + "But it will be called anyway."
            )

        # Call the service
        self.node.call_service(
            dest_node_id=destination_node_id,
            service=service_name,
            **json.loads(service_args),
        )

    # endregion

    def watch(self, *args) -> None:
        """Watch the memory content in real-time"""
        print("Press Ctrl+C to exit")
        try:
            # Implement a simple subscription to a topic
            # It does not rely on the node's subscription mechanism
            content = ""
            while True:
                size = len(content.splitlines())
                if size > 0:
                    # Move the cursor to the beginning of the content
                    print(f"\033[{size}A", end="")
                    # Clear the remaining lines
                    print("\033[J", end="")
                    # I love ANSI escape codes :)

                self.db = dict(self.node._memory)
                if self.db:
                    content = json.dumps(
                        self.db,
                        sort_keys=True,
                        indent=4,
                        separators=(", ", ": "),
                    )
                    print(content)

                    self._highest_rate = 1
                    for topic in self.db.keys():
                        if isinstance(self.db[topic], dict):
                            rate = self.db[topic].get("__r", 0)
                            if rate > self._highest_rate:
                                self._highest_rate = rate

                    # Sleep until the next message
                    time.sleep(min(1, 1 / float(self._highest_rate)))
                else:
                    break
        except KeyboardInterrupt:
            print("Interrupted")
            return
        # except Exception as e:
        #     print(e)
        #     return

    def main(self) -> None:
        try:
            while True:
                # Read the memory content
                self.db = dict(self.node._memory)

                self._highest_rate = 1
                for topic in self.db.keys():
                    if isinstance(self.db[topic], dict):
                        rate = self.db[topic].get("__r", 0)
                        if rate > self._highest_rate:
                            self._highest_rate = rate

                # Input command
                command = input(f"(axone:{self.node.name})> ")

                # Parse command
                command = command.rstrip().split(" ")
                if len(command) == 0:
                    continue

                # Execute command
                if command[0] in self._available_commands:
                    if "_cb" in self._available_commands[command[0]]:
                        self._available_commands[command[0]]["_cb"](command[1:])
                    elif len(command) >= 2:
                        if command[1] in self._available_commands[command[0]]:
                            self._available_commands[command[0]][command[1]]["_cb"](command[2:])
                        else:
                            print(f"Unknown subcommand '{command[1]}' for command '{command[0]}'")
                    else:
                        # Provide help for the specified command
                        self.help([command[0]])
                else:
                    print(f"Unknown command '{command[0]}'")

        except KeyboardInterrupt:
            print("Exiting...")
            exit(0)
        finally:
            self.node._memory.shm.close()
            del self.node


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='axone',
        description='Axone command line interface',
    )
    parser.add_argument(
        '-n',
        '--name',
        type=str,
        default='cmd_line_server',
        help='node name',
    )
    parser.add_argument(
        '-e',
        '--memory_endpoint',
        type=str,
        default='ExampleNodeMemory',
        help='memory endpoint name',
    )
    parser.add_argument(
        '-s',
        '--memory_size',
        type=int,
        default=4096,
        help='memory size',
    )
    parser.add_argument(
        '-f',
        '--config_file',
        type=str,
        default=None,
        help='configuration file',
    )
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help='debug mode',
    )
    args = parser.parse_args()
    kwargs = vars(args)

    logging.basicConfig(
        level=logging.DEBUG if kwargs['debug'] else logging.INFO,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    CmdLine(**kwargs).main()
