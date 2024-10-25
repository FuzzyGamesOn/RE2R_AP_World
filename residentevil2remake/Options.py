from dataclasses import dataclass
from Options import (Choice, OptionList, NamedRange, 
    StartInventoryPool,
    PerGameCommonOptions, DeathLinkMixin)

class Character(Choice):
    """Leon: Expected, can video game.
    Claire: Optimal choice, but more lickers."""
    display_name = "Character to Play"
    option_leon = 0
    option_claire = 1
    default = 0

class Scenario(Choice):
    """A: Best letter.
    B: 2nd-best letter. Very similar to A. Also known as 2nd scenario."""
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

class StartingHipPouches(NamedRange):
    """The number of hip pouches you want to start the game with, to a max of 6 (or 5 for Hardcore). 
    Any that you start with are taken out of the item pool and replaced with junk."""
    default = 0
    range_start = 0
    range_end = 6
    display_name = "Starting Hip Pouches"
    special_range_names = {
        "disabled": 0,
        "half": 3,
        "all": 6
    }

class StartingInkRibbons(NamedRange):
    """If playing Hardcore, the number of ink ribbons you want to start the game with, to a max of 12.
    Any that you start with are taken out of the item pool and replaced with junk."""
    default = 0
    range_start = 0
    range_end = 12
    display_name = "Starting Ink Ribbons"
    special_range_names = {
        "disabled": 0,
        "half": 6,
        "all": 12
    }

class BonusStart(Choice):
    """Some players might want to start with a little help in the way of a few extra heal items and packs of ammo.
    This option IS affected by cross-scenario weapon randomization, if that option is set.

    False: Normal, don't start with extra heal items and packs of ammo.
    True: Start with those helper items."""
    display_name = "Bonus Start"
    option_false = 0
    option_true = 1
    default = 0

class ExtraClockTowerItems(Choice):
    """The gears and jack handle required for Clock Tower can leave players BK for a while. 
    This option adds an extra set of these items so the odds of BK are lower.

    False: Normal, only 1 of each gear and the jack handle in the item pool.
    True: Now, 2 of each gear and 2 jack handles in the item pool."""
    display_name = "Extra Clock Tower Items"
    option_false = 0
    option_true = 1
    default = 1

class ExtraMedallions(Choice):
    """On your first visit to RPD, the medallions are required to leave. 
    If you spend too long waiting for these on average, this option will add extras of 2 medallions.

    False: Normal, only 1 of each RPD medallion in the item pool.
    True: Now, A scenarios will have 2 extra medallions (since Maiden is always at Fire Escape). 
          B scenarios will have 3 extra medallions since all are randomized."""
    display_name = "Extra Medallions"
    option_false = 0
    option_true = 1
    default = 1

class AllowProgressionInLabs(Choice):
    """The randomizer has a tendency to put other player's progression towards the end in Labs, which can cause some lengthy BK. 
    This option seeks to avoid that.

    False: (Default) The only progression in Labs -- and the final fight area(s) -- will be the non-randomized upgraded bracelets for Labs.
    True: Progression can be placed in Labs and the final fight area(s). This can, but won't always, lead to some BK.

    NOTE - This option only affects *YOUR* Labs. Your progression can still be in someone else's Labs if they have this option enabled."""
    display_name = "Allow Progression in Labs"
    option_false = 0
    option_true = 1
    default = 0

