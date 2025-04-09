import inspect
import logging
import struct
import time
from typing import Any, Iterator, Optional

from axone.utils import timeit_if_debug

BYTES_PER_INT = struct.calcsize('i')  # TODO: Change to numpy dtypes


def call_value(value, instance=None) -> Any:
    if callable(value):
        if inspect.isbuiltin(value):
            # Handle built-in functions here
            result = value()
        else:
            try:
                sig = inspect.signature(value)
                if len(sig.parameters) == 0:
                    result = value()
                elif instance and len(sig.parameters) == 1:
                    # If the callable is an instance method, call it with the instance as the first argument
                    result = value(instance)
                else:
                    # logging.error(f"Callable {value} has parameters {sig.parameters}")
                    result = None
            except ValueError:
                logging.error(f"Cannot get signature of function {value}")
                result = None
    else:
        result = value
    return result


def standard_data_encoding(*args, **kwargs) -> bytes:
    # Create temp arguments keys for args
    for i, arg in enumerate(args):
        kwargs[f"_arg_{i}"] = arg

    # Number of attributes
    logging.debug(f"Encoding {len(kwargs)} attributes")

    output = struct.pack('I', len(kwargs))

    for key, value in kwargs.items():
        # Attribute name
        key_bytes = key.encode("utf-8")
        key_len = len(key_bytes)
        if key_len > 127:
            raise ValueError("Attribute name too long")
        # Use the "native size" format to encode the string length since it is variable
        output += f'n{key_len}s'.encode()
        output += key_bytes
        logging.debug(f"Encoding attribute name {key} of length {key_len}")

        # Attribute type
        if value is None:
            output += b'x'
            output += struct.pack('!x')
            logging.debug(f"Encoding empty attribute {key}")

        elif isinstance(value, bool):
            output += b'?'
            output += struct.pack('?', value)
            logging.debug(f"Encoding boolean {key} of value {value}")

        elif isinstance(value, int):
            output += b'i'
            output += struct.pack('i', value)
            logging.debug(f"Encoding int {key} of value {value}")

        elif isinstance(value, float):
            # TODO: Should we check between 'float' and 'double' to optimize the size?
            output += b'd'
            output += struct.pack('d', value)
            logging.debug(f"Encoding double {key} of value {value}")

        elif isinstance(value, str):
            value_bytes = value.encode("utf-8")
            value_len = len(value_bytes)
            if value_len > 127:
                raise ValueError(f"Attribute value too long for key-value pair\n\t{key}:`{value}`")
            # Use the "native size" format to encode the string length since it is variable
            output += f'n{value_len}s'.encode()
            output += value_bytes
            logging.debug(f"Encoding string {value} of length {value_len}")

        elif isinstance(value, list):
            output += b'l'
            output += struct.pack('I', len(value))
            logging.debug(f"Encoding list {key} of length {len(value)}")
            for item in value:
                if isinstance(item, bool):
                    output += b'?'
                    output += struct.pack('?', item)
                    logging.debug(f"Encoding boolean list item of value {item}")

                elif isinstance(item, int):
                    output += b'i'
                    output += struct.pack('i', item)
                    logging.debug(f"Encoding int list item of value {item}")

                elif isinstance(item, float):
                    output += b'd'
                    output += struct.pack('d', item)
                    logging.debug(f"Encoding double list item of value {item}")

                elif isinstance(item, str):
                    item_bytes = item.encode("utf-8")
                    item_len = len(item_bytes)
                    if item_len > 127:
                        raise ValueError(f"List item value too long for key-value pair\n\t{key}:`{item}`")
                    output += f'n{item_len}s'.encode()
                    output += item_bytes
                    logging.debug(f"Encoding string list item {item} of length {item_len}")

                else:
                    raise ValueError(f"Unknown list item type {type(item)} for key-value pair\n\t{key}:'{item}'")

        # ! AxoneStructs are not supported here
        # elif isinstance(value, AxoneStruct):
        #     output += b"A"
        #     encoded_struct = value.encode()
        #     output += struct.pack('i', len(encoded_struct))
        #     output += encoded_struct

        else:
            raise ValueError(f"Unknown attribute type {type(value)} for key-value pair\n\t{key}:'{value}'")

    return output


