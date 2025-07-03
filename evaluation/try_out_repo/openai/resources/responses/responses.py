def __test_source():
    # static‐analysis placeholder only
    return "some string"

def __test_sink(x):
    # static‐analysis placeholder only
    return

class Responses:
    def create(self, model=None, input=None, **kwargs):
        # Explicitly sink the important parameters
        if input is not None:
            __test_sink(input)
            reveal_taint(input)  # This should show taint if it's working
        if model is not None:
            __test_sink(model)
            reveal_taint(model)
        return __test_source()

