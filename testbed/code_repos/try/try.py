import openai
import random


import sys
import os

def trace_calls(frame, event, arg):
    if event != 'call':
        return
    co = frame.f_code
    func_name = co.co_name
    filename = os.path.basename(co.co_filename)
    lineno   = frame.f_lineno
    print(f"→ call to {func_name}() in {filename}:{lineno}")
    # returning itself means "trace inside this function too"
    return trace_calls


client = openai.Client(api_key="asfasd")


def create(x):
    print(f"create: {x}")
    return "create_return"

class A:

    def __init__(self, x):
        # x = client.responses.create(
        #     model="gpt-4.1",
        #     input=x
        # )

        x = os.path.join("hello", x)
        create(x)
        pass

    # def exec(self,x):
    #     os.system(x)

def func_ultimate(x):
    a = A(x)
    # a.exec(x)

def func_next(x):
    # x = int(x) + 5
    func_ultimate(x)

def func1(x):
    func2(x)

def func2(x):
    func_next(x)

def vulnerable():
    # x = client.responses.create(
    #     model="gpt-4.1",
    #     input="hello"
    # )
    x = create("hello")

    if random.random() > 0.5:
        # a = x + "safasd"
        func2(x)
    else:
        # a = "Adfasdf" + x
        func1(x)

if __name__ == "__main__":
    sys.settrace(trace_calls)
    vulnerable()
