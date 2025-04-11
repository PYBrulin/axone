from enum import Enum, EnumMeta


class MyMeta(EnumMeta):

    def __contains__(self, other) -> bool:
        try:
            self(other)
        except ValueError:
            return False
        else:
            return True


class Method(Enum, metaclass=MyMeta):
    SOCKET = 0
    SHARED_MEMORY = 1

    @classmethod
    def from_value(cls, value) -> 'Method':
        return cls(value)
