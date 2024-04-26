import math
from typing import Optional

class WeaponRandomizer():
    def __init__(self, world, character, scenario):
        self.world = world
        self.random = world.random
        self.character = character
        self.scenario = scenario

        self.weapons_by_level = {
            'light': [item for item in world.item_name_to_item.values() if item.get('type') == 'Weapon' and 'light_gun' in item.get('groups', [])],
            'medium': [item for item in world.item_name_to_item.values() if item.get('type') == 'Weapon' and 'medium_gun' in item.get('groups', [])],
            'heavy': [item for item in world.item_name_to_item.values() if item.get('type') == 'Weapon' and 'heavy_gun' in item.get('groups', [])]
        }
        # ammo == None only applies for endgame items, which we want to avoid randomizing into the location of normal weapons
        self.all_weapons = [item for item in world.item_name_to_item.values() if item.get('type') == 'Weapon' and item.get('ammo', None) != None]
        self.starting_ammo_name = 'Handgun Ammo'

    ###
    # CrossScenarioWeapons == "Starting"
    ###
    def starting(self):
        random_weapon = self._determine_starting_weapon()
        self._swap_item_at_locations(self.starting_ammo_name, random_weapon['ammo'], "Ammo")

    ###
    # CrossScenarioWeapons == "Match"
    ###
    def match(self):
        self._determine_starting_weapon('light') # match starting weapon level too
        weapons = self._get_weapons_from_locations()
        
        for weapon in weapons:
            for key in self.weapons_by_level.keys():
                if "groups" in weapon and "{}_gun".format(key) in weapon["groups"]: 
                    matched = self.random.choice(self.weapons_by_level[key])
                
                    self._swap_item_at_locations(weapon['name'], matched['name'], "Weapon")
                    self._swap_item_at_locations(weapon['ammo'], matched['ammo'], "Ammo")

                    # remove anything that was placed so it's not placed again
                    self.weapons_by_level[key] = [i for i in self.weapons_by_level[key] if i['name'] != matched['name']]

    ###
    # CrossScenarioWeapons == "Full"
    ###
    def full(self, include_ammo: Optional[bool] = True):
        self._determine_starting_weapon()
        weapons = self._get_weapons_from_locations()

        for weapon in weapons:
            matched = self.random.choice(self.all_weapons)

            self._swap_item_at_locations(weapon['name'], matched['name'], "Weapon")

            # by default, this includes ammo. for options that rando ammo completely, this will be False
            if include_ammo:
                self._swap_item_at_locations(weapon['ammo'], matched['ammo'], "Ammo")

            # remove anything that was placed so it's not placed again
            self.all_weapons = [i for i in self.all_weapons if i['name'] != matched['name']]

    ###
    # CrossScenarioWeapons == "All"
    ###
    def all(self, include_ammo: Optional[bool] = True):
        self._determine_starting_weapon()
        weapons = self._get_weapons_from_locations()

        # replace the base weapons...
        for weapon in weapons:
            matched = self.random.choice(self.all_weapons)
            self._swap_item_at_locations(weapon['name'], matched['name'], "Weapon")

            # remove anything that was placed so it's not placed again
            self.all_weapons = [i for i in self.all_weapons if i['name'] != matched['name']]

        # count for repeating identifier for spoiler log
        str_repeat_count = 1

        # ... then place all the remaining weapons
        for loc in self._get_locations_for_extra_weapons():
            if len(self.all_weapons) == 0:
                break

            matched = self.random.choice(self.all_weapons)

            loc['original_item'] = matched['name']
            loc_key = self._get_location_key(loc['region'], loc['name'])
            self.world.location_name_to_location[loc_key] = loc

            self.world.replacement_weapons["_" * str_repeat_count] = matched['name']
            str_repeat_count += 1

            # remove anything that was placed so it's not placed again
            self.all_weapons = [i for i in self.all_weapons if i['name'] != matched['name']]

        if include_ammo:
            self._split_ammo_by_level()

    ###
    # CrossScenarioWeapons == "Full Ammo"
    ###    
    def full_ammo(self):
        self.full(include_ammo=False)
        self._split_ammo_randomly()

    ###
    # CrossScenarioWeapons == "All Ammo"
    ###
    def all_ammo(self):
        self.all(include_ammo=False)
        self._split_ammo_randomly()

    ###
    # CrossScenarioWeapons == "Troll"
    ###
    def troll(self):
        # self.all_ammo() is called during processing of options, and self.troll() is specifically called after upgrades, gunpowder, etc.

        weapons = [w for w in self._get_weapons_from_locations() if w['name'] != self.world.starting_weapon]
        only_weapons = [self.world.item_name_to_item.get(self.world.starting_weapon)]

        for _ in range(2):
            random_weapon = self.random.choice(weapons)
            only_weapons.append(random_weapon)
            weapons = [w for w in weapons if w['name'] != random_weapon]

        self.world.replacement_weapons = {"Other Random Weapons": "Play and find out :)"}

    ###
    # Function to be called after ANY weapon rando, so that the upgrades for the included weapons are also included
    ###
    def upgrades(self):
        all_upgrades = [item for item in self.world.item_name_to_item.values() if item.get('type') == 'Upgrade']

        # Now, find all upgrade items (orig or force) on locations that aren't randomized=0, add those locations to list to swap,
        #    and swap their orig & force to an upgrade at random for one of the new random weapons.
        #    Then, fill in any gaps with the first value in replacement ammo to match the starting weapon's ammo.
        location_names_with_upgrades = []
        available_upgrades = [item["name"] for item in all_upgrades if item.get('upgrades') in self.world.replacement_weapons.values()] # match to new weapons

        # NEED TO CHECK LOCATIONS BELOW TO MAKE SURE THEY'RE ACTUALLY RANDO'D
        # (i.e., L-Hawk Laser Sight)

        for loc_name, loc in {k: l for k, l in self.world.location_name_to_location.items() if l['character'] == self.character and l['scenario'] == self.scenario}.items():
            original_item = loc.get("original_item", None)
            original_item = self.world.item_name_to_item.get(original_item, {})

            force_item = loc.get("force_item", None)
            force_item = self.world.item_name_to_item.get(force_item, {})

            if original_item.get("type") == "Upgrade" or force_item.get("type") == "Upgrade":
                # if the location isn't randomized, it means that the original item (upgrade) is likely not able to be randomized
                #    so, leave the upgrade there, and remove that upgrade from the available upgrades so we don't try to place it again
                if loc.get("randomized", 1) == 0:
                    available_upgrades = [i for i in available_upgrades if i != original_item['name']]

                    continue

                location_names_with_upgrades.append(loc_name)

        if len(available_upgrades) > 0:
            extra_locations_needed = len(available_upgrades) - len(location_names_with_upgrades)

            if extra_locations_needed > 0:
                available_locations_for_extra = self._get_locations_for_extra_weapons()

                for x in range(extra_locations_needed):
                    loc = available_locations_for_extra[x]
                    loc_key = self._get_location_key(loc['region'], loc['name'])
                    location_names_with_upgrades.append(loc_key)

        if len(location_names_with_upgrades) > 0:
            extra_upgrades_needed = len(location_names_with_upgrades) - len(available_upgrades)

            if extra_upgrades_needed > 0:
                for x in range(extra_upgrades_needed):
                    replacement_item = list(self.world.replacement_ammo.values())[0]

                    if isinstance(replacement_item, list):
                        replacement_item = replacement_item[0]

                    available_upgrades.append(replacement_item)

        for loc_name in location_names_with_upgrades:
            if self.world.location_name_to_location[loc_name].get("force_item"):
                self.world.location_name_to_location[loc_name]["force_item"] = available_upgrades.pop(0)
            elif self.world.location_name_to_location[loc_name].get("original_item"):
                self.world.location_name_to_location[loc_name]["original_item"] = available_upgrades.pop(0)

    ###
    # Function to be called after ANY weapon rando, so that the high-grade gunpowder is split to support any weapon's ammo
    ###
    def high_grade_gunpowder(self):
        location_names_with_hgg = [] # hgg = high grade gunpowder

        # Finally, find all high grade gunpowder in the scenario, and split it half-and-half between white and yellow.
        #    To account for any possible weapons that show up in the scenario.
        for loc_name, loc in {k: l for k, l in self.world.location_name_to_location.items() if l['character'] == self.character and l['scenario'] == self.scenario}.items():
            original_item = loc.get("original_item", "")
            force_item = loc.get("force_item", "")

            if "High-Grade Gunpowder" in original_item or "High-Grade Gunpowder" in force_item:
                location_names_with_hgg.append(loc_name)

        # Alternate back and forth playing Yellow and White
        counter = 0
        for loc_name in location_names_with_hgg:
            if counter % 2 == 0:
                if self.world.location_name_to_location[loc_name].get("original_item"):
                    self.world.location_name_to_location[loc_name]["original_item"] = "High-Grade Gunpowder - Yellow"
                
                if self.world.location_name_to_location[loc_name].get("force_item"):
                    self.world.location_name_to_location[loc_name]["force_item"] = "High-Grade Gunpowder - Yellow"
            else:
                if self.world.location_name_to_location[loc_name].get("original_item"):
                    self.world.location_name_to_location[loc_name]["original_item"] = "High-Grade Gunpowder - White"
                
                if self.world.location_name_to_location[loc_name].get("force_item"):
                    self.world.location_name_to_location[loc_name]["force_item"] = "High-Grade Gunpowder - White"

            counter = counter + 1

    #################
    # Private methods for various tasks that each setting might need to do
    #################

    def _determine_starting_weapon(self, level: Optional[str] = None) -> dict:
        weapon_list = self.all_weapons

        if level:
            weapon_list = self.weapons_by_level[level]

        # pick random starting weapon and set for later slot data
        random_weapon = self.random.choice(weapon_list)
        self.world.starting_weapon = random_weapon["name"]
        # starting weapon isn't on a location, so no need to set replacement; but set replacement for ammo
        self.world.replacement_ammo[self.starting_ammo_name] = random_weapon["ammo"]

        # remove the starting
        self.all_weapons = [i for i in self.all_weapons if i['name'] != random_weapon['name']]

        for weapon_level in self.weapons_by_level.keys():
            self.weapons_by_level[weapon_level] = [i for i in self.weapons_by_level[weapon_level] if i['name'] != random_weapon['name']]

        return random_weapon

    def _swap_item_at_locations(self, old_item: str, new_item: str, item_type: str):
        for loc_name, loc in self._get_locations().items():
            # if the location has already been swapped, don't swap it again
            if loc.get('swapped', None) == True:
                continue

            original_item = loc.get("original_item", None)
            original_item = self.world.item_name_to_item.get(original_item, {})
            force_item = loc.get("force_item", None)
            force_item = self.world.item_name_to_item.get(force_item, {})
            swapped = False

            if original_item.get('type') == item_type:
                if original_item.get('name', None) == old_item:
                    loc['original_item'] = new_item
                    swapped = True
            
            if force_item.get('type') == item_type:
                if force_item.get('name', None) == old_item:
                    loc['force_item'] = new_item
                    swapped = True

            # if anything was swapped, set the new location back
            if swapped:
                loc['swapped'] = True
                self.world.location_name_to_location[loc_name] = loc
        
        old_item = self.world.item_name_to_item.get(old_item, {})

        if old_item.get('type') == 'Weapon':
            self.world.replacement_weapons[old_item['name']] = new_item

        if old_item.get('type') == 'Ammo':
            self.world.replacement_ammo[old_item['name']] = new_item
        
    def _get_locations(self):
        return {k: l for k, l in self.world.location_name_to_location.items() if l['character'] == self.character and l['scenario'] == self.scenario}

    def _get_weapons_from_locations(self):
        weapons = []

        for _, loc in self._get_locations().items():
            original_item = loc.get("original_item", None)
            original_item = self.world.item_name_to_item.get(original_item, {})

            if original_item.get("type") == "Weapon" and original_item.get("ammo", None):
                if original_item not in weapons:
                    weapons.append(original_item)

                continue

            force_item = loc.get("force_item", None)
            force_item = self.world.item_name_to_item.get(force_item, {})

            if force_item.get("type") == "Weapon" and force_item.get("ammo", None):
                if force_item in weapons:
                    weapons.append(force_item)

                continue

        return weapons
    
    def _get_locations_for_extra_weapons(self) -> list:
        available_locations = []
        locations = list(self._get_locations().values())
        self.random.shuffle(locations)

        for loc in locations:
            # if the location has already been swapped, don't swap it again
            if loc.get('swapped', None) == True:
                continue

            # only use locations that don't have an item forced there and are randomized
            if loc.get('force_item') or loc.get('randomized') == 0:
                continue

            if loc.get('original_item') in ['Handgun Ammo', 'Wooden Boards', 'Blue Herb']:
                available_locations.append(loc)

        return available_locations
    
    def _get_locations_having(self, item_name: str) -> list:
        return [loc for _, loc in self._get_locations().items() if loc.get('original_item') == item_name]

    def _split_ammo_by_level(self, level: Optional[str] = None):
        levels = self.weapons_by_level.keys()

        if level:
            levels = [level]
        else:
            self.world.replacement_ammo = {} # if we're splitting all ammo by level, this includes starting, so remove it and anything else

        weapons_at_locations = [self.world.item_name_to_item.get(w.get('name')) for w in self._get_weapons_from_locations()]
        weapons_at_locations = [w for w in weapons_at_locations if w.get('name') in self.world.replacement_weapons.values()]
        starting_weapon = self.world.item_name_to_item.get(self.world.starting_weapon)
        weapons_at_locations.append(starting_weapon)

        placed_weapons_by_level = {
            'light': [w for w in weapons_at_locations if 'light_gun' in w['groups']],
            'medium': [w for w in weapons_at_locations if 'medium_gun' in w['groups']],
            'heavy': [w for w in weapons_at_locations if 'heavy_gun' in w['groups']]
        }
        needed_ammo_by_level = {
            'light': [],
            'medium': [],
            'heavy': []
        }
        placed_ammo_by_level = {
            'light': [],
            'medium': [],
            'heavy': []
        }
        
        for level, weapons in placed_weapons_by_level.items():
            for weapon in weapons:
                needed_ammo_by_level[level].append(weapon['ammo'])
                placed_ammo_by_level[level].extend(self._get_locations_having(weapon['ammo']))

            # de-dupe the ammo list
            needed_ammo_by_level[level] = list(set(needed_ammo_by_level[level]))

        for lev in levels:
            # take the amount of locations with ammo and divide by the number of ammo types, rounding down
            level_total = len(needed_ammo_by_level[lev])
            each_amount = math.floor(len(placed_ammo_by_level[lev]) / level_total)
            count = 0

            # loop over all the placed ammo, and update it to the correct ammo split based on the count
            # 0 to count is first ammo, count to count x 2 is second, etc. Last one might get extra because rounded down.
            for loc in placed_ammo_by_level[lev]:
                index = math.floor(count / each_amount)

                if index + 1 >= level_total:
                    index = level_total - 1
                
                loc['original_item'] = needed_ammo_by_level[lev][index]
                loc_key = self._get_location_key(loc['region'], loc['name'])
                self.world.location_name_to_location[loc_key] = loc

                count += 1

            self.world.replacement_ammo["{} Weapon Ammo".format(lev.title())] = needed_ammo_by_level[lev]

    def _split_ammo_randomly(self):
        self.world.replacement_ammo = {} # all ammo is completely random, so skip starting listing(s) too

        placed_weapons = [self.world.item_name_to_item.get(w.get('name')) for w in self._get_weapons_from_locations()]
        starting_weapon = self.world.item_name_to_item.get(self.world.starting_weapon)
        placed_weapons.append(starting_weapon)

        needed_ammo = []
        placed_ammo = []
        
        for weapon in placed_weapons:
            needed_ammo.append(weapon['ammo'])

        for weapon in self.all_weapons:
            placed_ammo.extend(self._get_locations_having(weapon['ammo']))

        # de-dupe the ammo list
        needed_ammo = list(set(needed_ammo))

        # loop over all the placed ammo, and update it to a completely random ammo choice
        for loc in placed_ammo:
            loc['original_item'] = self.random.choice(needed_ammo)
            loc_key = self._get_location_key(loc['region'], loc['name'])
            self.world.location_name_to_location[loc_key] = loc

        self.world.replacement_ammo["Random Quantities"] = needed_ammo

    def _get_location_key(self, *location_parts):
        return " - ".join(location_parts)
