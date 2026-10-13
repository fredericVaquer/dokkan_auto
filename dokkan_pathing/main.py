"""Entry point.

    python -m dokkan_pathing                         # graphical simulator
    python -m dokkan_pathing --headless --stage mixed --runs 500
    python -m dokkan_pathing --headless --stage farming --objective farming --agents max smart --depth 3
"""

from __future__ import annotations

import argparse

from dokkan_pathing.game.dice import load_distributions
from dokkan_pathing.game.map import available_maps, load_map
from dokkan_pathing.game.objective import load_objectives
from dokkan_pathing.runner import MODE_MAX, MODE_SMART, format_summary, make_agent, run_batch


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Dokkan pathing simulator")
    parser.add_argument("--headless", action="store_true", help="run a batch comparison instead of the GUI")
    parser.add_argument("--stage", default="mixed", choices=list(available_maps()))
    parser.add_argument("--objective", default="balanced", choices=list(load_objectives()))
    parser.add_argument("--dice", default="uniform", choices=list(load_distributions()))
    parser.add_argument("--agents", nargs="+", default=["max", "smart"], choices=["max", "smart"])
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--runs", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    if not args.headless:
        from dokkan_pathing.ui.app import run_app

        run_app()
        return

    game_map = load_map(args.stage)
    objective = load_objectives()[args.objective]
    distribution = load_distributions()[args.dice]
    print(f"Stage: {game_map.name} | objective: {objective.name} | dice: {distribution.name} | runs: {args.runs}")
    for key in args.agents:
        mode = {"max": MODE_MAX, "smart": MODE_SMART}[key]
        label = f"{key} (d={args.depth})" if key == "smart" else key
        try:
            summary = run_batch(
                game_map,
                lambda: make_agent(mode, objective, distribution, args.depth),
                distribution,
                objective,
                runs=args.runs,
                seed=args.seed,
            )
        except NotImplementedError as exc:
            print(f"{label:<14} {exc}".replace("\n", " | "))
            continue
        print(format_summary(label, summary))


if __name__ == "__main__":
    main()
