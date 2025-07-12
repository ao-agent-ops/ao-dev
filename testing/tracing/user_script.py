def f(name):
    return f"Hello {namfe}, welcome!"


name = TaintedString("bad", taint=True)
msg = f(name)
print("Is tainted?", msg.is_tainted())
