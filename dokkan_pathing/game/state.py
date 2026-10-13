"""The immutable game state.

Why immutable (``frozen=True``)?
--------------------------------
Search algorithms explore *many* hypothetical futures from the same state. If
states were mutable, exploring "what if I pick die 1" could corrupt the state we
later use for "what if I pick die 2". With frozen dataclasses every rule
function returns a *new* state and the old one stays valid, so branching is free
of bugs by construction. Frozen dataclasses are also hashable, which is what
makes memoization (a dict keyed by state) possible later.

Why a ``phase``?
----------------
The phase says *who acts next*, which is exactly the node type of the search
tree:

    CHOOSE_DIE        -> decision node (agent picks a dice slot)
    CHOOSE_DIRECTION  -> decision node (agent picks a branch)
    MOVING            -> deterministic: exactly one forced step ahead
    ROLL              -> chance node (the used slot gets a random new die)
    DONE              -> terminal (boss reached)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from enum import Enum


class Phase(Enum):
    CHOOSE_DIE = "choose_die"
    MOVING = "moving"
    CHOOSE_DIRECTION = "choose_direction"
    ROLL = "roll"
    DONE = "done"


@dataclass(frozen=True)
class Metrics:
    """Everything that happened during a run, kept as separate counters.

    The objective function (``objective.py``) turns these into one score. Keeping
    them separate means the same run can be judged by different objectives.
    """

    rolls: int = 0
    fights: int = 0
    damage: int = 0
    support_items: int = 0
    training_items: int = 0
    zeni: int = 0
    ki: int = 0
    exclusive_items: int = 0
    random_tiles: int = 0
    negative_tiles: int = 0

    def add(self, name: str, amount: int = 1) -> Metrics:
        return replace(self, **{name: getattr(self, name) + amount})

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


METRIC_NAMES: tuple[str, ...] = tuple(f.name for f in fields(Metrics))

# A slot holds None between "die used" and "replacement rolled".
Dice = tuple[int | None, int | None, int | None]


@dataclass(frozen=True)
class GameState:
    position: str  # id of the node the player stands on
    dice: Dice  # never sorted: slot i stays slot i
    phase: Phase = Phase.CHOOSE_DIE
    metrics: Metrics = field(default_factory=Metrics)
    consumed: frozenset[str] = frozenset()  # nodes whose one-time effect already fired
    active_slot: int | None = None  # slot used for the current move (refilled at ROLL)
    steps_remaining: int = 0  # movement left in the current move

    @property
    def is_terminal(self) -> bool:
        return self.phase is Phase.DONE
