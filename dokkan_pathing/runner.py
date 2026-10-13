"""Headless batch runs: play many seeded episodes and average the metrics.

Watching one animated run tells you *how* an agent behaves; averaging hundreds
tells you whether it is actually *better*. Episode ``i`` uses seed ``seed + i``
for every agent, so all agents face the same replacement dice.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from dokkan_pathing.agents.base_agent import Agent
from dokkan_pathing.agents.max_agent import MaxAgent
from dokkan_pathing.agents.smart_agent import SmartAgent
from dokkan_pathing.game.dice import DiceDistribution
from dokkan_pathing.game.map import GameMap
from dokkan_pathing.game.objective import Objective
from dokkan_pathing.game.simulator import EpisodeResult, Simulator
from dokkan_pathing.game.state import METRIC_NAMES

MODE_PLAYER = "Player"
MODE_MAX = "Auto — Max"
MODE_SMART = "Auto — Smart"
MODES = (MODE_PLAYER, MODE_MAX, MODE_SMART)


def make_agent(mode: str, objective: Objective, distribution: DiceDistribution, depth: int) -> Agent | None:
    """``None`` means a human makes the decisions."""
    if mode == MODE_PLAYER:
        return None
    if mode == MODE_MAX:
        return MaxAgent()
    if mode == MODE_SMART:
        return SmartAgent(objective, distribution, depth)
    raise ValueError(f"unknown mode {mode!r}")


@dataclass
class BatchSummary:
    runs: int
    completed: int
    mean_metrics: dict[str, float]
    mean_score: float


def run_batch(
    game_map: GameMap,
    agent_factory: Callable[[], Agent],
    distribution: DiceDistribution,
    objective: Objective,
    runs: int = 200,
    seed: int = 0,
) -> BatchSummary:
    results: list[EpisodeResult] = []
    for i in range(runs):
        sim = Simulator(game_map, distribution, seed=seed + i)
        results.append(sim.run_episode(agent_factory()))
    mean = {m: sum(getattr(r.metrics, m) for r in results) / runs for m in METRIC_NAMES}
    score = sum(objective.score(r.metrics) for r in results) / runs
    return BatchSummary(runs, sum(r.completed for r in results), mean, score)


def format_summary(label: str, summary: BatchSummary) -> str:
    shown = {k: v for k, v in summary.mean_metrics.items() if v}
    metrics = "  ".join(f"{k}={v:.2f}" for k, v in shown.items())
    return f"{label:<14} score={summary.mean_score:9.1f}  completed={summary.completed}/{summary.runs}  {metrics}"