class CrossScenarioWeapons(Choice):
    """This option, when set, will randomize the weapons in your scenario, choosing from weapons in all 4 scenarios (LA, LB, CA, CB). 
    This includes weapon upgrades as well.

    This DOES NOT include boss weapons like the Anti-tank Rocket and the Minigun. This DOES include your starting weapon.
    This also DOES affect the Bonus Start option, if set.
    
    The available options are:

    None: You have thought better of randomizing your weapons, and balance is restored in the galaxy.
    Starting: Only your starting weapon is randomized. It can be randomized to any other weapon.
    Match: Weapon randomization will match light weapons (like pistols) to other light weapons, 
            medium weapons (like shotguns) to other medium weapons (like grenade launcher), etc. 
            Includes their upgrades. Ammo is matched by type (light, medium, etc.).
    Full: Weapon randomization will just pick at random. This can make you have all weak weapons or all strong weapons, or something in between. 
            Includes their upgrades. Ammo is split as it normally was by type (light, medium, etc.).
    All: Weapon randomization will add every available weapon and their upgrades. 
            Ammo is matched by type (light, medium, etc.) and split evenly in each type.
    Full Ammo: Same as Full (picks weapons at random), and will also randomize how much ammo is placed for each in the world.
    All Ammo: Same as All (adds every weapon from all 4 scenarios), and randomizes how much ammo is placed for each in the world.
    Troll: Same as AllAmmo (every weapon + random ammo), except the randomizer removes all but a few weapons. 
            Ammo and upgrades for the removed weapons are still included to troll you.
            
    NOTE: The options for "Full Ammo", "All Ammo", and "Troll" are not guaranteed to be reasonably beatable. Especially Troll. >:)"""
    display_name = "Cross-Scenario Weapons"
    option_none = 0
    option_starting = 1
    option_match = 2
    option_full = 3
    option_all = 4
    option_full_ammo = 5
    option_all_ammo = 6   
    option_troll = 7
    default = 0

class AmmoPackModifier(Choice):
    """This option, when set, will modify the quantity of ammo in each ammo pack. This can make the game easier or much, much harder.
    The available options are:

    None: You realized that consistency in ammo pack quantities is one of the few true joys in life, and this causes you to not modify them at all.
    Max: Each ammo pack will contain the maximum amount of ammo that the game allows. (i.e., you will never, ever run out of ammo.)
    Double: Each ammo pack will contain twice as much ammo as it normally contains.
    Half: Each ammo pack will contain half as much ammo as it normally contains.
    Only Three: Each ammo pack will have an ammo count of 3.
    Only Two: Each ammo pack will have an ammo count of 2.
    Only One: Each ammo pack will have an ammo count of 1. (Yes, your Handgun Ammo pack will have a single bullet in it.)
    Random By Type: Each ammo type's ammo pack will have a random quantity of ammo, and you will get that same quantity of ammo from every pack for that ammo type.
        (For example, you receive a Shotgun Shells pack that has a random quantity of 7 ammo. All Shotgun Shells packs will have a quantity of 7.)
    Random Always: Each ammo pack will have a random quantity of ammo, and that quantity will be randomized every time.
        (For example, you receive a Shotgun Shells pack that has a random quantity of 7 ammo. Your next Shotgun Shells pack has a quantity of 4, next has 2, etc.)

    NOTE: The options for "Only Three", "Only Two", "Only One", "Random By Type", and "Random Always" are not guaranteed to be reasonably beatable."""
    display_name = "Ammo Pack Modifier"
    option_none = 0
    option_max = 1
    option_double = 2
    option_half = 3
    option_only_three = 4
    option_only_two = 5
    option_only_one = 6
    option_random_by_type = 7
    option_random_always = 8

class OopsAllRockets(Choice):
    """Enabling this swaps all weapons, weapon ammo, and subweapons to Rocket Launchers. 
    (Except progression weapons, of course.)"""
    display_name = "Oops! All Rockets"
    option_false = 0
    option_true = 1
    default = 0

class OopsAllGrenades(Choice):
    """Enabling this swaps all weapons, weapon ammo, and subweapons to Grenades. 
    (Except progression weapons, of course.)"""
    display_name = "Oops! All Grenades"
    option_false = 0
    option_true = 1
    default = 0

class OopsAllKnives(Choice):
    """Enabling this swaps all weapons, weapon ammo, and subweapons to Knives. 
    (Except progression weapons, of course.)"""
    display_name = "Oops! All Knives"
    option_false = 0
    option_true = 1
    default = 0

