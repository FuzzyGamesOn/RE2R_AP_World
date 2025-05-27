from Options import OptionError

class RE2ROptionError(OptionError):
    def __init__(self, msg):
        msg = f"There was a problem with your RE2R YAML options. {msg}"

        super().__init__(msg)

