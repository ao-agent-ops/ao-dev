class TaintedString:
    def __init__(self, value, taint=True):
        self.value = value
        self.taint = taint

    def __str__(self):
        return self.value

    def __format__(self, format_spec):
        formatted = format(self.value, format_spec)
        return TaintedString(formatted, self.taint)

    def __add__(self, other):
        if isinstance(other, TaintedString):
            return TaintedString(self.value + other.value, self.taint or other.taint)
        elif isinstance(other, str):
            return TaintedString(self.value + other, self.taint)
        return NotImplemented

    def __radd__(self, other):
        if isinstance(other, str):
            return TaintedString(other + self.value, self.taint)
        return NotImplemented

    def is_tainted(self):
        return self.taint

if __name__ == "__main__":
    tainted = TaintedString("bad")
    result = f"hello {tainted}"
    print(result.value)      # "hello bad"
    print(result.is_tainted())  # True
