# RE2R Archipelago World
An Archipelago (AP) randomizer world for Resident Evil 2 Remake. Designed for use with the Archipelago client repository, which will be linked when it's ready.

## How to play an RE2R randomized world
This requires the RE2R Archipelago client here: https://github.com/FuzzyGamesOn/RE2R_AP_Client

## How to generate an RE2R randomized world
You can generate this AP world similar to any other:

1. Take the apworld file from the most recent Release here and put it in the `lib/worlds` folder of your normal Archipelago (AP) install.
2. Take the example YAML file from the most recent Release here and put it in the `Players` folder of your normal AP install.
3. In your normal AP install, run `ArchipelagoGenerate.exe`. It will place the generated multiworld in the `output` folder.
4. If you want to host the multiworld on the AP website, upload the zip that was generated in the `output` folder.
5. If you want to host the multiworld locally, run `ArchipelagoServer.exe` and choose the zip that was generated in the `output` folder.

## What scenarios does this support?
Currently, only Leon's 1st / A scenario is supported.

## How is the scenarios data structured?
All of the scenarios' data lives in the `data` folder. The structure of the data is:

- [Character folder](#character-folder)
  - [Scenarios folder](#scenarios-folder)
    - [Locations file](#locations-file)
    - [Regions file](#regions-file)
    - [Region Connections file](#region-connections-file)
    - [Typewriter List file](#typewriter-list-file)
  - [Item List file](#item-list-file)
  - [Region Zones file](#region-zones-file)

### Character folder
Each character is separated into its own folder to group their scenarios together.

---

#### Item List file
Each character's items are the same across scenarios. Some important fields to note:

##### Item Type
There are multiple item types to choose from:

- Key = These are high-priority gating items that unlock major progression
- Gating = These are low-priority gating items that unlock only a few locations
- Consumable = These are non-progression but likely useful items that are consumed on use
- Recovery = These are the same as Consumable, but further categorized as healing items
- Weapon = These are weapons that consume ammunition (so the Combat Knife is not included)
- Subweapon = These are weapons that do not consume ammunition, and many of these are throwable
- Ammo = These are all the ammo types for use with the Weapon item type
- Upgrade = These are all the weapon upgrades for use with the Weapon item type
- Lore = These are all non-progression, non-useful items that are classified as filler

##### Decimal
The decimal field is a decimal (base 10) representation of the item's in-game hex code. This is how the randomizer client translates a named item to an in-game item.

##### Count
The count field represents the quantity you receive each time the item is received, NOT the number of this item in the scenarios. In most cases, the count will be 1. For Weapons, the count is the starting ammo count for that weapon when received. For Ammo, the count is the amount of ammo received when you receive that "pack" of ammo.

##### Progression
If an item is marked as progression, it unlocks one or more locations. Typically, this will only be the case for the item types Key and Gating.

---

#### Region Zones file
Regions represent rooms, so zones represent groups of rooms, like RPD.

---

### Scenarios folder
Each scenario is separated into its own folder under the scenarios folder. Typically, each scenario has a different set of item locations, some different regions, and different ways that regions connect to each other.

---

#### Locations file
This is the most important part of the randomizer world. The locations and original items defined here directly impact what is randomized into the world, and the item object information is used by the randomizer client to track those location checks.

Some important fields to note:

##### Name and Region
These are combined into the location name, and the apworld customizes the region name to include the scenario suffix. The region name must match a region name in the Regions file.

##### Original Item
This is the item that is found at the location when playing through the vanilla game. When the apworld is generated, this item is added to the item pool for randomization.

##### Condition
This allows conditional logic for whether a location should be accessible. For instance, Locker 203 in the Safety Deposit Room requires both Spare Keys, so they are listed as a condition.

##### Item Object, Parent Object, and Folder Path
These three fields uniquely identify every location in the game. They are derived from game object names and field values from the game's code. Using these values, the randomizer client can identify the right named location to track.

To find these values, you can use [REF_Inspect](https://github.com/FuzzyGamesOn/REF_Inspect) and interact with the locations normally.

##### Force Item
This is an optional field and only included on some item entries. In some cases, we want to force a specific item to be placed at a specific location for a specific campaign, so we use this option and provide the name of the item to place.

##### Randomized
This is an optional field and only included on some item entries. In some cases, we want the location to keep its vanilla item, so we use this option. This option defaults to 1 (randomized), and 0 means not randomized.

##### ID and Victory
There must be exactly one Victory location (i.e., location that finishes the randomizer), and it is the only location that uses these fields. All location IDs are dynamically assigned unless provided, but Victory forces a non-dynamic ID. The Victory field is set to true to indicate that the location is the Victory location.

---

#### Regions file
This file lists all of the rooms (regions) in the game and what zone (area) they belong to. This file must always start with the Menu region.

---

#### Region Connections file
This file dictates how the randomizer connects each room (region) together. Currently, these connections must follow their vanilla connection and item requirements.

Some important fields to note:

##### From and To
Each of these must be set to a region name from the regions file. These define a forward connection *from* the From region *to* the To region. 

**Note: Since you can travel back along any connection you've previously traveled forward over, don't define two-way connections between regions. This will likely break logic because the logic will sometimes use the reverse connection to avoid the vanilla connection mentioned above.**

##### Condition
Similar to the Condition field in the regions file, this allows you to specify item requirements to traverse a region connection. This is the most common place to use the Condition field, for things like door keys, etc.

You will also notice that some major region connections (like going to RPD's Secret Room) include more items that are actually required to enter the connection. This forces the logic to provide the extra items before considering this connection to be in logic. (e.g., if you were defining Secret Room and only required the 3 Medallions, the randomizer could place all 3 Medallions in RPD's Main Room and expect you to leave RPD immediately, likely resulting in a hardlock at the G1 fight.)

##### Limitation
This is an optional field, and is currently only used to define a region connection as a one-sided connection (with the value "ONE_SIDED_DOOR"). This is commonly used for doors with latches or bolt cutter doors that you have to activate from one side to allow traversing.

**Note: One-sided connections are currently excluded from the randomizer because they may end up in logic on the reverse path, which can be unreachable. Similar issue as noted above with From and To. However, we want these defined in case we change this behavior later.**

---

#### Typewriter List file
This file defines all of the typewriter locations in the scenario. This is used for creating typewriter teleports in the randomizer client.

Some important fields to note:

##### Location ID, Map ID, and Item Object
These fields all uniquely identify a typewriter by field values and game object names from the game's code.

To find these values, you can use [REF_Inspect](https://github.com/FuzzyGamesOn/REF_Inspect) and interact with the typewriters normally.

##### Player Position
This field specifies the x/y/z (Vector3) location that the player should be teleported to when using the typewriter. Typically, you'd want this to be fairly close to the typewriter, or at least nearby in the same room.

To find a usable value for this, you can use [REF_Inspect](https://github.com/FuzzyGamesOn/REF_Inspect) and interact with the typewriters normally.