def standard_data_decoding(data) -> dict:
    # Create an iterator from the data
    data_iter = iter(data)

    # Number of attributes
    num_attrs = struct.unpack('I', bytes(next(data_iter) for _ in range(struct.calcsize('i'))))[0]

    out = {}

    for _ in range(num_attrs):

        # Get the attribute name first
        # Attribute name
        # Ensure the next character is a 'n' to indicate the length of the attribute name
        if next(data_iter) != ord('n'):
            raise ValueError("Attribute name should start with 'n'")
        # Get the next characters until a 's' is found
        key_len = ""
        while True:
            _charac = chr(next(data_iter))
            key_len += _charac
            if _charac.isalpha():
                break
        key_len = int(key_len[:-1])
        key = bytes(next(data_iter) for _ in range(key_len)).decode("utf-8")
        logging.debug(f"Decoding attribute {key}")

        # Get next byte to determine the type of the attribute
        attr_type = chr(next(data_iter))
        logging.debug(f"Attribute type {attr_type}")

        if attr_type == 'n':  # if "native size"
            # Get the next characters until a 's' or any alphabetical character is found
            value_len = ""
            while True:
                _charac = chr(next(data_iter))
                value_len += _charac
                if _charac.isalpha():
                    break
            value_len = int(value_len[:-1])
            value = bytes(next(data_iter) for _ in range(value_len)).decode("utf-8")

        elif attr_type == 'l':  # List type
            list_len = struct.unpack('I', bytes(next(data_iter) for _ in range(struct.calcsize('I'))))[0]
            value = []
            for _ in range(list_len):
                item_type = chr(next(data_iter))
                if item_type == '?':
                    item = struct.unpack('?', bytes(next(data_iter) for _ in range(struct.calcsize('?'))))[0]
                elif item_type == 'i':
                    item = struct.unpack('i', bytes(next(data_iter) for _ in range(struct.calcsize('i'))))[0]
                elif item_type == 'd':
                    item = struct.unpack('d', bytes(next(data_iter) for _ in range(struct.calcsize('d'))))[0]
                elif item_type == 'n':
                    item_len = ""
                    while True:
                        _charac = chr(next(data_iter))
                        item_len += _charac
                        if _charac.isalpha():
                            break
                    item_len = int(item_len[:-1])
                    item = bytes(next(data_iter) for _ in range(item_len)).decode("utf-8")
                else:
                    raise ValueError(f"Unknown list item type {item_type}")
                value.append(item)

        # ! AxoneStructs are not supported here
        # elif attr_type == 'A':
        #     value = AxoneStruct()
        #     value_len = struct.unpack('i', bytes(next(data_iter) for _ in range(struct.calcsize('i'))))[0]
        #     value.decode(bytes(next(data_iter) for _ in range(value_len)))

        else:  # Let struct handle the rest
            decoded = struct.unpack(attr_type, bytes(next(data_iter) for _ in range(struct.calcsize(attr_type))))
            value = decoded[0] if len(decoded) == 1 else None  # Note: When value is None, the length of decoded is 0

        logging.debug(f"Setting attribute {key} to {value if not attr_type == 'A' else type(value)}")
        out[key] = value

    return out


