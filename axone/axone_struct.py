import inspect
import logging
import struct
import time
from enum import Enum
from typing import Any, Iterator, Optional


def timeit_if_debug(func):
    def wrapper(*args, **kwargs):
        if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            logging.debug(f"{func.__name__} execution time: {end_time - start_time} seconds")
            return result
        else:
            return func(*args, **kwargs)

    return wrapper


class TypeSize(Enum):
    BOOLEAN = 0
    INT = 1
    DOUBLE = 2
    STRING = 3
    LIST = 4
    AXONESTRUCT = 10


BYTES_PER_INT = struct.calcsize('i')  # TODO: Change to numpy dtypes


def call_value(value, instance=None):
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


class AxoneStruct:

    # Not the best way to do this, but it works for now
    __blacklist_methods__ = ["encode", "decode", "update", "get_approximate_size", "list_instance_attributes", "get"]

    def __init__(self) -> None:
        pass

    # def list_all_attrs(self) -> None:
    #     print(self.__class__.__name__)
    #     print("> Instance attributes:")
    #     for key, value in self.__dict__.items():
    #         if not key.startswith("_") and not callable(value):
    #             print(" |", key, type(value), value)  # if not callable(value) else call_value(value, self))
    #     print("> Class attributes:")
    #     for key, value in self.__class__.__dict__.items():
    #         if not key.startswith("_"):
    #             print(" |", key, type(value), value if not callable(value) else call_value(value, self))
    #     print("> Method Resolution Order:")
    #     for cls in self.__class__.mro()[1:]:
    #         subattrs = [key for key in cls.__dict__.keys() if not key.startswith("_")]
    #         if subattrs:
    #             print(" |", cls.__name__, subattrs)

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

    # @property
    # def __attributes__(self) -> str:
    #     instance_attrs = {
    #         key: value if not callable(value) else call_value(value, self)
    #         for key, value in self.__dict__.items()
    #         if not key.startswith("_")
    #     }
    #     class_attrs = {
    #         key: value if not callable(value) else call_value(value, self)
    #         for key, value in self.__class__.__dict__.items()
    #         if not key.startswith("_")
    #     }
    #     mro_attrs = {
    #         key: value if not callable(value) else call_value(value, self)
    #         for cls in self.__class__.mro()[1:]
    #         for key, value in cls.__dict__.items()
    #         if not key.startswith("_")
    #     }
    #     attrs = {
    #         **mro_attrs,
    #         **class_attrs,
    #         **instance_attrs,
    #     }

    #     # Remove all value that have None
    #     return {key: value for key, value in attrs.items() if value is not None}

    # @property
    # def __attributes__(self) -> str:
    #     attrs = {}

    #     # Start from the base classes
    #     for cls in reversed(self.__class__.mro()):
    #         print([key for key in self.__dict__.keys()])
    #         cls_attrs = {
    #             key: value  # if not callable(value) else call_value(value, self)
    #             for key, value in cls.__dict__.items()
    #             if not key.startswith("_") and key not in attrs and not callable(value)
    #         }
    #         attrs.update(cls_attrs)

    #     # Then add the instance attributes
    #     print([key for key in self.__dict__.keys()])
    #     instance_attrs = {
    #         key: value if not callable(value) else call_value(value, self)
    #         for key, value in self.__dict__.items()
    #         if not key.startswith("_")
    #     }
    #     attrs.update(instance_attrs)

    #     # Remove all value that have None
    #     return {key: value for key, value in attrs.items() if value is not None}

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

    # def keys(self) -> Iterator[str]:
    #     return self.__attributes__.keys()

    # def values(self) -> Iterator[Any]:
    #     return self.__attributes__.values()

    # def items(self) -> ItemsView:
    #     return self.__attributes__.items()

    # def pop(self, key: str, default: Optional[Any] = None) -> Any:
    #     try:
    #         value = getattr(self, key)
    #         delattr(self, key)
    #         return value
    #     except AttributeError:
    #         return default

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

        # for key in self.__attributes__:
        #     value = getattr(self, key)

        #     value = call_value(value, self)

        for key, value in self.__attributes__.items():

            # Attribute name
            key_bytes = key.encode("utf-8")
            key_len = len(key_bytes)
            approx_size += key_len + 1

            # Attribute type
            if isinstance(value, bool):
                approx_size += 1 + 1  # struct.calcsize('b')
            elif isinstance(value, int):
                approx_size += 1 + 4  # struct.calcsize('i')
            elif isinstance(value, float):
                approx_size += 1 + 8  # struct.calcsize('d')
            elif isinstance(value, str):
                approx_size += 1 + 127  # Allow for a string of 127 characters max
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
        logging.debug(f"Encoding {len(self)} attributes")

        output = struct.pack('>B', len(self.__attributes__))

        for key, value in self.__attributes__.items():
            # Attribute name
            key_bytes = key.encode("utf-8")
            key_len = len(key_bytes)
            if key_len > 127:
                raise ValueError("Attribute name too long")
            output += struct.pack('>B', key_len)
            output += key_bytes

            # Attribute type
            if isinstance(value, bool):
                output += struct.pack('>B', TypeSize.BOOLEAN.value)
                output += struct.pack('>B', int(value))
                logging.debug(f"Encoding boolean {key} of value {value}")

            elif isinstance(value, int):
                output += struct.pack('>B', TypeSize.INT.value)
                output += struct.pack('>i', value)
                logging.debug(f"Encoding int {key} of value {value}")

            elif isinstance(value, float):
                output += struct.pack('>B', TypeSize.DOUBLE.value)
                output += struct.pack('>d', value)  # Changed 'f' to 'd'
                logging.debug(f"Encoding double {key} of value {value}")

            elif isinstance(value, str):
                output += struct.pack('>B', TypeSize.STRING.value)
                value_bytes = value.encode("utf-8")
                value_len = len(value_bytes)
                if value_len > 127:
                    raise ValueError(f"Attribute value too long for key-value pair\n\t{key}:`{value}`")
                output += struct.pack('>i', value_len)
                output += value_bytes
                logging.debug(f"Encoding string {key} of length {value_len}")

            elif isinstance(value, AxoneStruct):
                output += struct.pack('>B', TypeSize.AXONESTRUCT.value)
                encoded_struct = value.encode()
                output += struct.pack('>i', len(encoded_struct))
                output += encoded_struct

            else:
                raise ValueError(f"Unknown attribute type {type(value)} for key-value pair\n\t{key}:`{value}`")

        return output

    @timeit_if_debug
    def decode(self, data) -> None:
        """Decode binary data and set attributes accordingly"""
        # Create an iterator from the data
        data_iter = iter(data)

        # Number of attributes
        num_attrs = struct.unpack('>B', bytes([next(data_iter)]))[0]

        for _ in range(num_attrs):
            # Attribute name
            key_len = struct.unpack('>B', bytes([next(data_iter)]))[0]
            key = bytes(next(data_iter) for _ in range(key_len)).decode("utf-8")

            # Attribute type
            attr_type = TypeSize(struct.unpack('>B', bytes([next(data_iter)]))[0])

            if attr_type == TypeSize.BOOLEAN:
                value = bool(struct.unpack('>B', bytes([next(data_iter)]))[0])

            elif attr_type == TypeSize.INT:
                value = struct.unpack('>i', bytes(next(data_iter) for _ in range(BYTES_PER_INT)))[0]

            elif attr_type == TypeSize.DOUBLE:
                value = struct.unpack('>d', bytes(next(data_iter) for _ in range(2 * BYTES_PER_INT)))[0]

            elif attr_type == TypeSize.STRING:
                value_len = struct.unpack('>i', bytes(next(data_iter) for _ in range(BYTES_PER_INT)))[0]
                value = bytes(next(data_iter) for _ in range(value_len)).decode("utf-8")

            elif attr_type == TypeSize.AXONESTRUCT:
                value = AxoneStruct()
                value_len = struct.unpack('>i', bytes(next(data_iter) for _ in range(BYTES_PER_INT)))[0]
                value.decode(bytes(next(data_iter) for _ in range(value_len)))

            else:
                raise ValueError(f"Unknown attribute type {attr_type}")

            logging.debug(f"Setting attribute {key} to {value if not attr_type == TypeSize.AXONESTRUCT else type(value)}")
            setattr(self, key, value)


