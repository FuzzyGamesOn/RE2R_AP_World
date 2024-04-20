import re
import random

from typing import Dict, Any, TextIO
from Utils import visualize_regions

from BaseClasses import ItemClassification, Item, Location, Region, CollectionState
from worlds.AutoWorld import World
from ..generic.Rules import set_rule
from Fill import fill_restrictive

from .Data import Data
from .Options import re2roptions


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

class ResidentEvil2Remake(World):
    """
    'Leon, I am your father.' - Billy Birkin, probably
    """
    game: str = "Resident Evil 2 Remake"

    data_version = 2
    required_client_version = (0, 4, 3)
    apworld_release_version = "0.2.0" # defined to show in spoiler log

    item_id_to_name = { item['id']: item['name'] for item in Data.item_table }
    item_name_to_id = { item['name']: item['id'] for item in Data.item_table }
    item_name_to_item = { item['name']: item for item in Data.item_table }
    location_id_to_name = { loc['id']: RE2RLocation.stack_names(loc['region'], loc['name']) for loc in Data.location_table }
    location_name_to_id = { RE2RLocation.stack_names(loc['region'], loc['name']): loc['id'] for loc in Data.location_table }
    location_name_to_location = { RE2RLocation.stack_names(loc['region'], loc['name']): loc for loc in Data.location_table }

    # de-dupe the item names for the item group name
    item_name_groups = { key: set(values) for key, values in Data.item_name_groups.items() }

    option_definitions = re2roptions

    def create_regions(self): # and create locations
        scenario_locations = self._get_locations_for_scenario(self._get_character(), self._get_scenario())
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
                elif self._format_option_text(self.multiworld.allow_progression_in_labs[self.player]) == 'False' and region_data['zone_id'] > 3:
                    location.item_rule = lambda item: item.classification != ItemClassification.progression and ItemClassification.progression_skip_balancing
                # END if

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
        scenario_locations = self._get_locations_for_scenario(self._get_character(), self._get_scenario())

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
        starting_hip_pouches = int(self.multiworld.starting_hip_pouches[self.player])

        if starting_hip_pouches > 0:
            hip_pouches = [item for item in pool if item.name == 'Hip Pouch'] # 6 total in every campaign, I think

            # if the hip pouches option exceeds the number of hip pouches in the pool, reduce it to the number in the pool
            if starting_hip_pouches > len(hip_pouches):
                starting_hip_pouches = len(hip_pouches)
                self.multiworld.starting_hip_pouches[self.player] = len(hip_pouches)

            for x in range(starting_hip_pouches):
                self.multiworld.push_precollected(hip_pouches[x]) # starting inv
                pool.remove(hip_pouches[x])

        # check the bonus start option and add some heal items and ammo packs as precollected / starting items
        if self._format_option_text(self.multiworld.bonus_start[self.player]) == 'True':
            for x in range(3): self.multiworld.push_precollected(self.create_item('First Aid Spray'))
            for x in range(4): self.multiworld.push_precollected(self.create_item('Handgun Ammo'))

        # check the "Oops! All Rockets" option. From the option description:
        #     Enabling this swaps all weapons, weapon ammo, and subweapons to Rocket Launchers. 
        #     (Except progression weapons, of course.)
        if self._format_option_text(self.multiworld.oops_all_rockets[self.player]) == 'True':
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

        # check the "Oops! All Grenades" option. From the option description:
        #     Enabling this swaps all weapons, weapon ammo, and subweapons to Grenades. 
        #     (Except progression weapons, of course.)
        if self._format_option_text(self.multiworld.oops_all_grenades[self.player]) == 'True':
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
        if self._format_option_text(self.multiworld.oops_all_knives[self.player]) == 'True':
            # leave the Anti-Tank Rocket on Tyrant alone so the player can finish the fight
            items_to_replace = [
                item for item in self.item_name_to_item.values() 
                if 'type' in item and item['type'] in ['Weapon', 'Subweapon', 'Ammo'] and item['name'] != 'Anti-tank Rocket'
            ]
            to_item_name = 'Combat Knife'

            for from_item in items_to_replace:
                pool = self._replace_pool_item_with(pool, from_item['name'], to_item_name)

        if self._format_option_text(self.multiworld.extra_clock_tower_items[self.player]) == 'True':
            replaceables = [item for item in pool if item.name == 'Handgun Ammo' or item.name == 'Blue Herb']
            
            for x in range(3):
                pool.remove(replaceables[x])

            pool.append(self.create_item('Mechanic Jack Handle'))
            pool.append(self.create_item('Small Gear'))
            pool.append(self.create_item('Large Gear'))

        if self._format_option_text(self.multiworld.extra_medallions[self.player]) == 'True':
            replaceables = [item for item in pool if item.name == 'Handgun Ammo' or item.name == 'Blue Herb']
            
            for x in range(2):
                pool.remove(replaceables[x])

            pool.append(self.create_item('Lion Medallion'))
            pool.append(self.create_item('Unicorn Medallion'))

            # The A scenarios have Maiden forced to the Bolt Cutters vanilla location, which is guaranteed to be accessible.
            # B scenarios have it randomized, so add a second randomized Maiden.
            if self._get_scenario().lower() == 'b':
                pool.remove(replaceables[2]) # remove the 3rd item to make room for a 3rd medallion
                pool.append(self.create_item('Maiden Medallion'))

        if self._format_option_text(self.multiworld.no_first_aid_spray[self.player]) == 'True':
            pool = self._replace_pool_item_with(pool, 'First Aid Spray', 'Wooden Boards')

        if self._format_option_text(self.multiworld.no_green_herb[self.player]) == 'True':
            pool = self._replace_pool_item_with(pool, 'Green Herb', 'Wooden Boards')

        if self._format_option_text(self.multiworld.no_red_herb[self.player]) == 'True':
            pool = self._replace_pool_item_with(pool, 'Red Herb', 'Wooden Boards')
        
        if self._format_option_text(self.multiworld.no_gunpowder[self.player]) == 'True':
            replaceables = set(item.name for item in pool if 'Gunpowder' in item.name)
            less_useful_items = set(
                item.name for item in pool 
                    if 'Boards' in item.name or 'Cassette' in item.name or 'Film' in item.name or item.name == 'Blue Herb'
            )

            for from_item in replaceables:
                to_item = random.choice(list(less_useful_items))
                pool = self._replace_pool_item_with(pool, from_item, to_item)

        # if the number of unfilled locations exceeds the count of the pool, fill the remainder of the pool with extra maybe helpful items
        missing_item_count = len(self.multiworld.get_unfilled_locations(self.player)) - len(pool)

        if missing_item_count > 0:
            for x in range(missing_item_count):
                pool.append(self.create_item('Blue Herb'))

        self.multiworld.itempool += pool
            
    def create_item(self, item_name: str) -> Item:
        if not item_name: return

        item = self.item_name_to_item[item_name]

        # double filler, but accounts for key missing and key set to 
        classification = ItemClassification.progression if 'progression' in item and item['progression'] \
                        else ItemClassification.useful if 'progression' in item and item['type'] not in ['Lore'] \
                        else ItemClassification.filler

        return Item(item['name'], classification, item['id'], player=self.player)

    def fill_slot_data(self) -> Dict[str, Any]:
        slot_data = {
            "character": self._get_character(),
            "scenario": self._get_scenario(),
            "difficulty": self._get_difficulty(),
            "unlocked_typewriters": self._format_option_text(self.multiworld.unlocked_typewriters[self.player]).split(", ")
        }

        return slot_data
    
    def write_spoiler_header(self, spoiler_handle: TextIO):
        spoiler_handle.write(f"RE2R_AP_World version: {self.apworld_release_version}\n")

    def _has_items(self, state: CollectionState, item_names: list) -> bool:
        # if it requires all unique items, just do a state has all
        if len(set(item_names)) == len(item_names):
            return state.has_all(item_names, self.player)
        # else, it requires some duplicates, so let's group them up and do some has w/ counts
        else:
            item_counts = {
                item_name: len([i for i in item_names if i == item_name]) for item_name in item_names # e.g., { Spare Key: 2 }
            }

            for item_name, count in item_counts.items():
                if not state.has(item_name, self.player, count):
                    return False
                
            return True

    def _format_option_text(self, option) -> str:
        return re.sub('\w+\(', '', str(option)).rstrip(')')
    
    def _get_locations_for_scenario(self, character, scenario) -> dict:
        locations_pool = {
            loc['id']: loc for _, loc in self.location_name_to_location.items()
                if loc['character'] == character and loc['scenario'] == scenario
        }

        # if the player chose hardcore, take out any matching standard difficulty locations
        if self._format_option_text(self.multiworld.difficulty[self.player]) == 'Hardcore':
            for hardcore_loc in [loc for loc in locations_pool.values() if loc['difficulty'] == 'hardcore']:
                check_loc_region = re.sub('H\)$', ')', hardcore_loc['region']) # take the Hardcore off the region name
                check_loc_name = hardcore_loc['name']

                # if there's a standard location with matching name and region, it's obsoleted in hardcore, remove it
                standard_locs = [id for id, loc in locations_pool.items() if loc['region'] == check_loc_region and loc['name'] == check_loc_name]

                if len(standard_locs) > 0:
                    del locations_pool[standard_locs[0]]

        # else, the player is still playing standard, take out all of the matching hardcore difficulty locations
        else:
            locations_pool = {
                id: loc for id, loc in locations_pool.items() if loc['difficulty'] != 'hardcore'
            }
            
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
        return self._format_option_text(self.multiworld.character[self.player]).lower()
    
    def _get_scenario(self) -> str:
        return self._format_option_text(self.multiworld.scenario[self.player]).lower()
    
    def _get_difficulty(self) -> str:
        return self._format_option_text(self.multiworld.difficulty[self.player]).lower()
    
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