class NoFirstAidSpray(Choice):
    """Enabling this swaps all first aid sprays to filler or less useful items. 
    """
    display_name = "No First Aid Spray"
    option_false = 0
    option_true = 1
    default = 0

class NoGreenHerb(Choice):
    """Enabling this swaps all green herbs to filler or less useful items. 
    """
    display_name = "No Green Herbs"
    option_false = 0
    option_true = 1
    default = 0

class NoRedHerb(Choice):
    """Enabling this swaps all red herbs to filler or less useful items. 
    """
    display_name = "No Red Herbs"
    option_false = 0
    option_true = 1
    default = 0

class NoGunpowder(Choice):
    """Enabling this swaps all gunpowder of all types to filler or less useful items. 
    """
    display_name = "No Gunpowder"
    option_false = 0
    option_true = 1
    default = 0

class AddDamageTraps(Choice):
    """Enabling this adds traps to your game that, when received, deal 1 health state of damage to you. e.g., if you're "Fine", first one puts you in "Caution". 
    By default, these traps cannot kill you, but the "Damage Traps Can Kill" option can make them lethal.
    """
    display_name = "Add Damage Traps"
    option_false = 0
    option_true = 1
    default = 0

class DamageTrapCount(NamedRange):
    """While the "AddDamageTraps" option is enabled, this option specifies how many of this trap should be placed.
    """
    default = 10
    range_start = 0
    range_end = 30 
    display_name = "Damage Trap Count"
    special_range_names = {
        "disabled": 0,
        "half": 15,
        "all": 30
    }

class DamageTrapsCanKill(Choice):
    """Enabling this while "Add Damage Traps" is enabled will allow the damage traps to drop your health state below "Danger". As in, they can kill you. 
    """
    display_name = "Damage Traps Can Kill"
    option_false = 0
    option_true = 1
    default = 0

class AddPoisonTraps(Choice):
    """Enabling this adds traps to your game that, when received, apply the Poisoned status effect.
    Warning: There are typically only 11 Blue Herbs in the game, so you can potentially run out!
    """
    display_name = "Add Poison Traps"
    option_false = 0
    option_true = 1
    default = 0

class PoisonTrapCount(NamedRange):
    """While the "AddPoisonTraps" option is enabled, this option specifies how many of this trap should be placed.
    """
    default = 10
    range_start = 0
    range_end = 30 
    display_name = "Poison Trap Count"
    special_range_names = {
        "disabled": 0,
        "half": 15,
        "all": 30
    }

# making this mixin so we can keep actual game options separate from AP core options that we want enabled
# not sure why this isn't a mixin in core atm, anyways
@dataclass
class StartInventoryFromPoolMixin:
    start_inventory_from_pool: StartInventoryPool

@dataclass
class RE2ROptions(StartInventoryFromPoolMixin, DeathLinkMixin, PerGameCommonOptions):
    character: Character
    scenario: Scenario
    difficulty: Difficulty
    unlocked_typewriters: UnlockedTypewriters
    starting_hip_pouches: StartingHipPouches
    starting_ink_ribbons: StartingInkRibbons
    bonus_start: BonusStart
    extra_clock_tower_items: ExtraClockTowerItems
    extra_medallions: ExtraMedallions
    allow_progression_in_labs: AllowProgressionInLabs
    cross_scenario_weapons: CrossScenarioWeapons
    ammo_pack_modifier: AmmoPackModifier
    oops_all_rockets: OopsAllRockets
    oops_all_grenades: OopsAllGrenades
    oops_all_knives: OopsAllKnives
    no_first_aid_spray: NoFirstAidSpray
    no_green_herb: NoGreenHerb
    no_red_herb: NoRedHerb
    no_gunpowder: NoGunpowder
    add_damage_traps: AddDamageTraps
    damage_trap_count: DamageTrapCount
    damage_traps_can_kill: DamageTrapsCanKill
    add_poison_traps: AddPoisonTraps
    poison_trap_count: PoisonTrapCount

