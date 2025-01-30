import re
import typing

from typing import Dict, Any, TextIO
from Utils import visualize_regions

from BaseClasses import ItemClassification, Item, Location, Region, CollectionState
from worlds.AutoWorld import World
from ..generic.Rules import set_rule
from Fill import fill_restrictive

from .Data import Data
from .Options import RE2ROptions
from .WeaponRandomizer import WeaponRandomizer


Data.load_data('leon', 'a')
Data.load_data('leon', 'b')
Data.load_data('claire', 'a')
Data.load_data('claire', 'b')


class RE2RLocation(Location):
    def stack_names(*area_names):
        return " - ".join(area_names)
    
    def stack_names_not_victory(*area_names):
        if area_names[-1] == "Victory": return area_names[-1]

        return RE2RLocation.stack_names(*area_names)

    def is_item_forbidden(item, location_data, current_item_rule):
        return current_item_rule and ('forbid_item' not in location_data or item.name not in location_data['forbid_item'])


class ResidentEvil2Remake(World):
    """
    'Leon, I am your father.' - Billy Birkin, probably
    """
    game: str = "Resident Evil 2 Remake"

    data_version = 2
    required_client_version = (0, 4, 4)
    apworld_release_version = "0.2.5" # defined to show in spoiler log

    item_id_to_name = { item['id']: item['name'] for item in Data.item_table }
    item_name_to_id = { item['name']: item['id'] for item in Data.item_table }
    item_name_to_item = { item['name']: item for item in Data.item_table }
    location_id_to_name = { loc['id']: RE2RLocation.stack_names(loc['region'], loc['name']) for loc in Data.location_table }
    location_name_to_id = { RE2RLocation.stack_names(loc['region'], loc['name']): loc['id'] for loc in Data.location_table }
    location_name_to_location = { RE2RLocation.stack_names(loc['region'], loc['name']): loc for loc in Data.location_table }
    source_locations = {} # this is used to seed the initial item pool from original items, and is indexed by player as lname:loc locations

    # de-dupe the item names for the item group name
    item_name_groups = { key: set(values) for key, values in Data.item_name_groups.items() }

    # keep track of the weapon randomizer settings for use in various steps and in slot data
    starting_weapon = {}
    replacement_weapons = {}
    replacement_ammo = {}

    options_dataclass = RE2ROptions
    options: RE2ROptions

    def generate_early(self): # check weapon randomization before locations and items are processed, so we can swap non-randomized items as well
        # start with the normal locations per player for pool, then overwrite with weapon rando if needed
        self.source_locations[self.player] = self._get_locations_for_scenario(self._get_character(), self._get_scenario()) # id:loc combo
        self.source_locations[self.player] = { 
            RE2RLocation.stack_names(l['region'], l['name']): { **l, 'id': i } 
                for i, l in self.source_locations[self.player].items() 
        } # turn it into name:loc instead

        # if any of the "Oops! All X" weapon options are present, don't bother with weapon randomization since they'll all get overwritten
        #    and since starting with pistol is important to prevent softlock at Gator with all knives
        if self._format_option_text(self.options.oops_all_rockets) == 'True' or \
            self._format_option_text(self.options.oops_all_grenades) == 'True' or \
            self._format_option_text(self.options.oops_all_knives) == 'True':
            return

        weapon_rando = self._format_option_text(self.options.cross_scenario_weapons).lower()

        # if the user didn't pick any weapon randomization, skip all of this
        if weapon_rando == "none":
            return

        weapon_randomizer = WeaponRandomizer(self, self._get_character(), self._get_scenario())
        
        # if only randomizing the starting weapon, replace it and all of its ammo
        if weapon_rando == "starting": 
            weapon_randomizer.starting()
        elif weapon_rando == "match": 
            weapon_randomizer.match()
        elif weapon_rando == "full": 
            weapon_randomizer.full()
        elif weapon_rando == "all": 
            weapon_randomizer.all()
        elif weapon_rando == "full ammo": 
            weapon_randomizer.full_ammo()
        # all ammo and troll are identical, except there's a step after upgrades are placed for all weapons to remove all but a few weapons
        # so just do all_ammo here, then call the actual troll option after upgrades + gunpowder + whatever else
        elif weapon_rando == "all ammo" or weapon_rando == "troll" or weapon_rando == "troll starting": 
            weapon_randomizer.all_ammo()
        else:
            raise "Invalid weapon randomizer value!"

        weapon_randomizer.upgrades() # always swap upgrades after weapons are rando'd
        weapon_randomizer.high_grade_gunpowder() # always split high-grade gunpowder after weapons are rando'd

        if weapon_rando == "troll":
            weapon_randomizer.troll()
        if weapon_rando == "troll starting":
            weapon_randomizer.troll_starting()

    def create_regions(self): # and create locations
        scenario_locations = { l['id']: l for _, l in self.source_locations[self.player].items() }
        scenario_regions = self._get_region_table_for_scenario(self._get_character(), self._get_scenario())

        regions = [
            Region(region['name'], self.player, self.multiworld) 
                for region in scenario_regions
        ]
        
        for region in regions:
            region.locations = [
                RE2RLocation(self.player, RE2RLocation.stack_names_not_victory(region.name, location['name']), location['id'], region) 
                    for _, location in scenario_locations.items() if location['region'] == region.name
            ]
            region_data = [scenario_region for scenario_region in scenario_regions if scenario_region['name'] == region.name][0]
            
            for location in region.locations:
                location_data = scenario_locations[location.address]
                
                # if location has an item that should be forced there, place that. for cases where the item to place differs from the original.
                if 'force_item' in location_data and location_data['force_item']:
                    location.place_locked_item(self.create_item(location_data['force_item']))
                # if location is marked not rando'd, place its original item. 
                # if/elif here allows force_item + randomized=0, since a forced item is technically not randomized, but don't need to trigger both.
                elif 'randomized' in location_data and location_data['randomized'] == 0:
                    location.place_locked_item(self.create_item(location_data["original_item"]))
                # if location is not force_item'd or not not randomized, check for Labs progression option and apply
                # since Labs progression option doesn't matter for force_item'd or not randomized locations
                # we check for zone id > 3 because 3 is typically Sewers, and anything beyond that is Labs / endgame stuff
                elif self._format_option_text(self.options.allow_progression_in_labs) == 'False' and region_data['zone_id'] > 3:
                    location.item_rule = lambda item: not item.advancement
                # END if

                if 'forbid_item' in location_data and location_data['forbid_item']:
                    current_item_rule = location.item_rule or None

                    if not current_item_rule:
                        current_item_rule = lambda x: True

                    location.item_rule = lambda item, location_data=location_data: RE2RLocation.is_item_forbidden(item, location_data, current_item_rule)

                # now, set rules for the location access
                if "condition" in location_data and "items" in location_data["condition"]:
                    set_rule(location, lambda state, loc=location, loc_data=location_data: self._has_items(state, loc_data["condition"].get("items", [])))

            self.multiworld.regions.append(region)
                
        for connect in self._get_region_connection_table_for_scenario(self._get_character(), self._get_scenario()):
            # skip connecting on a one-sided connection because this should not be reachable backwards (and should be reachable otherwise)
            if 'limitation' in connect and connect['limitation'] in ['ONE_SIDED_DOOR']:
                continue

            from_name = connect['from'] if 'Menu' not in connect['from'] else 'Menu'
            to_name = connect['to'] if 'Menu' not in connect['to'] else 'Menu'

            region_from = self.multiworld.get_region(from_name, self.player)
            region_to = self.multiworld.get_region(to_name, self.player)
            ent = region_from.connect(region_to)

            if "condition" in connect and "items" in connect["condition"]:
                set_rule(ent, lambda state, en=ent, conn=connect: self._has_items(state, conn["condition"].get("items", [])))

        # Uncomment the below to see a connection of the regions (and their locations) for any scenarios you're testing.
        # visualize_regions(self.multiworld.get_region("Menu", self.player), "region_uml")

        # Place victory and set the completion condition for having victory
        self.multiworld.get_location("Victory", self.player) \
            .place_locked_item(self.create_item("Victory"))

        self.multiworld.completion_condition[self.player] = lambda state: self._has_items(state, ['Victory'])

    def create_items(self):
        scenario_locations = self.source_locations[self.player]

        pool = [
            self.create_item(item['name'] if item else None) for item in [
                self.item_name_to_item[location['original_item']] if location.get('original_item') else None
                    for _, location in scenario_locations.items()
            ]
        ]

        pool = [item for item in pool if item is not None] # some of the locations might not have an original item, so might not create an item for the pool

        # remove any already-placed items from the pool (forced items, etc.)
        for filled_location in self.multiworld.get_filled_locations(self.player):
            if filled_location.item.code and filled_location.item in pool: # not id... not address... "code"
                pool.remove(filled_location.item)

        # check the starting hip pouches option and add as precollected, removing from pool and replacing with junk
        starting_hip_pouches = int(self.options.starting_hip_pouches)

        if starting_hip_pouches > 0:
            hip_pouches = [item for item in pool if item.name == 'Hip Pouch'] # 6 total in every campaign, I think

            # if the hip pouches option exceeds the number of hip pouches in the pool, reduce it to the number in the pool
            if starting_hip_pouches > len(hip_pouches):
                starting_hip_pouches = len(hip_pouches)
                self.options.starting_hip_pouches.value = len(hip_pouches)

            for x in range(starting_hip_pouches):
                self.multiworld.push_precollected(hip_pouches[x]) # starting inv
                pool.remove(hip_pouches[x])

        # check the starting ink ribbons option and add as precollected, removing from pool and replacing with junk
        starting_ink_ribbons = int(self.options.starting_ink_ribbons)

        if self._format_option_text(self.options.difficulty) == 'Hardcore' and starting_ink_ribbons > 0:
            ink_ribbons = [item for item in pool if item.name == 'Ink Ribbon'] # 12+ total in every campaign, I think

            # if the ink ribbons option exceeds the number of ink ribbons in the pool, reduce it to the number in the pool
            if starting_ink_ribbons > len(ink_ribbons):
                starting_ink_ribbons = len(ink_ribbons)
                self.options.starting_ink_ribbons.value = len(ink_ribbons)

            for x in range(starting_ink_ribbons):
                self.multiworld.push_precollected(ink_ribbons[x]) # starting inv
                pool.remove(ink_ribbons[x])

        # check the bonus start option and add some heal items and ammo packs as precollected / starting items
        if self._format_option_text(self.options.bonus_start) == 'True':
            for x in range(3): self.multiworld.push_precollected(self.create_item('First Aid Spray'))

            if self.player in self.starting_weapon:
                starting_weapon = self.starting_weapon[self.player]
                starting_weapon_ammo = self.item_name_to_item[starting_weapon].get('ammo')
                for x in range(4): self.multiworld.push_precollected(self.create_item(starting_weapon_ammo))
            else:
                for x in range(4): self.multiworld.push_precollected(self.create_item('Handgun Ammo'))

        # do all the "no X" options here so we have more empty spots to use for traps, if needed
        if self._format_option_text(self.options.no_first_aid_spray) == 'True':
            pool = self._replace_pool_item_with(pool, 'First Aid Spray', 'Wooden Boards')

        if self._format_option_text(self.options.no_green_herb) == 'True':
            pool = self._replace_pool_item_with(pool, 'Green Herb', 'Wooden Boards')

        if self._format_option_text(self.options.no_red_herb) == 'True':
            pool = self._replace_pool_item_with(pool, 'Red Herb', 'Wooden Boards')
        
        if self._format_option_text(self.options.no_gunpowder) == 'True':
            replaceables = set(item.name for item in pool if 'Gunpowder' in item.name)
            less_useful_items = set(
                item.name for item in pool 
                    if 'Boards' in item.name or 'Cassette' in item.name or ('Film' in item.name and 'Hiding Place' not in item.name) or item.name == 'Blue Herb'
            )

            for from_item in replaceables:
                to_item = self.random.choice(list(less_useful_items))
                pool = self._replace_pool_item_with(pool, from_item, to_item)

        # figure out which traps are enabled, then swap them in for low-priority items
        # do this before the "oops all X" options so we can make use of extra Handgun Ammo spots before they get replaced out
        traps = []

        if self._format_option_text(self.options.add_damage_traps) == 'True':
            for x in range(int(self.options.damage_trap_count)):
                traps.append(self.create_item("Damage Trap"))

        if self._format_option_text(self.options.add_poison_traps) == 'True':
            for x in range(int(self.options.poison_trap_count)):
                traps.append(self.create_item("Poison Trap"))

        if len(traps) > 0:
            # use these spots for replacement first, since they're entirely non-essential
            available_spots = [
                item for item in pool 
                    if 'Boards' in item.name or 'Cassette' in item.name or ('Film' in item.name and 'Hiding Place' not in item.name)
            ]
            self.random.shuffle(available_spots)

            # use these spots for replacement next, since they're lower priority but we don't want to use as many of them
            # for gunpowder, only target the small / normal gunpowders
            extra_spots = [
                item for item in pool 
                    if 'Handgun Ammo' in item.name or item.name == 'Gunpowder'
            ]
            self.random.shuffle(extra_spots)
               
            for spot in available_spots:
                if len(traps) == 0: break

                trap_to_place = traps.pop()
                pool.remove(spot)
                pool.append(trap_to_place)
                
            for spot in extra_spots:
                if len(traps) == 0: break

                trap_to_place = traps.pop()
                pool.remove(spot)
                pool.append(trap_to_place)

        # add extras for Clock Tower items or Medallions, if configured
        # doing this before "oops all X" to make use of extra Handgun Ammo spots, too
        if self._format_option_text(self.options.extra_clock_tower_items) == 'True':
            replaceables = [item for item in pool if 'Boards' in item.name or item.name == 'Handgun Ammo' or item.name == 'Large-Caliber Handgun Ammo']
            
            for x in range(3):
                pool.remove(replaceables[x])

            pool.append(self.create_item('Mechanic Jack Handle'))
            pool.append(self.create_item('Small Gear'))
            pool.append(self.create_item('Large Gear'))

        if self._format_option_text(self.options.extra_medallions) == 'True':
            replaceables = [item for item in pool if 'Boards' in item.name or item.name == 'Handgun Ammo' or item.name == 'Large-Caliber Handgun Ammo']
            
            for x in range(2):
                pool.remove(replaceables[x])

            pool.append(self.create_item('Lion Medallion'))
            pool.append(self.create_item('Unicorn Medallion'))

            # The A scenarios have Maiden forced to the Bolt Cutters vanilla location, which is guaranteed to be accessible.
            # B scenarios have it randomized, so add a second randomized Maiden.
            if self._get_scenario().lower() == 'b':
                pool.remove(replaceables[2]) # remove the 3rd item to make room for a 3rd medallion
                pool.append(self.create_item('Maiden Medallion'))

        if self._format_option_text(self.options.early_medallions) == 'True':
            medallions = {i: len([i2 for i2 in pool if i2.name == i.name]) for i in pool if i.name in ['Lion Medallion', 'Unicorn Medallion', 'Maiden Medallion']}

            for item_name, item_qty in medallions.items():
                if item_qty > 0:
                    self.multiworld.early_items[self.player][item_name] = item_qty
   

        # check the "Oops! All Rockets" option. From the option description:
        #     Enabling this swaps all weapons, weapon ammo, and subweapons to Rocket Launchers. 
        #     (Except progression weapons, of course.)
        if self._format_option_text(self.options.oops_all_rockets) == 'True':
            # leave the Anti-Tank Rocket on Tyrant alone so the player can finish the fight
            items_to_replace = [
                item for item in self.item_name_to_item.values() 
                if 'type' in item and item['type'] in ['Weapon', 'Subweapon', 'Ammo'] and item['name'] != 'Anti-tank Rocket'
            ]
            to_item_name = 'Single Use Rocket'

            for from_item in items_to_replace:
                pool = self._replace_pool_item_with(pool, from_item['name'], to_item_name)

            # Add Marvin's Knife back in. He gets cranky if you don't give him his knife.
            for item in pool:
                if item.name == to_item_name:
                    pool.remove(item)
                    pool.append(self.create_item("Combat Knife"))
                    break

        # check the "Oops! All Miniguns" option. From the option description:
        #     Enabling this swaps all weapons, weapon ammo, and subweapons to Rocket Launchers. 
        #     (Except progression weapons, of course.)
        if self._format_option_text(self.options.oops_all_miniguns) == 'True':
            # leave the Anti-Tank Rocket on Tyrant alone so the player can finish the fight
            items_to_replace = [
                item for item in self.item_name_to_item.values() 
                if 'type' in item and item['type'] in ['Weapon', 'Subweapon', 'Ammo'] and item['name'] != 'Anti-tank Rocket'
            ]
            to_item_name = 'Minigun'

            for from_item in items_to_replace:
                pool = self._replace_pool_item_with(pool, from_item['name'], to_item_name)

            # Add Marvin's Knife back in. He gets cranky if you don't give him his knife.
            for item in pool:
                if item.name == to_item_name:
                    pool.remove(item)
                    pool.append(self.create_item("Combat Knife"))
                    break


        # check the "Oops! All Grenades" option. From the option description:
        #     Enabling this swaps all weapons, weapon ammo, and subweapons to Grenades. 
        #     (Except progression weapons, of course.)
        if self._format_option_text(self.options.oops_all_grenades) == 'True':
            # leave the Anti-Tank Rocket on Tyrant alone so the player can finish the fight
            items_to_replace = [
                item for item in self.item_name_to_item.values() 
                if 'type' in item and item['type'] in ['Weapon', 'Subweapon', 'Ammo'] and item['name'] != 'Anti-tank Rocket'
            ]
            to_item_name = 'Hand Grenade'

            for from_item in items_to_replace:
                pool = self._replace_pool_item_with(pool, from_item['name'], to_item_name)

            # Add Marvin's Knife back in. He gets cranky if you don't give him his knife.
            for item in pool:
                if item.name == to_item_name:
                    pool.remove(item)
                    pool.append(self.create_item("Combat Knife"))
                    break

        # check the "Oops! All Knives" option. From the option description:
        #     Enabling this swaps all weapons, weapon ammo, and subweapons to Combat Knives. 
        #     (Except progression weapons, of course.)
        if self._format_option_text(self.options.oops_all_knives) == 'True':
            # leave the Anti-Tank Rocket on Tyrant alone so the player can finish the fight
            items_to_replace = [
                item for item in self.item_name_to_item.values() 
                if 'type' in item and item['type'] in ['Weapon', 'Subweapon', 'Ammo'] and item['name'] != 'Anti-tank Rocket'
            ]
            to_item_name = 'Combat Knife'

            for from_item in items_to_replace:
                pool = self._replace_pool_item_with(pool, from_item['name'], to_item_name)


        # if the number of unfilled locations exceeds the count of the pool, fill the remainder of the pool with extra maybe helpful items
        missing_item_count = len(self.multiworld.get_unfilled_locations(self.player)) - len(pool)

        if missing_item_count > 0:
            for x in range(missing_item_count):
                pool.append(self.create_item('Blue Herb'))

        # Make any items that result in a really quick BK either early or local items, so the BK time is reduced
        early_items = {}       

        for item_name, item_qty in early_items.items():
            if item_qty > 0:
                self.multiworld.early_items[self.player][item_name] = item_qty

        local_items = {}       
        local_items["Fuse - Main Hall"] = len([i for i in pool if i.name == "Fuse - Main Hall"])

        for item_name, item_qty in local_items.items():
            if item_qty > 0:
                self.options.local_items.value.add(item_name)

        self.multiworld.itempool += pool
            
    def create_item(self, item_name: str) -> Item:
        if not item_name: return

        item = self.item_name_to_item[item_name]

        if item.get('progression', False):
            classification = ItemClassification.progression
        elif item.get('type', None) not in ['Lore', 'Trap']:
            classification = ItemClassification.useful
        elif item.get('type', None) == 'Trap':
            classification = ItemClassification.trap
        else: # it's Lore
            classification = ItemClassification.filler

        new_item = Item(item['name'], classification, item['id'], player=self.player)
        return new_item

    def get_filler_item_name(self) -> str:
        return "Wooden Boards"

    def fill_slot_data(self) -> Dict[str, Any]:
        slot_data = {
            "character": self._get_character(),
            "scenario": self._get_scenario(),
            "difficulty": self._get_difficulty(),
            "unlocked_typewriters": self._format_option_text(self.options.unlocked_typewriters).split(", "),
            "starting_weapon": self._get_starting_weapon(),
            "ammo_pack_modifier": self._format_option_text(self.options.ammo_pack_modifier),
            "damage_traps_can_kill": self._format_option_text(self.options.damage_traps_can_kill) == 'True',
            "death_link": self._format_option_text(self.options.death_link) == 'Yes' # why is this yes? lol
        }

        return slot_data
    
    def write_spoiler_header(self, spoiler_handle: TextIO):
        spoiler_handle.write(f"RE2R_AP_World version: {self.apworld_release_version}\n")

    def write_spoiler(self, spoiler_handle: typing.TextIO) -> None:
        # if weapons were randomized across scenarios, list what was swapped for what here (excluding upgrades, because who cares)
        if self._format_option_text(self.options.cross_scenario_weapons) != "None":
            starting_weapon = self.starting_weapon[self.player]
            spoiler_handle.write(f"\n\nWeapon Swaps ({self.multiworld.player_name[self.player]}):\n")
            spoiler_handle.write(f"\n{'(Starting Weapon)'.ljust(30, ' ')} -> {starting_weapon}")

            for from_weapon, to_weapon in self.replacement_weapons[self.player].items():
                # if the from weapon is a placeholder string of underscores, all of these were added (no "old" weapon)
                if re.match('^[_]+$', from_weapon):
                    from_weapon = '(Added)'

                if isinstance(to_weapon, list):
                    if not to_weapon:
                        spoiler_handle.write(f"\n{from_weapon.ljust(30, ' ')} -> :(")
                        continue

                    spoiler_handle.write(f"\n{from_weapon.ljust(30, ' ')} -> {to_weapon[0]}")

                    if len(to_weapon) > 1:
                        for weapon in to_weapon[1:]:
                            spoiler_handle.write(f"\n{''.ljust(30, ' ')} -> {weapon}")
                else:
                    spoiler_handle.write(f"\n{from_weapon.ljust(30, ' ')} -> {to_weapon}")
            
            spoiler_handle.write(f"\n\nAmmo Swaps ({self.multiworld.player_name[self.player]}):\n")

            for from_ammo, to_ammo in self.replacement_ammo[self.player].items():
                ammo_set = list(set(to_ammo))
                ammo_count = len([l for _, l in self.source_locations[self.player].items() if l.get('original_item', None) == ammo_set[0]])                    

                spoiler_handle.write(f"\n{from_ammo.ljust(30, ' ')} -> {ammo_set[0]} ({ammo_count})")

                if len(ammo_set) > 1:
                    for ammo in ammo_set[1:]:
                        ammo_count = len([l for _, l in self.source_locations[self.player].items() if l.get('original_item', None) == ammo])                    
                        spoiler_handle.write(f"\n{''.ljust(30, ' ')} -> {ammo} ({ammo_count})")

            spoiler_handle.write("\n\n(Ammo totals are for the whole campaign, not per swap/category.)")

    def _has_items(self, state: CollectionState, item_names: list) -> bool:
        # if there are no item requirements, this location is open, they "have the items needed"
        if len(item_names) == 0:
            return True

        # if the requirements are a single set of items, make it a list of a single set of items to support looping for multiple sets (below)
        if len(item_names) > 0 and type(item_names[0]) is not list:
            item_names = [item_names]

        for set_of_requirements in item_names:
            # if it requires all unique items, just do a state has all
            if len(set(set_of_requirements)) == len(set_of_requirements):
                if state.has_all(set_of_requirements, self.player):
                    return True
            # else, it requires some duplicates, so let's group them up and do some has w/ counts
            else:
                item_counts = {
                    item_name: len([i for i in set_of_requirements if i == item_name]) for item_name in set_of_requirements # e.g., { Spare Key: 2 }
                }
                missing_an_item = False

                for item_name, count in item_counts.items():
                    if not state.has(item_name, self.player, count):
                        missing_an_item = True

                if missing_an_item:
                    continue # didn't meet these requirements, so skip to the next set, if any
                
                # if we made it here, state has all the items and the quantities needed, return True
                return True

        # if we made it here, state didn't have enough to return True, so return False
        return False

    def _format_option_text(self, option) -> str:
        return re.sub(r'\w+\(', '', str(option)).rstrip(')')
    
    def _get_locations_for_scenario(self, character, scenario) -> dict:
        locations_pool = {
            loc['id']: loc for _, loc in self.location_name_to_location.items()
                if loc['character'] == character and loc['scenario'] == scenario
        }

        # if the player chose hardcore, take out any matching standard difficulty locations
        if self._format_option_text(self.options.difficulty) == 'Hardcore':
            for hardcore_loc in [loc for loc in locations_pool.values() if loc['difficulty'] == 'hardcore']:
                check_loc_region = re.sub(r'H\)$', ')', hardcore_loc['region']) # take the Hardcore off the region name
                check_loc_name = hardcore_loc['name']

                # if there's a standard location with matching name and region, it's obsoleted in hardcore, remove it
                standard_locs = [id for id, loc in locations_pool.items() if loc['region'] == check_loc_region and loc['name'] == check_loc_name and loc['difficulty'] != 'hardcore']

                if len(standard_locs) > 0:
                    del locations_pool[standard_locs[0]]

        # else, the player is still playing standard, take out all of the matching hardcore difficulty locations
        else:
            locations_pool = {
                id: loc for id, loc in locations_pool.items() if loc['difficulty'] != 'hardcore'
            }

        # now that we've factored in hardcore swaps, remove any hardcore locations that were just there for removing unused standard ones
        locations_pool = { id: loc for id, loc in locations_pool.items() if 'remove' not in loc }
        
        return locations_pool

    def _get_region_table_for_scenario(self, character, scenario) -> list:
        return [
            region for region in Data.region_table 
                if region['character'] == character and region['scenario'] == scenario
        ]
    
    def _get_region_connection_table_for_scenario(self, character, scenario) -> list:
        return [
            conn for conn in Data.region_connections_table
                if conn['character'] == character and conn['scenario'] == scenario
        ]
    
    def _get_character(self) -> str:
        return self._format_option_text(self.options.character).lower()
    
    def _get_scenario(self) -> str:
        return self._format_option_text(self.options.scenario).lower()
    
    def _get_difficulty(self) -> str:
        return self._format_option_text(self.options.difficulty).lower()
    
    def _get_starting_weapon(self) -> str:
        return self.starting_weapon[self.player] if self.player in self.starting_weapon else None
    
    def _replace_pool_item_with(self, pool, from_item_name, to_item_name) -> list:
        items_to_remove = [item for item in pool if item.name == from_item_name]
        count_of_new_items = len(items_to_remove)

        for item in items_to_remove:
            pool.remove(item)

        for x in range(count_of_new_items):
            pool.append(self.create_item(to_item_name))

        return pool

    # def _output_items_and_locations_as_text(self):
    #     my_locations = [
    #         {
    #             'id': loc.address,
    #             'name': loc.name,
    #             'original_item': self.location_name_to_location[loc.name]['original_item'] if loc.name != "Victory" else "(Game Complete)"
    #         } for loc in self.multiworld.get_locations() if loc.player == self.player
    #     ]

    #     my_locations = set([
    #         "{} | {} | {}".format(loc['id'], loc['name'], loc['original_item'])
    #         for loc in my_locations
    #     ])
        
    #     my_items = [
    #         {
    #             'id': item.code,
    #             'name': item.name
    #         } for item in self.multiworld.get_items() if item.player == self.player
    #     ]

    #     my_items = set([
    #         "{} | {}".format(item['id'], item['name'])
    #         for item in my_items
    #     ])

    #     print("\n".join(sorted(my_locations)))
    #     print("\n".join(sorted(my_items)))

    #     raise BaseException("Done with debug output.")
