# Learning path: building the Smart agent

The simulator, Player mode and the Max baseline are complete. The Smart agent is
yours to write. Each exercise is small, has a target test in
`dokkan_pathing/tests/test_smart_agent.py` that skips until you implement it,
and something to look at in the GUI.

```bash
python -m unittest dokkan_pathing.tests.test_smart_agent -v   # your progress
python -m unittest                                              # everything (simulator must stay green)
python -m dokkan_pathing --headless --stage mixed --depth 2     # Max vs Smart, 200 seeded games
python -m dokkan_pathing                                        # watch it play
```

Once you implement a TODO, **remove its `raise NotImplementedError`**. The tests
use that exception to decide whether to skip.

---

## Exercise 0: Play it yourself (no code)

Play **Damage Avoidance** and **Fight Avoidance** in Player mode, then watch
*Auto — Max* on the same stage with the same seed.

- On the damage map's straight section, which die choices let you jump *over* a
  damage tile? Why can Max not do this?
- Why does Max walk into both fights on the fight map? (Hint: the order of
  `next` in `maps/fight_avoidance.json`.)

Concepts: the rules you are about to search over. Read `game/rules.py`
top-to-bottom first; it is short.

## Exercise 1: `evaluate()` (search/evaluation.py)

Return the objective score of the metrics collected so far. One line.

Before moving on, answer this: the search will call `evaluate` on states where
the stage is *not* finished. What is missing from the score in that case?
(Exercise 6 comes back to this.)

Test: `Exercise1EvaluateTest`.

## Exercise 2: `expectimax_value()`, the recursion (search/expectimax.py)

This is the core of the project. The table at the top of `expectimax.py` gives
the value of every node type. Handle them in this order:

1. terminal state → `evaluate`
2. depth exhausted → `evaluate`
3. `ROLL` (chance) → probability-weighted average over `ctx.distribution.outcomes()`
4. `CHOOSE_DIRECTION` (max) → best child, **same depth**
5. `CHOOSE_DIE` (max) → best child

Decide where depth decreases and write it down as a comment. The tests accept
either "when the die is chosen" or "when the new die is rolled", as long as
directions never decrease it.

Things to think through:
- Why is it safe to call `play_die(state, ...)` several times on the same
  `state`? (Look at `GameState`'s `frozen=True` and at `test_rules_do_not_mutate_input_state`.)
- Why must the terminal check come *before* the depth check?
- In the chance node, are the probabilities guaranteed to sum to 1? Does your
  code rely on that?

Tests: `Exercise2ExpectimaxTest`. `test_chance_node_averages_over_rolls` has the
expected value worked out by hand in its docstring; trace your recursion against it.

## Exercises 3 and 4: Decisions (`score_dice`, `score_directions`, `SmartAgent`)

Turn values into choices: score every option, return the best one, and fill
`self.last_decision` so the GUI shows a table like:

```
  Die 1 (2)  expected score =     -52.7
  Die 2 (4)  expected score =     -61.4
> Die 3 (6)  expected score =     -50.5
```

Then run **Fight Avoidance** in *Auto — Smart* with depth 1. It should avoid
both fights. Also run `--headless --stage fight_avoidance` and compare the
numbers with Max.

Tests: `Exercise3And4DecisionTest`.

## Exercise 5: Memoization (`cache_key` + `ctx.cache`)

Before writing code, measure. Print `ctx.nodes_visited` for depths 1, 2, 3 and 4
on **Complex Mixed**. How fast does it grow? Each turn multiplies the tree by
roughly (3 dice × 6 outcomes) = 18.

Then cache `(state, depth) → value` in `ctx.cache` and count `ctx.cache_hits`.
The same position is reached in many ways (die 2 then die 4 versus die 4 then
die 2), and that is where the savings come from.

Then the deeper question in the `cache_key` docstring: `state.metrics` is part
of the state, so paths with different histories never share an entry. Could
`expectimax_value` return the value of the *future only*, relative to the
metrics already collected? Hint: the objective is linear.

Test: `Exercise5MemoizationTest`.

## Exercise 6: The horizon problem (heuristic in `evaluate`)

Run **Exclusive Farming** with the `fast` objective at depth 2. Your agent will
probably take the long route even though `fast` hates extra rolls. The reason:
within two turns both routes are unfinished, and a plain objective score only
sees the items, not the extra roll the detour will cost *after* the horizon.

Fix it by adding an estimate of the remaining cost to non-terminal states.
`ctx.game_map.distance_to_final(node)` and `ctx.distribution.mean` are there for
this.

Test: `Exercise6HeuristicTest` (the objective should now flip the route).

## Exercise 7: Unavoidable fights (open-ended)

Watch **Basic** with Smart at depth 2. At some point it refuses a die that
walks into the fight and uses a smaller one. The fight on Basic cannot be
avoided (it is a stopping fight), so this only *postpones* it past the horizon and wastes a roll. This
is the classic **horizon effect**. Your spec warned about the same thing for the
boss: something unavoidable must not distort route selection.

Ideas to try:
- precompute "minimum number of fights between this node and the final tile" (like
  `distance_to_final`, but counting fights, and remember fights are consumed) and
  charge them in the heuristic;
- or deepen the search only when a fight is within reach (selective deepening).

Measure with `--headless --stage basic` before and after.

## Later ideas

- Order the dice and prune (`*-minimax`-style bounds for chance nodes)
- Iterative deepening with a time budget instead of a fixed depth
- A map that rewards *keeping* a big die for later: what does depth 1 miss?
- Only then: Monte Carlo rollouts, and eventually learning the evaluation function
