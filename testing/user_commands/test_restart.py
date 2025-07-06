import time
import os

print("Test script started!")
print(f"PID: {os.getpid()}")
print(f"Working directory: {os.getcwd()}")
print("Waiting for input (or restart)...")
user_input = input("Enter something: ")
print(f"You entered: {user_input}")
print("Script finished!") 