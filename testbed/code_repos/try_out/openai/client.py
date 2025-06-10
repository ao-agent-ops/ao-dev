from .resources.responses.responses import Responses

class Client:
    def __init__(self, api_key: str) -> None:
        pass

    @property
    def responses(self) -> Responses:
        return Responses()
