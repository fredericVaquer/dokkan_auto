"""Common interface for anything that makes path decisions.

An agent is asked two kinds of question, matching the two decision phases:

* ``choose_die(state, game_map)`` -> slot index 0, 1 or 2
* ``choose_direction(state, game_map, options)`` -> one of the node ids in ``options``

Agents never mutate the state or touch the RNG; the Simulator applies their
choice. After deciding, an agent may store a ``DecisionInfo`` in
``self.last_decision`` so the UI can show *why* it chose what it chose.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from dokkan_pathing.game.map import GameMap
from dokkan_pathing.game.state import GameState


@dataclass
class OptionScore:
    label: str  # e.g. "Die 2 (4)" or "c (exclusive)"
    value: float | None = None  # expected score, if the agent computed one


@dataclass
class DecisionInfo:
    kind: str  # "die" or "direction"
    options: list[OptionScore]
    chosen_index: int
    notes: list[str] = field(default_factory=list)

    def format(self) -> str:
        lines = []
        for i, opt in enumerate(self.options):
            marker = ">" if i == self.chosen_index else " "
            value = f"  expected score = {opt.value:9.1f}" if opt.value is not None else ""
            lines.append(f"{marker} {opt.label}{value}")
        lines.append(f"Selected: {self.options[self.chosen_index].label}")
        lines += self.notes
        return "\n".join(lines)


class Agent(ABC):
    name = "Agent"

    def __init__(self) -> None:
        self.last_decision: DecisionInfo | None = None

    @abstractmethod
    def choose_die(self, state: GameState, game_map: GameMap) -> int: ...

    @abstractmethod
    def choose_direction(self, state: GameState, game_map: GameMap, options: tuple[str, ...]) -> str: ...


def direction_label(game_map: GameMap, node_id: str) -> str:
    """Human-readable label for a branch option, shared by agents and the UI."""
    return f"{node_id} ({game_map.node(node_id).type.value})"
