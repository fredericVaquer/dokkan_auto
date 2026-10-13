"""Tile types and the rules for *when* each tile has an effect.

Design note
-----------
Tile behaviour is described by *data* (``TILE_RULES``) instead of by a chain of
``if tile.type == ...`` statements spread through the simulator. Adding a new
tile type means adding one enum member and one table row; the movement code in
``rules.py`` does not change.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TileType(str, Enum):
    START = "start"
    NORMAL = "normal"
    SUPPORT_ITEM = "support_item"
    TRAINING_ITEM = "training_item"
    ZENI = "zeni"
    KI = "ki"
    EXCLUSIVE = "exclusive"
    RANDOM = "random"
    BABA = "baba"
    DAMAGE = "damage"
    FIGHT = "fight"
    KINTON = "kinton"
    BOSS = "boss"
    FINAL = "final"


class Trigger(Enum):
    NEVER = "never"  # the tile has no effect
    ENTER = "enter"  # fires whenever the player steps onto the tile, passing OR landing
    LAND = "land"  # fires only if the move *ends* on the tile


@dataclass(frozen=True)
class TileRule:
    trigger: Trigger
    metric: str | None = None  # which Metrics field the tile increases (by node.amount)
    consumable: bool = False  # removed from the board after firing once
    forced_stop: bool = False  # entering the tile always ends the move immediately


TILE_RULES: dict[TileType, TileRule] = {
    TileType.START: TileRule(Trigger.NEVER),
    TileType.NORMAL: TileRule(Trigger.NEVER),
    # Items are picked up as you walk over them, and disappear afterwards.
    TileType.SUPPORT_ITEM: TileRule(Trigger.ENTER, "support_items", consumable=True),
    TileType.TRAINING_ITEM: TileRule(Trigger.ENTER, "training_items", consumable=True),
    TileType.ZENI: TileRule(Trigger.ENTER, "zeni", consumable=True),
    TileType.KI: TileRule(Trigger.ENTER, "ki", consumable=True),
    TileType.EXCLUSIVE: TileRule(Trigger.ENTER, "exclusive_items", consumable=True),
    # Event tiles only fire if you land exactly on them, so the die you pick matters.
    TileType.RANDOM: TileRule(Trigger.LAND, "random_tiles", consumable=True),
    # Baba's shop: lets you buy a random item (usually a weak support item). Rare, mildly positive.
    TileType.BABA: TileRule(Trigger.LAND, "baba_shops", consumable=True),
    TileType.DAMAGE: TileRule(Trigger.LAND, "damage"),
    # A plain enemy only fights you if you land on it; a bigger die walks past it.
    # Marking the node ``"stop": true`` in the map makes it a stopping enemy instead:
    # reaching it ends the move and starts the fight. Once defeated, enemies are gone.
    TileType.FIGHT: TileRule(Trigger.LAND, "fights", consumable=True),
    # Kinton stops you and teleports you to node.target (handled in rules.py).
    TileType.KINTON: TileRule(Trigger.NEVER, forced_stop=True),
    # Bosses always stop you. A stage can have several; the run goes on afterwards.
    # Counted separately from "fights" so unavoidable bosses don't distort route choice.
    TileType.BOSS: TileRule(Trigger.ENTER, "bosses", consumable=True, forced_stop=True),
    # Reaching the final tile ends the stage (handled in rules.py).
    TileType.FINAL: TileRule(Trigger.NEVER, forced_stop=True),
}
