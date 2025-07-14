from static_analysis.pyre_static_analysis.models_and_stubs.openai.resources.responses.responses import Responses

class Client:
    def __init__(self, api_key: str) -> None:
        pass

    @property
    def responses(self) -> Responses:
        return Responses()
