"""Objective model: turns a run's ``Metrics`` into a single score (higher = better).

This is deliberately separate from the search. The search answers "which action
leads to the best expected score?"; the objective answers "what counts as
good?". Swapping ``fast`` for ``farming`` changes the agent's behaviour without
touching a line of search code.

The score is linear: ``score = sum(weight[m] * metrics.m)``. Negative weights are
penalties (fights, rolls, damage), positive weights are rewards (items). The
boss is not a metric at all, because every run must end there anyway.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from dokkan_pathing.game.state import METRIC_NAMES, Metrics

CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"


@dataclass(frozen=True)
class Objective:
    name: str
    weights: dict[str, float] = field(hash=False)  # metric name -> value per unit
    description: str = ""

    def __post_init__(self) -> None:
        unknown = set(self.weights) - set(METRIC_NAMES)
        if unknown:
            raise ValueError(f"unknown metric(s) in objective {self.name!r}: {sorted(unknown)}")

    def score(self, metrics: Metrics) -> float:
        return sum(weight * getattr(metrics, name) for name, weight in self.weights.items())

    def breakdown(self, metrics: Metrics) -> dict[str, float]:
        """Contribution of each metric to the score (non-zero entries only)."""
        parts = {name: weight * getattr(metrics, name) for name, weight in self.weights.items()}
        return {name: value for name, value in parts.items() if value}


def load_objectives(path: str | Path | None = None) -> dict[str, Objective]:
    path = Path(path) if path else CONFIGS_DIR / "objectives.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        name: Objective(name, dict(entry["weights"]), entry.get("description", ""))
        for name, entry in raw.items()
    }
