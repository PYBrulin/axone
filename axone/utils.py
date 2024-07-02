import logging
import random
import string
import time


def generate_uuid(input_string: str) -> str:
    """Generate a unique id"""
    # Generate a random string of 10 characters based on the input string
    random.seed(input_string)  # TODO: Meh. This is not bad but not good either.
    return "".join(random.choices(string.ascii_letters + string.digits + input_string, k=10))


def timeit_if_debug(func):
    def wrapper(*args, **kwargs):
        if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            millitime = (end_time - start_time) * 1000
            # We expect the execution time to be less than 1 millisecond for most functions
            if millitime > 1:
                logging.error(f"{func.__name__}() execution time: {millitime} milliseconds")
            else:
                logging.debug(f"{func.__name__}() execution time: {millitime} milliseconds")
            return result
        else:
            return func(*args, **kwargs)

    return wrapper


if __name__ == "__main__":
    print(generate_uuid("Hello"))
    print(generate_uuid("Hello"))
    print(generate_uuid("Hello1"))

    print(generate_uuid("test_node_to_central"))
    print(generate_uuid("test_node2_to_central"))
