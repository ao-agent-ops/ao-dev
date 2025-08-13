from language_model import LANGUAGE_MODEL

x = LANGUAGE_MODEL.invoke("hello")

y = LANGUAGE_MODEL.parse_standard_response(x)
rec = y["recommendation"]

z = LANGUAGE_MODEL.invoke(rec)
