"""Start screen: pick stage, mode, objective, dice, depth and animation speed."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk

from dokkan_pathing.game.dice import load_distributions
from dokkan_pathing.game.map import available_maps, load_map
from dokkan_pathing.game.objective import load_objectives
from dokkan_pathing.runner import MODE_PLAYER, MODES


@dataclass(frozen=True)
class Speed:
    step_ms: int  # time per tile moved
    decision_ms: int  # pause on each AI decision so you can read it


SPEEDS = {
    "Slow": Speed(320, 1000),
    "Normal": Speed(170, 600),
    "Fast": Speed(70, 300),
    "Turbo": Speed(15, 60),
}


@dataclass(frozen=True)
class RunConfig:
    stage: str  # map key, e.g. "mixed"
    mode: str
    objective: str
    dice: str
    depth: int
    speed: str
    seed: int | None  # None = new random seed on every (re)start


class MenuFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, on_start: Callable[[RunConfig], None], initial: RunConfig | None = None):
        super().__init__(master, padding=24)
        self.on_start = on_start
        self.maps = {key: load_map(key) for key in available_maps()}
        self.objectives = load_objectives()
        self.stage_names = {m.name: key for key, m in self.maps.items()}

        initial = initial or RunConfig("basic", MODE_PLAYER, "balanced", "uniform", 2, "Normal", None)
        self.stage = tk.StringVar(value=self.maps[initial.stage].name)
        self.mode = tk.StringVar(value=initial.mode)
        self.objective = tk.StringVar(value=initial.objective)
        self.dice = tk.StringVar(value=initial.dice)
        self.depth = tk.StringVar(value=str(initial.depth))
        self.speed = tk.StringVar(value=initial.speed)
        self.seed = tk.StringVar(value="" if initial.seed is None else str(initial.seed))
        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="Dokkan Pathing Simulator", font=("TkDefaultFont", 22, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 18), sticky="w"
        )
        rows = [
            ("Stage", ttk.Combobox(self, textvariable=self.stage, values=list(self.stage_names), state="readonly")),
            ("Mode", ttk.Combobox(self, textvariable=self.mode, values=list(MODES), state="readonly")),
            ("Objective", ttk.Combobox(self, textvariable=self.objective, values=list(self.objectives), state="readonly")),
            ("Dice distribution", ttk.Combobox(self, textvariable=self.dice, values=list(load_distributions()), state="readonly")),
            ("Search depth", ttk.Spinbox(self, textvariable=self.depth, from_=1, to=8, width=6)),
            ("Animation speed", ttk.Combobox(self, textvariable=self.speed, values=list(SPEEDS), state="readonly")),
            ("Seed (blank = random)", ttk.Entry(self, textvariable=self.seed, width=12)),
        ]
        for i, (label, widget) in enumerate(rows, start=1):
            ttk.Label(self, text=label).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 16))
            widget.grid(row=i, column=1, sticky="we", pady=4)
        self.columnconfigure(1, weight=1, minsize=280)

        self.info = ttk.Label(self, wraplength=520, justify="left", foreground="#555")
        self.info.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="w", pady=(14, 8))
        self.error = ttk.Label(self, foreground="#c62828")
        self.error.grid(row=len(rows) + 2, column=0, columnspan=2, sticky="w")
        ttk.Button(self, text="Start", command=self._start).grid(row=len(rows) + 3, column=0, columnspan=2, pady=12)

        for var in (self.stage, self.objective, self.mode):
            var.trace_add("write", lambda *_: self._update_info())
        self._update_info()
        self.winfo_toplevel().bind("<Return>", lambda _e: self._start())

    def _update_info(self) -> None:
        game_map = self.maps[self.stage_names[self.stage.get()]]
        objective = self.objectives[self.objective.get()]
        self.info.config(text=f"{game_map.description}\n\nObjective '{objective.name}': {objective.description}")

    def _start(self) -> None:
        try:
            depth = int(self.depth.get())
            if depth < 1:
                raise ValueError
        except ValueError:
            self.error.config(text="Search depth must be a positive integer.")
            return
        seed_text = self.seed.get().strip()
        if seed_text and not seed_text.lstrip("-").isdigit():
            self.error.config(text="Seed must be an integer (or blank).")
            return
        self.winfo_toplevel().unbind("<Return>")
        self.on_start(
            RunConfig(
                stage=self.stage_names[self.stage.get()],
                mode=self.mode.get(),
                objective=self.objective.get(),
                dice=self.dice.get(),
                depth=depth,
                speed=self.speed.get(),
                seed=int(seed_text) if seed_text else None,
            )
        )
