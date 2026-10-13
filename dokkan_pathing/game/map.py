"""The stage as a directed graph of nodes, loaded from JSON.

Map JSON format::

    {
      "name": "Basic",
      "description": "...",
      "start": "s",
      "initial_dice": [2, 4, 6],            # optional; random if omitted
      "nodes": [
        {"id": "s", "type": "start", "pos": [0, 1], "next": ["a"]},
        {"id": "k", "type": "kinton", "pos": [5, 0], "target": "q"},
        {"id": "d", "type": "damage", "pos": [3, 1], "next": ["e"], "amount": 2},
        ...
      ]
    }

The order of ``next`` matters: it is the order in which branch options are
offered, and the Max agent always takes the first one.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from dokkan_pathing.game.tiles import TileType

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"


class MapError(ValueError):
    """Raised when a map definition is inconsistent."""


@dataclass(frozen=True)
class Node:
    id: str
    type: TileType
    next: tuple[str, ...] = ()
    pos: tuple[float, float] = (0.0, 0.0)  # layout coordinates, only used for drawing
    target: str | None = None  # Kinton teleport destination
    amount: int = 1  # how much the tile adds to its metric
    label: str = ""  # optional text shown under the node


class GameMap:
    def __init__(
        self,
        name: str,
        nodes: Iterable[Node],
        start: str,
        description: str = "",
        initial_dice: tuple[int, int, int] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.start = start
        self.initial_dice = initial_dice
        self.nodes: dict[str, Node] = {}
        for node in nodes:
            if node.id in self.nodes:
                raise MapError(f"duplicate node id {node.id!r}")
            self.nodes[node.id] = node
        self._distances: dict[str, float] | None = None
        self.validate()

    def node(self, node_id: str) -> Node:
        return self.nodes[node_id]

    def successors(self, node_id: str) -> tuple[str, ...]:
        return self.nodes[node_id].next

    @property
    def boss_ids(self) -> tuple[str, ...]:
        return tuple(n.id for n in self.nodes.values() if n.type is TileType.BOSS)

    def distance_to_boss(self, node_id: str) -> float:
        """Fewest *steps* from ``node_id`` to a boss (``math.inf`` if unreachable).

        Entering a Kinton cloud counts as one step and then continues from its
        target for free. Forced stops (fights, Kinton) are ignored, so this is
        an optimistic estimate of how many steps are left, not of how many rolls.
        """
        if self._distances is None:
            self._distances = self._compute_distances()
        return self._distances[node_id]

    def _compute_distances(self) -> dict[str, float]:
        # Repeated relaxation (Bellman-Ford style). Maps are tiny, so a simple
        # loop until nothing changes is easier to read than Dijkstra.
        dist = {nid: math.inf for nid in self.nodes}
        for boss in self.boss_ids:
            dist[boss] = 0
        changed = True
        while changed:
            changed = False
            for node in self.nodes.values():
                if node.type is TileType.BOSS:
                    continue
                if node.type is TileType.KINTON:
                    candidate = dist[node.target]
                else:
                    candidate = 1 + min((dist[n] for n in node.next), default=math.inf)
                if candidate < dist[node.id]:
                    dist[node.id] = candidate
                    changed = True
        return dist

    def validate(self) -> None:
        if self.start not in self.nodes:
            raise MapError(f"start node {self.start!r} does not exist")
        if not self.boss_ids:
            raise MapError("map has no boss node")
        if self.initial_dice is not None:
            if len(self.initial_dice) != 3 or not all(1 <= d <= 6 for d in self.initial_dice):
                raise MapError(f"initial_dice must be three values in 1..6, got {self.initial_dice}")
        for node in self.nodes.values():
            for nxt in node.next:
                if nxt not in self.nodes:
                    raise MapError(f"node {node.id!r} points to unknown node {nxt!r}")
                if nxt == node.id:
                    raise MapError(f"node {node.id!r} points to itself")
            if node.type is TileType.KINTON:
                if node.target not in self.nodes or node.target == node.id:
                    raise MapError(f"kinton {node.id!r} needs a valid 'target', got {node.target!r}")
            elif node.type is not TileType.BOSS and not node.next:
                raise MapError(f"node {node.id!r} is a dead end (no 'next')")
        if math.isinf(self.distance_to_boss(self.start)):
            raise MapError("boss is not reachable from the start")

    @classmethod
    def from_dict(cls, data: dict) -> GameMap:
        nodes = [
            Node(
                id=raw["id"],
                type=TileType(raw.get("type", "normal")),
                next=tuple(raw.get("next", ())),
                pos=tuple(raw.get("pos", (0, 0))),
                target=raw.get("target"),
                amount=raw.get("amount", 1),
                label=raw.get("label", ""),
            )
            for raw in data["nodes"]
        ]
        dice = data.get("initial_dice")
        return cls(
            name=data.get("name", "Unnamed"),
            nodes=nodes,
            start=data["start"],
            description=data.get("description", ""),
            initial_dice=tuple(dice) if dice else None,
        )

    @classmethod
    def load(cls, path: str | Path) -> GameMap:
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


def available_maps() -> dict[str, Path]:
    """Map key (file stem, e.g. ``"basic"``) -> path of its JSON file."""
    return {p.stem: p for p in sorted(MAPS_DIR.glob("*.json"))}


def load_map(key: str) -> GameMap:
    maps = available_maps()
    if key not in maps:
        raise KeyError(f"unknown map {key!r}; available: {', '.join(maps)}")
    return GameMap.load(maps[key])
