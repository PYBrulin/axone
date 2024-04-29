import base64
import json
import zlib
from typing import Final, Protocol, runtime_checkable

NULL_BYTE: Final = b"\x00"


class SerializationError(ValueError):
    def __init__(self, data: dict) -> None:
        super().__init__(f"Failed to serialize data: {data!r}")


class DeserializationError(ValueError):
    def __init__(self, data: bytes) -> None:
        super().__init__(f"Failed to deserialize data: {data!r}")


@runtime_checkable
class SharedMemoryDictSerializer(Protocol):
    def dumps(self, obj: dict) -> bytes: ...

    def loads(self, data: bytes) -> dict: ...


class JSONSerializer(SharedMemoryDictSerializer):
    __slots__ = ()
    encoder = json.JSONEncoder
    encoder.item_separator = ","
    encoder.key_separator = ":"
    decoder = json.JSONDecoder

    def dumps(self, obj: dict) -> bytes:
        try:
            return json.dumps(obj, cls=self.encoder).encode() + NULL_BYTE
        except (ValueError, TypeError):
            raise SerializationError(obj)

    def loads(self, data: bytes) -> dict:
        data = data.split(NULL_BYTE, 1)[0]
        try:
            return json.loads(data, cls=self.decoder)
        except json.JSONDecodeError:
            raise DeserializationError(data)


class B64Serializer(SharedMemoryDictSerializer):
    __slots__ = ()
    encoder = json.JSONEncoder
    encoder.item_separator = ","
    encoder.key_separator = ":"
    decoder = json.JSONDecoder

    def dumps(self, obj: dict) -> bytes:
        try:
            obj = base64.b64encode(
                zlib.compress(
                    json.dumps(
                        obj,
                        cls=self.encoder,
                    ).encode(),
                    9,
                )
            )
            return obj + NULL_BYTE
        except (ValueError, TypeError):
            raise SerializationError(obj)

    def loads(self, data: bytes) -> dict:
        data = data.split(NULL_BYTE, 1)[0]
        try:
            return json.loads(
                zlib.decompress(base64.b64decode(data)).decode("utf-8"),
                cls=self.decoder,
            )
        except json.JSONDecodeError:
            raise DeserializationError(data)


SERIALIZERS = {
    "json": JSONSerializer(),
    "b64": B64Serializer(),
}


if __name__ == "__main__":
    serializer = B64Serializer()
    data = {"a": 1, "b": 2}
    serialized = serializer.dumps(data)
    print(serialized)
    deserialized = serializer.loads(serialized)
    print(deserialized)
    assert deserialized == data, f"{deserialized!r} != {data!r}"

    print(str(serializer))
    print(str(JSONSerializer.__name__))
    print(str(B64Serializer.__name__))
