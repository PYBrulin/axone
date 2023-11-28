import argparse
import json
import os
import time

from axone.node import Node


class CmdLine:
    def __init__(self, **kwargs) -> None:
        self.node = Node(
            name=kwargs.get('name', 'cmd_line_server'),
            memory_endpoint=kwargs.get('memory_endpoint', 'ExampleNodeMemory'),
            memory_size=kwargs.get('memory_size', 4096),
        )
        self._highest_rate = 1

        self._available_commands = {
            "help": {"_cb": self.help, "_help": "Display this help message"},
            "clear": {"_cb": self.clear, "_help": "Clear the terminal"},
            "quit": {"_cb": self.quit, "_help": "Exit the program"},
            "memory": {
                "_cb": self.memory,
                "_help": "Display the memory content",
            },
            "rate": {"_cb": self.rate, "_help": "Display the highest rate"},
            "restart": {"_cb": self.restart, "_help": "Restart the node"},
            "config": {
                "_cb": self.config,
                "_help": "Display the node configuration",
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
        }

    def help(self, *args) -> None:
        args = args[0]

        # If args is provided, display help from the subcommand
        if len(args) == 1:
            if args[0] in self._available_commands:
                print("Available commands :")
                for subcommand in self._available_commands[args[0]].items():
                    if isinstance(subcommand[1], dict):
                        print(
                            f"  {args[0]} {subcommand[0]} : {subcommand[1]['_help']}"
                        )
            else:
                print(f"Unknown command '{args[0]}'")
            print("")
            return

        # Display help for all commands
        print("Available commands :")
        for i, command in enumerate(self._available_commands.items()):
            if isinstance(command[1], dict):
                print(
                    " │ "
                    if (
                        i < len(self._available_commands) - 1
                        or len(command[1]) > 0
                    )
                    else " └ ",
                    end="",
                )
                print(f"{command[0]:17s} : {command[1]['_help']}")
                for j, subcommand in enumerate(command[1].items()):
                    if isinstance(subcommand[1], dict):
                        print(
                            " │ "
                            if (
                                i < len(self._available_commands) - 1
                                or j < len(command[1]) - 2
                            )
                            else " └ ",
                            end="",
                        )
                        print(
                            " │ " if j < len(command[1]) - 2 else " └ ",
                            end="",
                        )
                        print(
                            f"{subcommand[0]:14s} : {subcommand[1]['_help']}"
                        )
        print("")

    def clear(self, *args) -> None:
        os.system("cls||clear")

    def quit(self, *args) -> None:
        exit(0)

    def memory(self, *args) -> None:
        self.db = self.node._memory._read_memory()
        print(
            json.dumps(
                self.db,
                sort_keys=True,
                indent=4,
            )
        )

    def rate(self, *args) -> None:
        print(f"Highest rate : {self._highest_rate}")

    def restart(self, *args) -> None:
        self.node._memory.shm.close()
        self.node._memory.shm.unlink()

        self.node = Node(
            name=self.node.name,
            memory_endpoint=self.node.memory_endpoint,
            memory_size=self.node.memory_size,
        )

    def config(self, *args) -> None:
        print(f"Name : {self.node.name}")
        print(f"Memory endpoint : {self.node.memory_endpoint}")
        print(f"Memory size : {self.node.memory_size}")

    # region Node
    def node_info(self, *args) -> None:
        args = args[0]

        if len(args) == 0:
            node = self.node._memory.get("__nodes", {})[self.node.name]
        elif args[0] in self.node._memory.get("__nodes", {}):
            node = self.node._memory.get("__nodes", {})[args[0]]
        else:
            print(f"Unknown node '{args[0]}'")
            return

        for key, value in node.items():
            if isinstance(value, dict):
                print(f"{key}" + "─" * (20 - len(key) + 1) + "┐")
                for i, (subkey, subvalue) in enumerate(value.items()):
                    print(" │ " if i < len(value) - 1 else " └ ", end="")
                    print(f"{subkey:17s} : {subvalue}")
            else:
                print(f"{key:20s} : {value}")

    def node_list(self, *args) -> None:
        """Display the list of nodes"""
        self.db = self.node._memory.get("__nodes", {})
        if len(self.db) == 0:
            print("No nodes")
            return

        print("Nodes :")
        for node in self.db.keys():
            print(f"  {node}")

    # endregion
    # region Topic

    def topic_info(self, *args) -> None:
        pass

    def topic_list(self, *args) -> None:
        """Display the list of topics"""
        # Topics are all the keys in the memory except the ones starting with "__"
        self.db = self.node._memory._read_memory()
        topics = [
            topic
            for topic in self.db.keys()
            if not topic.startswith("__") and topic != "nodes"
        ]
        if len(topics) == 0:
            print("No topics published")
            return

        print("Topics :")
        for topic in topics:
            value = self.db[topic]
            if isinstance(value, dict):
                print(f"{topic}" + "─" * (20 - len(topic) + 1) + "┐")

                # Iterate over the subkeys sorted by keys
                for i, (subkey, subvalue) in enumerate(
                    sorted(value.items(), key=lambda item: item[0])
                ):
                    # Skip the rate
                    if subkey == "__rate":
                        continue

                    print(
                        " │ " if i < len(value) - 1 else " └ ",
                        end="",
                    )

                    if subkey == "__timestamp":
                        print(f"{'Last publication':17s} : ", end="")
                        print(
                            f"{round(time.time() - subvalue, 3)} s ago", end=""
                        )
                        print(f"({value.get('__rate', -1)} Hz)")
                    elif subkey == '__source':
                        print(f"{'Publisher':17s} : {subvalue}")
                    else:
                        print(f"{subkey:17s} : {subvalue}")
            else:
                print(f"{topic:20s} : {value}")

    def topic_echo(self, *args) -> None:
        """Subscribe to a topic and display its content in real time"""
        topic_name = args[0]

        if len(args) == 0:
            print("Missing topic name")
            return

        if topic_name not in self.node._memory._read_memory():
            print(f"Unknown topic '{topic_name}'")
            return

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

                topic = self.node._memory.get(topic_name, {})
                if topic:
                    content = json.dumps(
                        topic,
                        sort_keys=True,
                        indent=4,
                    )
                    print(content)

                    timestamp = topic.get("__timestamp", 0)
                    rate = topic.get("__rate", -1)

                    # Sleep until the next message
                    if rate > 0:
                        # Try to align the subscription with the publishing rate as much as possible
                        time.sleep(
                            max(
                                0,
                                1 / float(rate)
                                - max(0, time.time() - timestamp),
                            )
                        )
                    else:
                        # If rate is not specified, then sleep for 0.1 second
                        time.sleep(0.1)
                else:
                    print(f"Topic '{topic_name}' has been deleted")
                    break
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            return

    # endregion

    def main(self) -> None:
        try:
            while True:
                # Read the memory content
                self.db = self.node._memory._read_memory()

                self._highest_rate = 1
                for topic in self.db.keys():
                    if isinstance(self.db[topic], dict):
                        rate = self.db[topic].get("__rate", 0)
                        if rate > self._highest_rate:
                            self._highest_rate = rate

                # Input command
                command = input(f"({self.node.name})> ")

                # Parse command
                command = command.split(" ")
                if len(command) == 0:
                    continue

                # Execute command
                if command[0] in self._available_commands:
                    if len(command) == 1:
                        if "_cb" in self._available_commands[command[0]]:
                            self._available_commands[command[0]]["_cb"](
                                command[1:]
                            )
                        else:
                            # Provide help for the specified command
                            self.help([command[0]])

                    elif len(command) >= 2:
                        if command[1] in self._available_commands[command[0]]:
                            self._available_commands[command[0]][command[1]][
                                "_cb"
                            ](command[2:])
                        else:
                            print(
                                f"Unknown subcommand '{command[1]}' for command '{command[0]}'"
                            )
                    # else:
                    #     print(f"Too many arguments for command '{command[0]}'")
                else:
                    print(f"Unknown command '{command[0]}'")

        except KeyboardInterrupt:
            print("KeyboardInterrupt")
            exit(0)
        finally:
            self.node._memory.shm.close()
            self.node._memory.shm.unlink()  # Call unlink only once to release the shared memory
            del self.node


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--name', type=str, default='cmd_line_server', help='node name'
    )
    parser.add_argument(
        '--memory_endpoint',
        type=str,
        default='ExampleNodeMemory',
        help='memory endpoint name',
    )
    parser.add_argument(
        '--memory_size', type=int, default=4096, help='memory size'
    )
    args = parser.parse_args()
    kwargs = vars(args)

    CmdLine(**kwargs).main()