class AxoneStruct:

    # Not the best way to do this, but it works for now
    __blacklist_methods__ = ["encode", "decode", "update", "get_approximate_size", "list_instance_attributes", "get"]

    # Create a logger for this class
    __logger__ = logging.getLogger("AxoneStruct")
    __logger__.setLevel(logging.WARNING)

    def __init__(self) -> None:
        pass

    def __str__(self) -> str:
        out = self.__class__.__name__
        for key, value in self.__attributes__.items():
            if not key.startswith("_"):
                if isinstance(value, AxoneStruct):
                    out += f"\n │ {key} {type(value)} {value.__class__.__name__}"
                    out += "\n │ ".join([s for s in str(value).split("\n")])
                else:
                    out += f"\n │ {key} {type(value)} {value if not callable(value) else call_value(value, self)}"
        return out

    def list_instance_attributes(self, instance=None):
        out = {}
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                if not callable(value):
                    out[key] = value
                elif key not in self.__blacklist_methods__:
                    out[key] = call_value(value, self if instance is None else instance)
        return out

    @property
    def __attributes__(self):
        attrs = self.list_instance_attributes()

        # Start from the base classes
        base_instance = self.__class__
        if hasattr(base_instance, 'list_instance_attributes'):
            base_attrs = base_instance.list_instance_attributes(base_instance)
            base_attrs.update(attrs)
            return base_attrs
        else:
            return self.list_instance_attributes()

    def __len__(self) -> int:
        return len(self.__attributes__.items())

    def __delitem__(self, key: str) -> None:
        if key in self.__class__.__dict__:
            delattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.__attributes__)

    def __reversed__(self) -> Iterator[str]:
        return reversed(self.__attributes__)

    def __contains__(self, key: str) -> bool:
        return key in self.__attributes__

    def __eq__(self, other: Any) -> bool:
        """Check if the object is equal to another object based on its attributes"""
        return self.__attributes__ == other

    def __ne__(self, other: Any) -> bool:
        """Check if the object is not equal to another object based on its attributes"""
        return self.__attributes__ != other

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            return default

    def update(self, other: Any) -> None:
        for key, value in other.items():
            setattr(self, key, value)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.__attributes__:
            self.__dict__[key] = value
        else:
            raise AttributeError(
                f"Attribute '{key}' not found in class '{self.__class__.__name__}'. You should not add new attributes to the "
                + "class at runtime otherwise the size of the message might overflow the shared memory block that has been "
                + "allocated for it."
            )

    def get_approximate_size(self) -> int:
        """Get the approximate size of the encoded message.

        Do the same encoding as in the encode method, but instead of actually
        encoding the data, just return the size of the output and set a high value for string mostly
        """

        # Number of attributes
        approx_size = 2

        for key, value in self.__attributes__.items():

            # Attribute name
            key_bytes = key.encode("utf-8")
            key_len = len(key_bytes)
            approx_size += key_len + 1

            # Attribute type
            if isinstance(value, bool):
                approx_size += 1 + struct.calcsize('b')
            elif isinstance(value, int):
                approx_size += 1 + struct.calcsize('i')
            elif isinstance(value, float):
                approx_size += 1 + struct.calcsize('d')
            elif isinstance(value, str):
                approx_size += 5 + 127  # Allow for a string of 127 characters max
            elif isinstance(value, list):
                # lists are tricky, we need to encode the length of the list and then the length of each element
                approx_size += 1 + 4  # 1 for the type, 4 for the length of the list
                for v in value:
                    if isinstance(v, AxoneStruct):
                        approx_size += v.get_approximate_size()
                    else:
                        approx_size += 4 + len(str(v))  # 4 for the length of the string, len(str(v)) for the string itself
            elif isinstance(value, AxoneStruct):
                approx_size += 1 + value.get_approximate_size()
            else:
                raise ValueError(f"Unknown attribute type {type(value)} for key-value pair\n\t{key}:`{value}`")

        return approx_size

    @timeit_if_debug
    def encode(self) -> bytes:
        """Encode all class attributes as bytes of minimum size

        Output binary should follow the following format:
        - __BYTES_PER_INT__ bytes: number of attributes
        - The __BYTES_PER_INT__ bytes used to encode the number of attributes should
          be the minimum number of bytes required to encode the number of
          attributes (TODO)

        - for each attribute:
            - 1 byte: type of the attribute (0: boolean, 1: int, 2: long, 3: string)
            - __BYTES_PER_INT__ bytes: length of the attribute name
            - n bytes: attribute name
            if type is boolean:
            - 1 byte: 0 if False, 1 if True
            if type is int, float or string:
            - __BYTES_PER_INT__ bytes: length of the attribute value
            - n bytes: attribute value
        """

        # Number of attributes
        self.__logger__.debug(f"Encoding {len(self)} attributes")

        output = struct.pack('I', len(self.__attributes__))

        for key, value in self.__attributes__.items():
            # Attribute name
            key_bytes = key.encode("utf-8")
            key_len = len(key_bytes)
            if key_len > 127:
                raise ValueError("Attribute name too long")
            # Use the "native size" format to encode the string length since it is variable
            output += f'n{key_len}s'.encode()
            output += key_bytes
            self.__logger__.debug(f"Encoding attribute name {key} of length {key_len}")

            # Attribute type
            if value is None:
                output += b'x'
                output += struct.pack('!x')
                self.__logger__.debug(f"Encoding empty attribute {key}")

            elif isinstance(value, bool):
                output += b'?'
                output += struct.pack('?', value)
                self.__logger__.debug(f"Encoding boolean {key} of value {value}")

            elif isinstance(value, int):
                output += b'i'
                output += struct.pack('i', value)
                self.__logger__.debug(f"Encoding int {key} of value {value}")

            elif isinstance(value, float):
                # TODO: Should we check between 'float' and 'double' to optimize the size?
                output += b'd'
                output += struct.pack('d', value)
                self.__logger__.debug(f"Encoding double {key} of value {value}")

            elif isinstance(value, str):
                value_bytes = value.encode("utf-8")
                value_len = len(value_bytes)
                if value_len > 127:
                    raise ValueError(f"Attribute value too long for key-value pair\n\t{key}:`{value}`")
                # Use the "native size" format to encode the string length since it is variable
                output += f'n{value_len}s'.encode()
                output += value_bytes
                self.__logger__.debug(f"Encoding string {value} of length {value_len}")

            elif isinstance(value, list):
                output += b'l'
                output += struct.pack('I', len(value))
                self.__logger__.debug(f"Encoding list {key} of length {len(value)}")
                for item in value:
                    if isinstance(item, bool):
                        output += b'?'
                        output += struct.pack('?', item)
                        self.__logger__.debug(f"Encoding boolean list item of value {item}")

                    elif isinstance(item, int):
                        output += b'i'
                        output += struct.pack('i', item)
                        self.__logger__.debug(f"Encoding int list item of value {item}")

                    elif isinstance(item, float):
                        output += b'd'
                        output += struct.pack('d', item)
                        self.__logger__.debug(f"Encoding double list item of value {item}")

                    elif isinstance(item, str):
                        item_bytes = item.encode("utf-8")
                        item_len = len(item_bytes)
                        if item_len > 127:
                            raise ValueError(f"List item value too long for key-value pair\n\t{key}:`{item}`")
                        # output += struct.pack(f'n{item_len}s', item_bytes)
                        output += f'n{item_len}s'.encode()
                        output += item_bytes
                        self.__logger__.debug(f"Encoding string list item {item} of length {item_len}")

                    else:
                        raise ValueError(f"Unknown list item type {type(item)} for key-value pair\n\t{key}:'{item}'")

            elif isinstance(value, AxoneStruct):
                output += b"A"
                encoded_struct = value.encode()
                output += struct.pack('i', len(encoded_struct))
                output += encoded_struct

            else:
                raise ValueError(f"Unknown attribute type {type(value)} for key-value pair\n\t{key}:'{value}'")

        return output

    @timeit_if_debug
    def decode(self, data) -> None:
        """Decode binary data and set attributes accordingly"""

        # Display data size
        self.__logger__.debug(f"Decoding {len(data)} bytes")

        # Create an iterator from the data
        data_iter = iter(data)

        # Number of attributes
        num_attrs = struct.unpack('I', bytes(next(data_iter) for _ in range(struct.calcsize('i'))))[0]

        for _ in range(num_attrs):

            # Get the attribute name first
            # Attribute name
            # Ensure the next character is a 'n' to indicate the length of the attribute name
            if next(data_iter) != ord('n'):
                raise ValueError("Attribute name should start with 'n'")
            # Get the next characters until a 's' is found
            key_len = ""
            while True:
                _charac = chr(next(data_iter))
                key_len += _charac
                if _charac.isalpha():
                    break
            key_len = int(key_len[:-1])
            key = bytes(next(data_iter) for _ in range(key_len)).decode("utf-8")
            self.__logger__.debug(f"Decoding attribute {key}")

            # Get next byte to determine the type of the attribute
            attr_type = chr(next(data_iter))
            self.__logger__.debug(f"Attribute type {attr_type}")

            if attr_type == 'n':  # if "native size"
                # Get the next characters until a 's' or any alphabetical character is found
                value_len = ""
                while True:
                    _charac = chr(next(data_iter))
                    value_len += _charac
                    if _charac.isalpha():
                        break
                value_len = int(value_len[:-1])
                value = bytes(next(data_iter) for _ in range(value_len)).decode("utf-8")

            elif attr_type == 'l':
                list_len = struct.unpack('I', bytes(next(data_iter) for _ in range(struct.calcsize('I'))))[0]
                value = []
                for _ in range(list_len):
                    item_type = chr(next(data_iter))
                    if item_type == '?':
                        item = struct.unpack('?', bytes(next(data_iter) for _ in range(struct.calcsize('?'))))[0]
                    elif item_type == 'i':
                        item = struct.unpack('i', bytes(next(data_iter) for _ in range(struct.calcsize('i'))))[0]
                    elif item_type == 'd':
                        item = struct.unpack('d', bytes(next(data_iter) for _ in range(struct.calcsize('d'))))[0]
                    elif item_type == 'n':
                        item_len = ""
                        while True:
                            _charac = chr(next(data_iter))
                            item_len += _charac
                            if _charac.isalpha():
                                break
                        item_len = int(item_len[:-1])
                        item = bytes(next(data_iter) for _ in range(item_len)).decode("utf-8")
                    else:
                        raise ValueError(f"Unknown list item type {item_type}")
                    value.append(item)

            elif attr_type == 'A':
                value = AxoneStruct()
                value_len = struct.unpack('i', bytes(next(data_iter) for _ in range(struct.calcsize('i'))))[0]
                value.decode(bytes(next(data_iter) for _ in range(value_len)))

            else:  # Let struct handle the rest
                decoded = struct.unpack(attr_type, bytes(next(data_iter) for _ in range(struct.calcsize(attr_type))))
                value = decoded[0] if len(decoded) == 1 else None  # Note: When value is None, the length of decoded is 0

            self.__logger__.debug(f"Setting attribute {key} to {value if not attr_type == 'A' else type(value)}")
            setattr(self, key, value)


