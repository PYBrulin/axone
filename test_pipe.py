import multiprocessing
import time


def child_process(conn):
    # Receive message from parent
    start_time = time.perf_counter()
    msg = conn.recv()
    end_time = time.perf_counter()
    millitime = (end_time - start_time) * 1000

    print(f"Child received message: '{msg}' in {millitime} milliseconds")

    # Send response back to parent
    conn.send("Received your message!")


if __name__ == "__main__":
    # Create a Pipe
    parent_conn, child_conn = multiprocessing.Pipe()

    # Create and start child process
    p = multiprocessing.Process(target=child_process, args=(child_conn,))
    p.start()

    # Send a message to child process and measure time
    start_time = time.perf_counter()
    parent_conn.send("Hello, child process!")
    response = parent_conn.recv()
    end_time = time.perf_counter()
    millitime = (end_time - start_time) * 1000
    print(f"Parent received response: '{response}' in {millitime} milliseconds")

    # Wait for child process to finish
    p.join()
