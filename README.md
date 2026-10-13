# dokkan_auto
This repo will try to get an optimized auto Dragon Ball Z Dokan Battle. Usually, levels in this game consist of 2 principal components: pathing and fighting. The game has already automatic features for those, but pathing always takes the maximum value and fight always takes the maximum ki path, which are not necessarily the optimum.

## Pathing simulator

A small simulator of Dokkan's board/dice pathing (no combat, no emulator) for
building search-based path agents. Standard library only (tkinter, unittest).

```bash
python -m dokkan_pathing                                    # GUI: menu -> board
python -m dokkan_pathing --headless --stage mixed --runs 500  # batch: Max vs Smart
python -m unittest                                          # tests
```

Modes: **Player** (you choose dice and branches), **Auto — Max** (largest die,
first branch: the in-game behaviour), **Auto — Smart** (expectimax, left as
exercises: see [docs/LEARNING_PATH.md](docs/LEARNING_PATH.md)).

```
dokkan_pathing/
  game/      rules engine: immutable state, pure rules, map, dice, objective, simulator
  search/    expectimax + evaluation               (TODO: exercises)
  agents/    MaxAgent (done), SmartAgent           (TODO: exercises)
  ui/        tkinter menu + animated board
  maps/      6 small JSON stages, each built to test one behaviour
  configs/   objective weights (fast/safe/farming/balanced), dice distributions
  tests/     simulator tests + target tests for the Smart agent
```
