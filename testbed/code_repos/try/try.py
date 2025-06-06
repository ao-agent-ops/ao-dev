import os
import random

class A:

    def init(self, x):
        os.system(x)
        pass

    # def exec(self,x):
    #     os.system(x)

def func_ultimate(x):
    a = A(x)
    # a.exec(x)

def func_next(x):
    x = int(x) + 5
    func_ultimate(x)

def func1(x):
    func2(x)

def func2(x):
    func_next(x)

def vulnerable():
    # (Line 4)
    x = input("Enter something: ")

    if random.random() > 0.5:
        # Branch A → sink at line 7
        a = x + "safasd"
        func2(a)
    else:
        # Branch B → sink at line 9
        a = "Adfasdf" + x
        func1(a)

if __name__ == "__main__":
    vulnerable()

