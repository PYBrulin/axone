from enum import Enum
from typing import Any


class TypeSize(Enum):
    BOOLEAN = 0
    INT = 1
    LONG = 2
    STRING = 3
    AXONESTRUCT = 4


class AxoneStruct:
    def __init__(self) -> None:
        pass

    def list_all_attrs(self) -> None:
        print(self.__class__.__name__)
        print("> Instance attributes:")
        for key, value in self.__dict__.items():
            print(" |", key, type(value), value)
        print("> Class attributes:")
        for key, value in self.__class__.__dict__.items():
            if not key.startswith("__"):
                print(" |", key, type(value), value)
        print("> Method Resolution Order:")
        for cls in self.__class__.mro()[1:]:
            subattrs = [key for key in cls.__dict__.keys() if not key.startswith("__") and not callable(getattr(cls, key))]
            if subattrs:
                print(" |", cls.__name__, subattrs)

    def __str__(self) -> str:
        out = self.__class__.__name__
        for key, value in self.__class__.__dict__.items():
            if not key.startswith("__") and not callable(getattr(self.__class__, key)):
                out += f"\n │ {key} {type(value)} {value}"
        return out

    @property
    def __attributes__(self) -> str:
        return {
            key: value
            for key, value in self.__class__.__dict__.items()
            if not key.startswith("__") and not callable(getattr(self.__class__, key))
        }

    def __getitem__(self, key: str) -> Any:
        return getattr(self.__class__, key)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.__class__.__dict__:
            setattr(self.__class__, key, value)
        else:
            raise AttributeError(
                f"Attribute '{key}' not found in class '{self.__class__.__name__}'. You should not add new attributes to the "
                + "class at runtime otherwise the size of the message might overflow the shared memory block that has been "
                + "allocated for it."
            )

    __BYTES_PER_INT__ = 4

    def get_approximate_size(self) -> int:
        """Get the approximate size of the encoded message.

        Do the same encoding as in the encode method, but instead of actually
        encoding the data, just return the size of the output and set a high value for string mostly
        """

        # Number of attributes
        attrs = [
            key
            for key in self.__class__.__dict__.keys()
            if not key.startswith("__") and not callable(getattr(self.__class__, key))
        ]
        approx_size = 2

        for key in attrs:
            value = getattr(self, key)

            # Attribute name
            key_bytes = key.encode("utf-8")
            key_len = len(key_bytes)
            approx_size += key_len + 1

            # Attribute type
            if isinstance(value, bool):
                approx_size += 2
            elif isinstance(value, int):
                approx_size += 1 + self.__BYTES_PER_INT__
            elif isinstance(value, float):
                approx_size += 1 + 2 * self.__BYTES_PER_INT__
            elif isinstance(value, str):
                approx_size += 1 + 127  # Allow for a string of 127 characters max
            elif isinstance(value, AxoneStruct):
                approx_size += 1 + value.get_approximate_size()
            else:
                raise ValueError(f"Unknown attribute type {type(value)}")

        return approx_size

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
            if type is int or string:
            - __BYTES_PER_INT__ bytes: length of the attribute value
            - n bytes: attribute value
            if type is float, encode both parts separately:
            - __BYTES_PER_INT__ bytes: length of the attribute integer part
            - n bytes: attribute integer part
            - __BYTES_PER_INT__ bytes: length of the attribute decimal part
            - n bytes: attribute decimal part
        """

        # Number of attributes
        attrs = [
            key
            for key in self.__class__.__dict__.keys()
            if not key.startswith("__") and not callable(getattr(self.__class__, key))
        ]

        num_attrs = len(attrs)
        output = num_attrs.to_bytes(1, byteorder="big")

        output += self.__BYTES_PER_INT__.to_bytes(1, byteorder="big")

        for key in attrs:
            value = getattr(self, key)

            # Attribute name
            key_bytes = key.encode("utf-8")
            key_len = len(key_bytes)
            if key_len > 127:
                raise ValueError("Attribute name too long")
            output += key_len.to_bytes(1, byteorder="big")
            output += key_bytes

            # Attribute type
            if isinstance(value, bool):
                output += TypeSize.BOOLEAN.value.to_bytes(1, byteorder="big")
                output += int(value).to_bytes(1, byteorder="big")

            elif isinstance(value, int):
                output += TypeSize.INT.value.to_bytes(1, byteorder="big")
                output += value.to_bytes(self.__BYTES_PER_INT__, byteorder="big")

            elif isinstance(value, float):
                output += TypeSize.LONG.value.to_bytes(1, byteorder="big")
                string_value = format(value, '.8f')

                # Split float into integer using string
                int_part = int(string_value.split(".")[0])
                dec_part = int(string_value.split(".")[1])
                output += int_part.to_bytes(self.__BYTES_PER_INT__, byteorder="big")
                output += dec_part.to_bytes(self.__BYTES_PER_INT__, byteorder="big")

            elif isinstance(value, str):
                output += TypeSize.STRING.value.to_bytes(1, byteorder="big")
                value_bytes = value.encode("utf-8")
                value_len = len(value_bytes)
                if value_len > 127:
                    raise ValueError(f"Attribute value too long for key-value pair\n\t{key}:`{value}`")
                output += value_len.to_bytes(self.__BYTES_PER_INT__, byteorder="big")
                output += value_bytes

            elif isinstance(value, AxoneStruct):
                output += TypeSize.AXONESTRUCT.value.to_bytes(1, byteorder="big")
                encoded_struct = value.encode()
                output += len(encoded_struct).to_bytes(self.__BYTES_PER_INT__, byteorder="big")
                output += encoded_struct

            else:
                raise ValueError(f"Unknown attribute type {type(value)}")

        return output

    def decode(self, data) -> None:
        """Decode binary data and set attributes accordingly"""
        # Create an iterator from the data
        data_iter = iter(data)

        # Number of attributes
        num_attrs = int.from_bytes(next(data_iter).to_bytes(1, byteorder='big'), byteorder="big")

        # __BYTES_PER_INT__
        self.__BYTES_PER_INT__ = int.from_bytes(next(data_iter).to_bytes(1, byteorder='big'), byteorder="big")

        for _ in range(num_attrs):
            # Attribute name
            key_len = int.from_bytes(next(data_iter).to_bytes(1, byteorder='big'), byteorder="big")
            key = bytes(next(data_iter) for _ in range(key_len)).decode("utf-8")

            # Attribute type
            attr_type = TypeSize(int.from_bytes(next(data_iter).to_bytes(1, byteorder='big'), byteorder="big"))

            if attr_type == TypeSize.BOOLEAN:
                value = bool(int.from_bytes(next(data_iter).to_bytes(1, byteorder='big'), byteorder="big"))

            elif attr_type == TypeSize.INT:
                value = int.from_bytes(bytes(next(data_iter) for _ in range(self.__BYTES_PER_INT__)), byteorder="big")

            elif attr_type == TypeSize.LONG:
                int_part = int.from_bytes(bytes(next(data_iter) for _ in range(self.__BYTES_PER_INT__)), byteorder="big")
                dec_part = int.from_bytes(bytes(next(data_iter) for _ in range(self.__BYTES_PER_INT__)), byteorder="big")
                value = float(f"{int_part}.{dec_part}")

            elif attr_type == TypeSize.STRING:
                value_len = int.from_bytes(bytes(next(data_iter) for _ in range(self.__BYTES_PER_INT__)), byteorder="big")
                value = bytes(next(data_iter) for _ in range(value_len)).decode("utf-8")

            elif attr_type == TypeSize.AXONESTRUCT:
                value = AxoneStruct()
                value_len = int.from_bytes(bytes(next(data_iter) for _ in range(self.__BYTES_PER_INT__)), byteorder="big")
                value.decode(bytes(next(data_iter) for _ in range(value_len)))

            else:
                raise ValueError(f"Unknown attribute type {attr_type}")

            setattr(self, key, value)


class AxoneTopic(AxoneStruct):
    _source: str = ""  # source
    _timestamp: float = 0.0  # timestamp
    _rate: float = -1.0  # rate


class AxoneService(AxoneStruct):
    _source: str = ""  # source
    request: AxoneStruct = None  # request
    response: AxoneStruct = None  # response


if __name__ == "__main__":

    class SubMessage(AxoneStruct):
        x: int = 0
        y: int = 1
        z: int = 2

    class ATopicPassedToAxone(AxoneTopic):
        a: bool = True
        b: int = 0
        c: int = 1
        d: int = 2
        e: float = 1.23456789
        f: float = 1e9
        g: float = 0.00001357
        h: str = "hello"

        xyz: SubMessage = SubMessage()

        an_decently_long_attribute_name: str = "world"
        # an_overly_long_attribute_name_that_should_raise_an_error_if_attempted_to_be_encoded_but_yeah_let_s_try_it_anyway_gosh_this_is_longer_than_i_expected_what_a_long_name_i_must_be_crazy_to_have_thought_of_this: (  # noqa: E501
        #     str
        # ) = "!"

        # a_callable: callable = lambda x: x + 1

    class AServicePassedToAxone(AxoneService):
        _requester: str = "source"  # The node making the request
        # The request with possible arguments defined by the node advertizing the service
        request: ATopicPassedToAxone = ATopicPassedToAxone()
        # The answer to the request
        response: ATopicPassedToAxone = SubMessage()

    # Topic
    s = ATopicPassedToAxone()

    print("s.list_all_attrs()")
    s.list_all_attrs()
    print(s)

    with open("topic.bin", "wb") as f:
        print("s.encode()")
        out = s.encode()
        print(out)
        print(len(out))
        f.write(out)

    # print out in hexadecimal string
    print(" ".join(f"{c:02x}" for c in out))

    with open("topic.bin", "rb") as f:
        print("s.decode()")
        out = f.read()
        s2 = AxoneStruct()  # The base message class
        s2.decode(out)  # A subclass of the base message class that inherits the attribute of ATopicPassedToAxone
        print(s2.xyz.x)
        print(s2.h)

    # Service

    s = AServicePassedToAxone()

    with open("service.bin", "wb") as f:
        print("s.encode()")
        out = s.encode()
        f.write(out)

    # print out in hexadecimal string
    print(" ".join(f"{c:02x}" for c in out))

    with open("service.bin", "rb") as f:
        print("s.decode()")
        out = f.read()
        s2 = AxoneStruct()  # The base message class
        s2.decode(out)  # A subclass of the base message class that inherits the attribute of ATopicPassedToAxone

        print("Request", str(s2.request))
        print("Response", str(s2.response))

    # print(s.get_approximate_size(), len(s.encode()))

    # from multiprocessing import shared_memory

    # shm_a = shared_memory.SharedMemory(
    #     name=s.__class__.__name__,
    #     create=True,
    #     size=s.get_approximate_size(),
    # )
    # type(shm_a.buf)

    # buffer = shm_a.buf
    # len(buffer)

    # buffer[: len(s.encode())] = s.encode()

    # # Attach to an existing shared memory block
    # shm_b = shared_memory.SharedMemory(shm_a.name)

    # s2 = AxoneStruct()
    # s2.decode(shm_b.buf)  # Copy the data into a new Message instance
    # s2.list_all_attrs()

    # shm_b.close()  # Close each SharedMemory instance
    # shm_a.close()
    # shm_a.unlink()  # Call unlink only once to release the shared memory
