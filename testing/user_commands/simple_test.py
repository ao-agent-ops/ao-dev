import time
import os

print("Simple test script started!")
print(f"PID: {os.getpid()}")
print(f"Working directory: {os.getcwd()}")
print("Script will finish in 3 seconds...")
time.sleep(3)
print("Script finished!") 