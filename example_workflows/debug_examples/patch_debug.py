from runner.taint_wrappers import TaintStr
import re
import json


def f(s):
    return s + "hello"

def main():
    s = TaintStr('foo', taint_origin=['origin'])
    x = f(s)

    x = json.dumps([TaintStr('foo', taint_origin=['origin']), {'bar': ('baz', None, 1.0, 2)}])
    x == str
    str == x
    test = TaintStr("Hello \n I am", taint_origin=["origin"])
    match = re.search(pattern=r'\n', string=test)
    out = match[0]
    out = match.group()
    pass

if __name__ == "__main__":
    main()