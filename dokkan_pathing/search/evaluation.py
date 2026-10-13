"""How good is a state where the search stops looking further?

The search calls ``evaluate`` at two kinds of leaf:

1. **Terminal** leaves (``state.phase is Phase.DONE``): the stage is over, so
   the objective score of the collected metrics is the exact answer.
2. **Cutoff** leaves (search depth ran out): the stage is NOT over. The
   metrics so far are only part of the story; the rolls still needed to reach
   the boss are missing. Ignoring them makes the agent short-sighted: within
   the horizon, a long detour looks just as good as a short route.

Exercise 1 handles both cases with the plain objective score.
Exercise 6 comes back here to add a *heuristic* estimate of the future for
cutoff leaves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dokkan_pathing.game.state import GameState

if TYPE_CHECKING:
    from dokkan_pathing.search.expectimax import SearchContext


def evaluate(state: GameState, ctx: SearchContext) -> float:
    """Return the value of ``state`` (higher = better) as seen by ``ctx.objective``.

    Useful things you can reach from here:
        state.metrics                     -> Metrics counters collected so far
        state.is_terminal                 -> True once the boss is reached
        ctx.objective.score(metrics)      -> float, see game/objective.py
        ctx.game_map.distance_to_boss(id) -> fewest steps left (Exercise 6)
        ctx.distribution.mean             -> average die value (Exercise 6)
    """
    return ctx.objective.score(state.metrics)
    # TODO(Exercise 6, later): for NON-terminal states, add an estimate of the cost
    # of finishing the stage, e.g. "about distance_to_boss / mean_die more rolls,
    # each costing weights['rolls']". Ask yourself: why does this estimate make
    # the agent prefer short routes even when depth is small?
    raise NotImplementedError("TODO: implement evaluate() in search/evaluation.py (Exercise 1)")
