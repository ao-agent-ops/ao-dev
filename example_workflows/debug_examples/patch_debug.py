from runner.taint_wrappers import TaintStr
import re


def main():
    test = TaintStr("Hello \n I am", taint_origin=["origin"])
    match = re.search(pattern=r'\n', string=test)
    out = match[0]

if __name__ == "__main__":
    main()