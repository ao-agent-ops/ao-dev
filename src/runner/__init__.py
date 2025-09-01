from .taint_wrappers import cursed_join

# Built-in overrides:
BUILT_IN_OVERRIDES = [(str, "join", cursed_join)]
