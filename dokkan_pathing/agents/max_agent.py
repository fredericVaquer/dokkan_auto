"""Baseline: mimics Dokkan's built-in auto-path. Always uses the largest die."""

from __future__ import annotations

from dokkan_pathing.agents.base_agent import Agent, DecisionInfo, OptionScore, direction_label
from dokkan_pathing.game.map import GameMap
from dokkan_pathing.game.rules import available_slots
from dokkan_pathing.game.state import GameState


class MaxAgent(Agent):
    name = "Auto — Max"

    def choose_die(self, state: GameState, game_map: GameMap) -> int:
        slots = available_slots(state)
        # Largest value; on ties the leftmost slot (hence -slot in the key).
        best = max(slots, key=lambda slot: (state.dice[slot], -slot))
        self.last_decision = DecisionInfo(
            kind="die",
            options=[OptionScore(f"Die {s + 1} ({state.dice[s]})") for s in slots],
            chosen_index=slots.index(best),
            notes=["Rule: always the largest die (leftmost on ties)."],
        )
        return best

    def choose_direction(self, state: GameState, game_map: GameMap, options: tuple[str, ...]) -> str:
        self.last_decision = DecisionInfo(
            kind="direction",
            options=[OptionScore(direction_label(game_map, o)) for o in options],
            chosen_index=0,
            notes=["Rule: always the first listed direction."],
        )
        return options[0]
