import os
import time

import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm


def create_file(filename, size):
    with open(filename, 'wb') as f:
        f.write(os.urandom(size))


def measure_write_time(filename, size):
    start_time = time.perf_counter_ns()
    with open(filename, 'wb') as f:
        f.write(os.urandom(size))
    end_time = time.perf_counter_ns()
    return end_time - start_time


def measure_read_time(filename):
    start_time = time.perf_counter_ns()
    with open(filename, 'rb') as f:
        _ = f.read()
    end_time = time.perf_counter_ns()
    return end_time - start_time


def convert_bytes(num) -> str:
    """
    this function will convert bytes to MB.... GB... etc
    https://stackoverflow.com/a/52379087
    """
    step_unit = 1024.0
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < step_unit:
            return f"{num:3.1f} {x}"
        num /= step_unit


# Sizes in bytes (1B, 1KB, 10KB, 100KB, 1MB, 10MB, 100MB)
sizes = [
    1,  # 1 byte
    1024,
    10 * 1024,
    100 * 1024,
    1024**2,
    10 * (1024**2),
    100 * (1024**2),
]
repetitions = 1000  # Number of times to repeat the read operation for each file size
times = []


read_times = []
write_times = []
read_min_times = []
read_max_times = []
write_min_times = []
write_max_times = []
read_std_devs = []
write_std_devs = []

for size in sizes:
    read_time_measurements = []
    write_time_measurements = []
    for _ in tqdm(range(repetitions), desc=f'Size: {convert_bytes(size)}'):
        filename = f'test_{size}.bin'
        write_time_measurements.append(measure_write_time(filename, size))
        read_time_measurements.append(measure_read_time(filename))
        os.remove(filename)  # remove the file after each repetition
    read_times.append(np.mean(read_time_measurements))
    write_times.append(np.mean(write_time_measurements))
    read_min_times.append(min(read_time_measurements))
    read_max_times.append(max(read_time_measurements))
    write_min_times.append(min(write_time_measurements))
    write_max_times.append(max(write_time_measurements))
    read_std_devs.append(np.std(read_time_measurements))
    write_std_devs.append(np.std(write_time_measurements))

# Convert times to milliseconds
read_times = [t / 1_000_000 for t in read_times]
write_times = [t / 1_000_000 for t in write_times]
read_min_times = [t / 1_000_000 for t in read_min_times]
read_max_times = [t / 1_000_000 for t in read_max_times]
write_min_times = [t / 1_000_000 for t in write_min_times]
write_max_times = [t / 1_000_000 for t in write_max_times]
read_std_devs = [t / 1_000_000 for t in read_std_devs]
write_std_devs = [t / 1_000_000 for t in write_std_devs]


# Plot read times
fig, axs = plt.subplots(2)
axs[0].plot(sizes, read_times, label='Mean Read')
axs[0].fill_between(sizes, read_min_times, read_max_times, color='b', alpha=0.1, label='Read Min-Max Range')
axs[0].errorbar(sizes, read_times, yerr=read_std_devs, fmt='.k', label='Read Std Dev')
axs[0].set_xlabel('File Size (bytes)')
axs[0].set_ylabel('Time (milliseconds)')
axs[0].set_title('File Read Time vs File Size (Default Scale)')
axs[0].legend()
axs[0].grid(True)

axs[1].plot(sizes, read_times, label='Mean Read')
axs[1].fill_between(sizes, read_min_times, read_max_times, color='b', alpha=0.1, label='Read Min-Max Range')
axs[1].errorbar(sizes, read_times, yerr=read_std_devs, fmt='.k', label='Read Std Dev')
axs[1].set_xlabel('File Size (bytes)')
axs[1].set_xscale('log')
axs[1].set_ylabel('Time (milliseconds)')
axs[1].set_yscale('log')
axs[1].set_title('File Read Time vs File Size (Logarithmic Scale)')
axs[1].legend()
axs[1].grid(True)

plt.tight_layout()

# Plot write times
fig, axs = plt.subplots(2)
axs[0].plot(sizes, write_times, label='Mean Write', color='r')
axs[0].fill_between(sizes, write_min_times, write_max_times, color='r', alpha=0.1, label='Write Min-Max Range')
axs[0].errorbar(sizes, write_times, yerr=write_std_devs, fmt='.k', label='Write Std Dev')
axs[0].set_xlabel('File Size (bytes)')
axs[0].set_ylabel('Time (milliseconds)')
axs[0].set_title('File Write Time vs File Size (Default Scale)')
axs[0].legend()
axs[0].grid(True)

axs[1].plot(sizes, write_times, label='Mean Write', color='r')
axs[1].fill_between(sizes, write_min_times, write_max_times, color='r', alpha=0.1, label='Write Min-Max Range')
axs[1].errorbar(sizes, write_times, yerr=write_std_devs, fmt='.k', label='Write Std Dev')
axs[1].set_xlabel('File Size (bytes)')
axs[1].set_xscale('log')
axs[1].set_ylabel('Time (milliseconds)')
axs[1].set_yscale('log')
axs[1].set_title('File Write Time vs File Size (Logarithmic Scale)')
axs[1].legend()
axs[1].grid(True)

# Plot read and write mean time
fig, axs = plt.subplots(2)
axs[0].plot(sizes, read_times, label='Mean Read', color='b')
axs[0].plot(sizes, write_times, label='Mean Write', color='r')
axs[0].set_xlabel('File Size (bytes)')
axs[0].set_ylabel('Time (milliseconds)')
axs[0].set_title('File Read and Write Time vs File Size (Default Scale)')
axs[0].legend()
axs[0].grid(True)

axs[1].plot(sizes, read_times, label='Mean Read', color='b')
axs[1].plot(sizes, write_times, label='Mean Write', color='r')
axs[1].set_xlabel('File Size (bytes)')
axs[1].set_xscale('log')
axs[1].set_ylabel('Time (milliseconds)')
axs[1].set_yscale('log')
axs[1].set_title('File Read and Write Time vs File Size (Logarithmic Scale)')
axs[1].legend()
axs[1].grid(True)


plt.tight_layout()
plt.show()
