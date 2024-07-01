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
    if not hasattr(func, 'wrapper_depth'):
        func.wrapper_depth = -1  # Initialize a counter on the function if it doesn't exist

    def wrapper(*args, **kwargs):
        func.wrapper_depth += 1  # Increment the counter each time the wrapper is called
        if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            logging.debug(f"[{func.wrapper_depth}] {func.__name__}() execution time: {end_time - start_time} seconds")
        else:
            result = func(*args, **kwargs)
        func.wrapper_depth -= 1  # Decrement the counter when exiting the wrapper
        return result

    return wrapper


if __name__ == "__main__":
    print(generate_uuid("Hello"))
    print(generate_uuid("Hello"))
    print(generate_uuid("Hello1"))

    print(generate_uuid("test_node_to_central"))
    print(generate_uuid("test_node2_to_central"))
