# Script to run all example_* script in separate processes

import os
import subprocess
import sys
import time

os.system("cls||clear")  # Clear the terminal


from custom_logger import setup_logger

setup_logger(debug=False)


# Get the path to the examples directory
examples_dir = os.path.dirname(os.path.realpath(__file__))
# Get the path to the root directory
root_dir = os.path.dirname(examples_dir)

# Get the path to the example scripts
example_scripts = [
    os.path.join(examples_dir, f)
    for f in os.listdir(examples_dir)
    if f.startswith('example_')
]

# Run each example script in a separate process
for script in example_scripts:
    # Run the script in a separate process
    subprocess.Popen([sys.executable, script])
    time.sleep(1)
try:
    # Wait for all processes to finish
    while True:
        time.sleep(1)
except Exception as e:
    print(e)
    pass
finally:
    # Kill all processes
    for script in example_scripts:
        subprocess.Popen(['pkill', '-f', script])
        time.sleep(1)

# Exit
sys.exit(0)
