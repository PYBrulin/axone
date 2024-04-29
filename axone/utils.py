import functools
import random
import string
import time

TIMESTAMP_PRECISION = 3


def generate_uuid(input_string: str) -> str:
    """Generate a unique id"""
    # Generate a random string of 10 characters based on the input string
    random.seed(input_string)  # TODO: Meh. This is not bad but not good either.
    return "".join(random.choices(string.ascii_letters + string.digits + input_string, k=10))


def get_timestamp(timestamp_precision: int = TIMESTAMP_PRECISION) -> int | float:
    """Output a formatted timestamp."""
    # TODO:Limit the range of the timestamp.
    # TODO:Currently Assume that the timestamp can not be older than 1 year.
    # TODO:This will prevent the timestamp from taking too much space in the memory.
    # Idea base the timestamp on the oldest node in the memory.
    # And reduce the floating point precision to 3 digits
    return round(
        time.time(),
        (
            timestamp_precision if timestamp_precision > 0 else None
        ),  # Note: If ndigits is None round() converts to int directly
    )


def conditional_decorator(condition, decorator):
    """Return the decorator if condition is true, otherwise return a function that does nothing."""

    def decorator_func(func):
        if not condition:
            return func
        return decorator(func)

    return decorator_func


def time_it(func):
    """Time the execution of a function."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} ran in: {end_time - start_time} secs")
        return result

    return wrapper


if __name__ == "__main__":
    print(generate_uuid("Hello"))
    print(generate_uuid("Hello"))
    print(generate_uuid("Hello1"))