# Standard Axone messages


class AxoneTopic(AxoneStruct):
    source_: str = ""  # source
    timestamp_: float = 0.0  # timestamp
    rate_: float = -1.0  # rate


class AxoneService(AxoneStruct):
    class AxoneRequest(AxoneStruct):
        source_: str = ""  # source
        timestamp_: float = 0.0  # timestamp
        counter_: int = 0  # counter

    class AxoneAnswer(AxoneStruct):
        error_: bool = False  # error
        timestamp_: float = 0.0  # timestamp
        counter_: int = -1  # counter

    source_: str = ""  # source
    request: AxoneStruct = None  # request
    response: AxoneStruct = None  # response


if __name__ == "__main__":
    # Several examples of how to use the AxoneStruct class

    from axone.custom_logger import setup_logger

    setup_logger(debug=True)

    class SubMessage(AxoneStruct):
        x: int = 0
        y: float = 1.2
        z: str = "34"

    class ATopicPassedToAxone(AxoneTopic):
        a: bool = True
        b: int = 0
        c: int = 1
        d: int = 2
        e: float = 1.23456789
        f: float = 1e9
        g: float = 0.00001357
        h: str = "hello"
        time: float = time.time  # a callable that will be called when the attribute is accessed
        list_of_random_types: list[Any] = [1, 2.0, "hello", True]

        xyz: SubMessage = SubMessage()

        an_decently_long_attribute_name: str = "world"
        # an_overly_long_attribute_name_that_should_raise_an_error_if_attempted_to_be_encoded_but_yeah_let_s_try_it_anyway_gosh_this_is_longer_than_i_expected_what_a_long_name_i_must_be_crazy_to_have_thought_of_this: (  # noqa: E501
        #     str
        # ) = "!"

        a_callable: callable = lambda x: 1 + 1

        def _update_message(self) -> None:
            return f"Hello message_callback from topic_published_rate_func {2 * time.time()}"

        message_callback: str = _update_message

        # def print_within(self, input_string) -> None:
        #     print(input_string)

    class AServicePassedToAxone(AxoneService):
        _requester: str = "source"  # The node making the request
        # The request with possible arguments defined by the node advertizing the service
        request: ATopicPassedToAxone = ATopicPassedToAxone()
        # The answer to the request
        response: ATopicPassedToAxone = SubMessage()

    # Topic
    topic = ATopicPassedToAxone()
    print("str(topic)", str(topic))

    print("topic.__attributes__")
    print(topic.__attributes__)

    print(topic.get_approximate_size())

    with open("topic.bin", "wb") as f:
        print("topic.encode()")
        out = topic.encode()
        print(out)
        print(len(out))
        f.write(out)

    # print out in hexadecimal string
    print(" ".join(f"{c:02x}" for c in out))

    with open("topic.bin", "rb") as f:
        print("topic.decode()")
        out = f.read()
        topic2 = AxoneStruct()  # The base message class
        topic2.decode(out)  # A subclass of the base message class that inherits the attribute of ATopicPassedToAxone
        print("str(topic2)", str(topic2))
        print("xyz", type(topic2.xyz), str(topic2.xyz))
        print("xyz.x", type(topic2.xyz.x), topic2.xyz.x)
        print("h", type(topic2.h), topic2.h)

    # # Service
    # print("\nServices")

    # service = AServicePassedToAxone()

    # with open("service.bin", "wb") as f:
    #     print("service.encode()")
    #     out = service.encode()
    #     f.write(out)

    # # print out in hexadecimal string
    # print(" ".join(f"{c:02x}" for c in out))

    # with open("service.bin", "rb") as f:
    #     print("service.decode()")
    #     out = f.read()
    #     print(out)
    #     service2 = AxoneStruct()  # The base message class
    #     service2.decode(out)  # A subclass of the base message class that inherits the attribute of ATopicPassedToAxone

    #     print("Request", str(service2.request))
    #     print("Response", str(service2.response))
