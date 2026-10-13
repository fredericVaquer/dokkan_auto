"""Stateful wrapper around the pure rules: owns the current state and the RNG.

The UI drives it one transition at a time (so it can animate); headless code
calls ``run_episode(agent)``. Either way, the only randomness is the replacement
die sampled in ``roll``. With a fixed seed, the sequence of replacement dice is
the same no matter which agent plays, so comparing Max and Smart on the same
seed is a fair comparison ("common random numbers").
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dokkan_pathing.game import rules
from dokkan_pathing.game.dice import DiceDistribution
from dokkan_pathing.game.map import GameMap
from dokkan_pathing.game.rules import Event
from dokkan_pathing.game.state import GameState, Metrics, Phase

if TYPE_CHECKING:
    from dokkan_pathing.agents.base_agent import Agent


@dataclass
class EpisodeResult:
    metrics: Metrics
    completed: bool  # final tile reached
    aborted: bool  # hit max_rolls (e.g. an agent that loops forever)
    events: list[Event] = field(default_factory=list)


class Simulator:
    def __init__(
        self,
        game_map: GameMap,
        distribution: DiceDistribution,
        seed: int | None = None,
        initial_dice: tuple[int, int, int] | None = None,
        max_rolls: int = 200,
    ) -> None:
        self.game_map = game_map
        self.distribution = distribution
        self.rng = random.Random(seed)
        self.max_rolls = max_rolls
        if initial_dice is None:
            initial_dice = game_map.initial_dice or tuple(distribution.sample(self.rng) for _ in range(3))
        self.state: GameState = rules.initial_state(game_map, initial_dice)
        self.log: list[Event] = []

    @property
    def phase(self) -> Phase:
        return self.state.phase

    @property
    def aborted(self) -> bool:
        return self.state.phase is Phase.CHOOSE_DIE and self.state.metrics.rolls >= self.max_rolls

    @property
    def is_over(self) -> bool:
        return self.state.is_terminal or self.aborted

    def direction_options(self) -> tuple[str, ...]:
        return rules.direction_options(self.state, self.game_map)

    # Each method performs exactly one transition and returns its events.

    def select_die(self, slot: int) -> list[Event]:
        return self._apply(rules.select_die(self.state, self.game_map, slot))

    def select_direction(self, node_id: str) -> list[Event]:
        return self._apply(rules.select_direction(self.state, self.game_map, node_id))

    def step(self) -> list[Event]:
        return self._apply(rules.step(self.state, self.game_map))

    def roll(self, value: int | None = None) -> list[Event]:
        if value is None:
            value = self.distribution.sample(self.rng)
        return self._apply(rules.roll(self.state, value))

    def advance(self) -> list[Event]:
        """Perform the next automatic transition (a forced step or a dice roll)."""
        if self.phase is Phase.MOVING:
            return self.step()
        if self.phase is Phase.ROLL:
            return self.roll()
        raise ValueError(f"no automatic transition in phase {self.phase.name}")

    def run_episode(self, agent: Agent) -> EpisodeResult:
        """Play until the final tile (or ``max_rolls``) letting ``agent`` make every decision."""
        while not self.is_over:
            if self.phase is Phase.CHOOSE_DIE:
                self.select_die(agent.choose_die(self.state, self.game_map))
            elif self.phase is Phase.CHOOSE_DIRECTION:
                options = self.direction_options()
                self.select_direction(agent.choose_direction(self.state, self.game_map, options))
            else:
                self.advance()
        return EpisodeResult(self.state.metrics, self.state.is_terminal, self.aborted, list(self.log))

    def _apply(self, transition: rules.Transition) -> list[Event]:
        self.state, events = transition
        self.log.extend(events)
        return events
