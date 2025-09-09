import re
import json
from runner.taint_wrappers import TaintStr
from enum import Enum

class Test(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3

def main():
    out = json.dumps([TaintStr('foo', taint_origin=['origin']), {'bar': ('baz', None, 1.0, 2)}])
    assert isinstance(out, TaintStr), "out from re.Match.group() is not tainted"
    test = TaintStr("Hello \n I am", taint_origin=["origin"])
    match = re.search(pattern=r'\n', string=test)
    out = match[0]  # this does not work currently
    out = match.group()
    assert isinstance(out, TaintStr), "out from re.Match.group() is not tainted"


if __name__ == "__main__":
    main()