"""Probability distribution for newly rolled dice.

Each replacement die is an independent draw from this distribution. The search
needs two things from it: ``sample`` (to play) and ``outcomes`` (to enumerate
the branches of a chance node together with their probabilities).
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

FACES: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"


@dataclass(frozen=True)
class DiceDistribution:
    name: str
    probabilities: tuple[float, ...]  # probabilities[i] is P(face = i + 1)

    def __post_init__(self) -> None:
        if len(self.probabilities) != len(FACES):
            raise ValueError(f"need {len(FACES)} probabilities, got {len(self.probabilities)}")
        if any(p < 0 for p in self.probabilities):
            raise ValueError("probabilities must be non-negative")
        if not math.isclose(sum(self.probabilities), 1.0, abs_tol=1e-9):
            raise ValueError(f"probabilities must sum to 1, got {sum(self.probabilities)}")

    @classmethod
    def from_weights(cls, name: str, weights: list[float] | tuple[float, ...]) -> DiceDistribution:
        """Build from relative weights, e.g. ``[1, 1, 1, 1, 2, 2]``."""
        total = sum(weights)
        if total <= 0:
            raise ValueError("weights must have a positive sum")
        return cls(name, tuple(w / total for w in weights))

    @classmethod
    def uniform(cls) -> DiceDistribution:
        return cls.from_weights("uniform", [1] * len(FACES))

    def probability(self, face: int) -> float:
        return self.probabilities[face - 1]

    def outcomes(self) -> tuple[tuple[int, float], ...]:
        """``(face, probability)`` pairs for every face that can actually occur."""
        return tuple((face, p) for face, p in zip(FACES, self.probabilities) if p > 0)

    def sample(self, rng: random.Random) -> int:
        return rng.choices(FACES, weights=self.probabilities, k=1)[0]

    @property
    def mean(self) -> float:
        return sum(face * p for face, p in zip(FACES, self.probabilities))


def load_distributions(path: str | Path | None = None) -> dict[str, DiceDistribution]:
    path = Path(path) if path else CONFIGS_DIR / "dice.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {name: DiceDistribution.from_weights(name, entry["weights"]) for name, entry in raw.items()}