class AxoneTopic(AxoneStruct):
    source_: str = ""  # source
    timestamp_: float = 0.0  # timestamp
    rate_: float = -1.0  # rate


class AxoneService(AxoneStruct):
    source_: str = ""  # source
    request: AxoneStruct = None  # request
    response: AxoneStruct = None  # response


if __name__ == "__main__":
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

        xyz: SubMessage = SubMessage()

        an_decently_long_attribute_name: str = "world"
        # an_overly_long_attribute_name_that_should_raise_an_error_if_attempted_to_be_encoded_but_yeah_let_s_try_it_anyway_gosh_this_is_longer_than_i_expected_what_a_long_name_i_must_be_crazy_to_have_thought_of_this: (  # noqa: E501
        #     str
        # ) = "!"

        a_callable: callable = lambda x: 1 + 1

        def _update_message(self) -> None:
            return f"Hello message_callback from topic_published_rate_func {2 * time.time()}"

        message_callback: str = _update_message

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

    # Service
    print("\nServices")

    service = AServicePassedToAxone()

    with open("service.bin", "wb") as f:
        print("service.encode()")
        out = service.encode()
        f.write(out)

    # print out in hexadecimal string
    print(" ".join(f"{c:02x}" for c in out))

    with open("service.bin", "rb") as f:
        print("service.decode()")
        out = f.read()
        print(out)
        service2 = AxoneStruct()  # The base message class
        service2.decode(out)  # A subclass of the base message class that inherits the attribute of ATopicPassedToAxone

        print("Request", str(service2.request))
        print("Response", str(service2.response))
