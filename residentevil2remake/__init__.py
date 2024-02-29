import re

from typing import Dict, Any

from BaseClasses import ItemClassification, Item, Location, Region, CollectionState
from worlds.AutoWorld import World
from ..generic.Rules import set_rule
from Fill import fill_restrictive

from .Data import Data
from .Options import re2roptions


Data.load_data('leon', 'a')
# can add other scenarios like that once they're ready, too, like:
# Data.load_data('claire', 'b')


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

    item_id_to_name = { item['id']: item['name'] for item in Data.item_table }
    item_name_to_id = { item['name']: item['id'] for item in Data.item_table }
    item_name_to_item = { item['name']: item for item in Data.item_table }
    location_id_to_name = { loc['id']: RE2RLocation.stack_names(loc['region'], loc['name']) for loc in Data.location_table }
    location_name_to_id = { RE2RLocation.stack_names(loc['region'], loc['name']): loc['id'] for loc in Data.location_table }
    location_name_to_location = { RE2RLocation.stack_names(loc['region'], loc['name']): loc for loc in Data.location_table }

    option_definitions = re2roptions

    def create_regions(self): # and create locations
        scenario_locations = self._get_locations_for_scenario(self._get_character(), self._get_scenario())
        regions = [
            Region(region['name'], self.player, self.multiworld) 
                for region in self._get_region_table_for_scenario(self._get_character(), self._get_scenario())
        ]
        
        for region in regions:
            region.locations = [
                RE2RLocation(self.player, RE2RLocation.stack_names_not_victory(region.name, location['name']), location['id'], region) 
                    for _, location in scenario_locations.items() if location['region'] == region.name
            ]
            
            for location in region.locations:
                location_data = scenario_locations[location.address]

                # if location has an item that should be forced there, place that. for cases where the item to place differs from the original.
                if 'force_item' in location_data and location_data['force_item']:
                    location.place_locked_item(self.create_item(location_data['force_item']))
                # if location is marked not rando'd, place its original item. 
                # if/elif here allows force_item + randomized=0, since a forced item is technically not randomized, but don't need to trigger both.
                elif 'randomized' in location_data and location_data['randomized'] == 0:
                    location.place_locked_item(self.create_item(location_data["original_item"]))              
                # END if

                # now, set rules for the location access
                if "condition" in location_data and "items" in location_data["condition"]:
                    set_rule(location, lambda state, loc=location, loc_data=location_data: self._has_items(state, loc_data["condition"].get("items", [])))

            self.multiworld.regions.append(region)
                
        for connect in self._get_region_connection_table_for_scenario(self._get_character(), self._get_scenario()):
            # skip connecting on a one-sided connection because this should not be reachable backwards (and should be reachable otherwise)
            if 'limitation' in connect and connect['limitation'] in ['ONE_SIDED_DOOR']:
                continue

            region_from = self.multiworld.get_region(connect['from'], self.player)
            region_to = self.multiworld.get_region(connect['to'], self.player)
            ent = region_from.connect(region_to)

            if "condition" in connect and "items" in connect["condition"]:
                set_rule(ent, lambda state, en=ent, conn=connect: self._has_items(state, conn["condition"].get("items", [])))

        #visualize_regions(self.multiworld.get_region("Menu", self.player), "region_uml")

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

        # all that changes in hardcore item-wise is that ammo/gunpowder pool is reduced slightly to fit ink ribbons
        if self._format_option_text(self.multiworld.difficulty[self.player]) == 'Hardcore':
            handgun_ammo = [item for item in pool if item.name == 'Handgun Ammo'] # 40 total in LA
            gunpowder = [item for item in pool if item.name == 'Gunpowder'] # 17 total in LA
            blue_herbs = [item for item in pool if item.name == 'Blue Herb'] # 11 total in LA

            # vanilla provides 27-29 saves across X ribbons giving 2-3
            # rando could do either 27/30 (3 per for 9/10 total) or 24 (2 per for 12 total), higher item density seems better
            # original total for 3 items above is 68, so do same proportions but for 12 instead:
            # so swapping out 7 ammo, 3 gunpowder, 2 blue herb each for an ink ribbon (2 uses) per

            for x in range(7):
                pool.remove(handgun_ammo[x])
                pool.append(self.create_item('Ink Ribbon'))

            for x in range(3):
                pool.remove(gunpowder[x])
                pool.append(self.create_item('Ink Ribbon'))

            for x in range(2):
                pool.remove(blue_herbs[x])
                pool.append(self.create_item('Ink Ribbon'))

        # check the starting hip pouches option and add as precollected, removing from pool and replacing with junk
        starting_hip_pouches = int(self.multiworld.starting_hip_pouches[self.player])

        if starting_hip_pouches > 0:
            hip_pouches = [item for item in pool if item.name == 'Hip Pouch'] # 6 total in every campaign, I think

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
            to_item_name = 'Anti-tank Rocket'

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
            "unlocked_typewriters": self._format_option_text(self.multiworld.unlocked_typewriters[self.player]).split(", ")
        }

        return slot_data

    def _has_items(self, state: CollectionState, item_names: list) -> bool:
        return state.has_all(item_names, self.player)

    def _format_option_text(self, option) -> str:
        return re.sub('\w+\(', '', str(option)).rstrip(')')
    
    def _get_locations_for_scenario(self, character, scenario) -> dict:
        return {
            loc['id']: loc for _, loc in self.location_name_to_location.items()
                if loc['character'] == character and loc['scenario'] == scenario
        }

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
