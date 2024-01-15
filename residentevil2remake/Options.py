from Options import Choice, OptionList

class Character(Choice):
    """Leon: Expected, can video game.
    Claire: Optimal choice, but needs implement."""
    display_name = "Character to Play"
    option_leon = 0
    option_claire = 1
    default = 0

class Scenario(Choice):
    """A: Best letter.
    B: 2nd-best letter. Too similar to A. Probably not implemented yet."""
    display_name = "Scenario to Play"
    option_a = 0
    option_b = 1
    default = 0

class Difficulty(Choice):
    """Standard: Most people should play on this.
    Hardcore: Good luck, and thanks for testing deaths. Kappa
    Assisted: No. Do Standard."""
    display_name = "Difficulty to Play On"
    option_standard = 0
    option_hardcore = 1
    default = 0

class UnlockedTypewriters(OptionList):
    """Specify the exact name of typewriters from the warp buttons in-game, as a YAML array.
    """
    display_name = "Unlocked Typewriters"

re2roptions = {
    "character": Character,
    "scenario": Scenario,
    "difficulty": Difficulty,
    "unlocked_typewriters": UnlockedTypewriters
}
