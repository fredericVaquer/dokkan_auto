"""The board view: draws the map, animates the token and shows dice, metrics and AI reasoning.

How the loop works
------------------
``_tick`` looks at ``sim.phase`` and does exactly one thing, much like the
search dispatches on phase:

    DONE / aborted     -> show the result, stop
    MOVING             -> sim.step(), animate one tile, tick again
    ROLL               -> sim.roll(), flash the new die, tick again
    CHOOSE_DIE / DIR   -> Player: highlight the options and wait for a click/key
                          AI:     ask the agent, show its reasoning, pause briefly, apply

The UI never changes the game state itself. Every change goes through the
Simulator, so whatever you see on screen follows the same rules as the tests
and the headless runner.
"""

from __future__ import annotations

import random
import sys
import time
import tkinter as tk
import traceback
from collections.abc import Callable

from dokkan_pathing.agents.base_agent import direction_label
from dokkan_pathing.game.dice import load_distributions
from dokkan_pathing.game.map import load_map
from dokkan_pathing.game.objective import load_objectives
from dokkan_pathing.game.rules import Event, EventKind, available_slots
from dokkan_pathing.game.simulator import Simulator
from dokkan_pathing.game.state import Phase
from dokkan_pathing.game.tiles import TileType
from dokkan_pathing.runner import make_agent
from dokkan_pathing.ui.menu import SPEEDS, RunConfig

BOARD_BG = "#16203a"
PANEL_BG = "#202a44"
PANEL_FG = "#e8ecf6"
MUTED_FG = "#9aa6c4"
EDGE = "#6f7da3"
HIGHLIGHT = "#ffeb3b"
CHOSEN = "#00e676"
TOKEN = "#ff9800"

# fill colour, label, label colour
TILE_STYLE: dict[TileType, tuple[str, str, str]] = {
    TileType.START: ("#9e9e9e", "S", "#000"),
    TileType.NORMAL: ("#e6dfcc", "", "#000"),
    TileType.SUPPORT_ITEM: ("#43a047", "SUP", "#fff"),
    TileType.TRAINING_ITEM: ("#9ccc65", "TRN", "#000"),
    TileType.ZENI: ("#ffd54f", "Z", "#000"),
    TileType.KI: ("#4fc3f7", "KI", "#000"),
    TileType.EXCLUSIVE: ("#ab47bc", "EX", "#fff"),
    TileType.RANDOM: ("#ffa726", "?", "#000"),
    TileType.NEGATIVE: ("#78909c", "NEG", "#fff"),
    TileType.DAMAGE: ("#e53935", "DMG", "#fff"),
    TileType.FIGHT: ("#b71c1c", "VS", "#fff"),
    TileType.KINTON: ("#b3e5fc", "KIN", "#000"),
    TileType.BOSS: ("#111111", "BOSS", "#ff5252"),
}
CONSUMED_FILL, CONSUMED_TEXT = "#3a4562", "#76809c"

POPUPS: dict[EventKind, tuple[str, str]] = {
    EventKind.COLLECT: ("+{text}", "#b9f6ca"),
    EventKind.FIGHT: ("FIGHT!", "#ff5252"),
    EventKind.DAMAGE: ("-{value} HP", "#ff8a80"),
    EventKind.NEGATIVE: ("negative", "#cfd8dc"),
    EventKind.RANDOM: ("random!", "#ffcc80"),
    EventKind.TELEPORT: ("Kinton!", "#81d4fa"),
    EventKind.MOVEMENT_LOST: ("-{value} steps", "#ffab91"),
    EventKind.BOSS: ("BOSS!", "#ff5252"),
}

METRIC_LABELS = {
    "rolls": "Rolls", "fights": "Fights", "damage": "Damage", "support_items": "Support items",
    "training_items": "Training items", "zeni": "Zeni", "ki": "KI", "exclusive_items": "Exclusive",
    "random_tiles": "Random tiles", "negative_tiles": "Negative tiles",
}

MONO = ("TkFixedFont", 9)


class GameView(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        run_config: RunConfig,
        on_menu: Callable[[RunConfig], None],
        on_restart: Callable[[RunConfig], None],
    ) -> None:
        super().__init__(master, bg=PANEL_BG)
        self.run_config = run_config
        self.on_menu = on_menu
        self.on_restart = on_restart
        self.game_map = load_map(run_config.stage)
        self.objective = load_objectives()[run_config.objective]
        self.distribution = load_distributions()[run_config.dice]
        self.speed = SPEEDS[run_config.speed]
        self.seed = run_config.seed if run_config.seed is not None else random.randrange(1_000_000)
        self.sim = Simulator(self.game_map, self.distribution, seed=self.seed)
        self.agent = make_agent(run_config.mode, self.objective, self.distribution, run_config.depth)

        self._alive = True
        self._after_ids: set[str] = set()
        self._tick_id: str | None = None
        self._paused = False
        self._busy = False  # an animation is running
        self._halted = False  # stopped because of an error / unimplemented TODO
        self._highlight: set[str] = set()  # branch options to outline
        self._chosen_node: str | None = None
        self._chosen_slot: int | None = None
        self._flash_slot: int | None = None
        self._token_node = self.sim.state.position
        self._token_xy = (0.0, 0.0)
        self._node_items: dict[str, tuple[int, int]] = {}
        self._layout_params = (0.0, 0.0, 1.0, 1.0, 20.0)

        self._build()
        self.winfo_toplevel().bind("<Key>", self._on_key)
        self._log(f"Stage '{self.game_map.name}' | seed {self.seed} | dice {list(self.sim.state.dice)}")
        self._schedule_tick(300)

    # ------------------------------------------------------------------ layout

    def _build(self) -> None:
        self.canvas = tk.Canvas(self, bg=BOARD_BG, highlightthickness=0, width=900, height=640)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._draw_board())
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        side = tk.Frame(self, bg=PANEL_BG, width=360)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)

        def label(parent, text="", size=10, bold=False, fg=PANEL_FG, **kw):
            weight = "bold" if bold else "normal"
            return tk.Label(parent, text=text, bg=PANEL_BG, fg=fg, font=("TkDefaultFont", size, weight), **kw)

        # Packed first so the panel always reserves room for them, even when the text boxes don't fit.
        self.button_bar = buttons = tk.Frame(side, bg=PANEL_BG)
        buttons.pack(fill="x", padx=12, pady=10, side="bottom")
        self.pause_button = tk.Button(buttons, text="Pause", command=self._toggle_pause, width=8)
        self.pause_button.pack(side="left")
        if self.agent is None:
            self.pause_button.config(state="disabled")
        tk.Button(buttons, text="Restart", command=self._restart, width=8).pack(side="left", padx=6)
        tk.Button(buttons, text="Stage select", command=self._back_to_menu, width=11).pack(side="left")
        self.end_button = tk.Button(side, text="Back to stage select", command=self._back_to_menu,
                                    font=("TkDefaultFont", 11, "bold"), bg=HIGHLIGHT, activebackground=HIGHLIGHT)

        label(side, self.game_map.name, 15, True, anchor="w").pack(fill="x", padx=12, pady=(10, 0))
        cfg = self.run_config
        info = f"{cfg.mode}  |  objective: {cfg.objective}  |  depth: {cfg.depth}\ndice: {cfg.dice}  |  seed: {self.seed}"
        label(side, info, 9, fg=MUTED_FG, anchor="w", justify="left").pack(fill="x", padx=12)

        self.dice_canvas = tk.Canvas(side, bg=PANEL_BG, highlightthickness=0, width=330, height=104)
        self.dice_canvas.pack(padx=12, pady=(10, 2))
        self.dice_canvas.bind("<Button-1>", self._on_dice_click)

        self.status = label(side, "", 11, True, fg=HIGHLIGHT, anchor="w", justify="left", wraplength=330)
        self.status.pack(fill="x", padx=12)
        self.directions = tk.Frame(side, bg=PANEL_BG)
        self.directions.pack(fill="x", padx=12)

        metrics = tk.Frame(side, bg=PANEL_BG)
        metrics.pack(fill="x", padx=12, pady=(8, 0))
        self.metric_labels: dict[str, tk.Label] = {}
        for i, (key, text) in enumerate(METRIC_LABELS.items()):
            r, c = divmod(i, 2)
            label(metrics, text, 9, fg=MUTED_FG, anchor="w").grid(row=r, column=c * 2, sticky="w")
            self.metric_labels[key] = label(metrics, "0", 10, True, anchor="e", width=4)
            self.metric_labels[key].grid(row=r, column=c * 2 + 1, sticky="e", padx=(0, 18))
        self.score_label = label(side, "", 11, True, anchor="w")
        self.score_label.pack(fill="x", padx=12, pady=(4, 0))

        label(side, "AI decision", 10, True, anchor="w").pack(fill="x", padx=12, pady=(10, 0))
        self.decision_text = self._text_box(side, 11)
        label(side, "Events", 10, True, anchor="w").pack(fill="x", padx=12, pady=(8, 0))
        self.event_text = self._text_box(side, 8)

        self._refresh_panel()

    def _text_box(self, parent: tk.Misc, height: int) -> tk.Text:
        box = tk.Text(parent, height=height, bg="#141b2f", fg=PANEL_FG, font=MONO, relief="flat", wrap="word",
                      insertbackground=PANEL_FG, padx=6, pady=4)
        box.pack(fill="x", padx=12)
        box.tag_configure("error", foreground="#ff8a80")
        box.tag_configure("muted", foreground=MUTED_FG)
        box.config(state="disabled")
        return box

    # ------------------------------------------------------------------- board

    def _compute_layout(self) -> None:
        w = max(self.canvas.winfo_width(), 200)
        h = max(self.canvas.winfo_height(), 200)
        xs = [n.pos[0] for n in self.game_map.nodes.values()]
        ys = [n.pos[1] for n in self.game_map.nodes.values()]
        margin, top, bottom = 50, 70, 60  # room for the banner and the legend
        sx = (w - 2 * margin) / max(max(xs) - min(xs), 1)
        sy = min((h - top - bottom) / max(max(ys) - min(ys), 1), sx * 2.2)
        radius = max(10.0, min(24.0, 0.36 * min(sx, sy)))
        used_h = sy * (max(ys) - min(ys))
        oy = top + (h - top - bottom - used_h) / 2
        self._layout_params = (margin - min(xs) * sx, oy - min(ys) * sy, sx, sy, radius)

    def _xy(self, node_id: str) -> tuple[float, float]:
        ox, oy, sx, sy, _ = self._layout_params
        x, y = self.game_map.node(node_id).pos
        return ox + x * sx, oy + y * sy

    @property
    def _radius(self) -> float:
        return self._layout_params[4]

    def _draw_board(self) -> None:
        c = self.canvas
        c.delete("all")
        self._compute_layout()
        r = self._radius
        for node in self.game_map.nodes.values():
            x1, y1 = self._xy(node.id)
            for nxt in node.next:
                x2, y2 = self._xy(nxt)
                dx, dy = x2 - x1, y2 - y1
                d = max((dx * dx + dy * dy) ** 0.5, 1)
                c.create_line(x1 + dx / d * r, y1 + dy / d * r, x2 - dx / d * (r + 2), y2 - dy / d * (r + 2),
                              fill=EDGE, width=2, arrow="last", arrowshape=(9, 11, 4))
            if node.type is TileType.KINTON:
                x2, y2 = self._xy(node.target)
                mx, my = (x1 + x2) / 2, min(y1, y2) - 3 * r
                c.create_line(x1, y1 - r, mx, my, x2, y2 - r - 2, smooth=True, dash=(5, 4),
                              fill="#81d4fa", width=2, arrow="last", arrowshape=(9, 11, 4))
        self._node_items.clear()
        for node in self.game_map.nodes.values():
            x, y = self._xy(node.id)
            rr = r * 1.25 if node.type is TileType.BOSS else r
            oval = c.create_oval(x - rr, y - rr, x + rr, y + rr, width=2)
            fill, text, _ = TILE_STYLE[node.type]
            if node.amount != 1 and text:
                text = f"{text}{node.amount}"
            size = max(7, int(r * 0.42))
            txt = c.create_text(x, y, text=text, font=("TkDefaultFont", size, "bold"))
            c.create_text(x, y + rr + 8, text=node.label or node.id, fill=MUTED_FG, font=("TkDefaultFont", 7))
            self._node_items[node.id] = (oval, txt)
        self._draw_legend()
        self._token_xy = self._xy(self._token_node)
        tr = r * 0.55
        x, y = self._token_xy
        c.create_oval(x - tr, y - tr, x + tr, y + tr, fill=TOKEN, outline="white", width=3, tags="token")
        c.create_text(c.winfo_width() / 2, 28, text="", fill=PANEL_FG, font=("TkDefaultFont", 15, "bold"), tags="banner")
        self._refresh_nodes()
        self._update_banner()

    def _draw_legend(self) -> None:
        c = self.canvas
        x, y = 14, c.winfo_height() - 22
        for tile, (fill, text, _) in TILE_STYLE.items():
            if tile in (TileType.START, TileType.NORMAL):
                continue
            c.create_rectangle(x, y - 6, x + 12, y + 6, fill=fill, outline="")
            name = tile.value.replace("_item", "").replace("_", " ")
            item = c.create_text(x + 16, y, text=name, anchor="w", fill=MUTED_FG, font=("TkDefaultFont", 8))
            x = c.bbox(item)[2] + 12

    def _refresh_nodes(self) -> None:
        state = self.sim.state
        for node_id, (oval, txt) in self._node_items.items():
            node = self.game_map.node(node_id)
            fill, _, text_color = TILE_STYLE[node.type]
            if node_id in state.consumed:
                fill, text_color = CONSUMED_FILL, CONSUMED_TEXT
            outline, width = "#0b1020", 2
            if node_id in self._highlight:
                outline, width = HIGHLIGHT, 4
            if node_id == self._chosen_node:
                outline, width = CHOSEN, 5
            self.canvas.itemconfig(oval, fill=fill, outline=outline, width=width)
            self.canvas.itemconfig(txt, fill=text_color)
        self.canvas.tag_raise("token")

    def _set_token(self, x: float, y: float) -> None:
        tr = self._radius * 0.55
        self._token_xy = (x, y)
        self.canvas.coords("token", x - tr, y - tr, x + tr, y + tr)
        self.canvas.tag_raise("token")

    def _animate_token(self, node_id: str, duration: int, then: Callable[[], None]) -> None:
        self._token_node = node_id
        (x0, y0), (x1, y1) = self._token_xy, self._xy(node_id)
        frames = max(1, duration // 16)

        def frame(i: int) -> None:
            t = i / frames
            t = t * t * (3 - 2 * t)  # ease in/out
            self._set_token(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
            if i < frames:
                self._after(16, lambda: frame(i + 1))
            else:
                then()

        frame(1)

    def _popup(self, node_id: str, text: str, color: str) -> None:
        x, y = self._xy(node_id)
        item = self.canvas.create_text(x, y - self._radius - 10, text=text, fill=color,
                                       font=("TkDefaultFont", 11, "bold"))
        steps = 20

        def rise(i: int) -> None:
            self.canvas.move(item, 0, -1.2)
            if i < steps:
                self._after(35, lambda: rise(i + 1))
            else:
                self.canvas.delete(item)

        rise(0)

    def _update_banner(self, text: str | None = None, color: str = PANEL_FG) -> None:
        if text is None:
            text, color = self._phase_text()
        self.canvas.itemconfig("banner", text=text, fill=color)
        self.canvas.coords("banner", self.canvas.winfo_width() / 2, 28)

    # -------------------------------------------------------------- side panel

    def _refresh_panel(self) -> None:
        state = self.sim.state
        for key, lbl in self.metric_labels.items():
            lbl.config(text=str(getattr(state.metrics, key)))
        self.score_label.config(text=f"Score ({self.objective.name}): {self.objective.score(state.metrics):.1f}")
        self._draw_dice()
        if not self._halted:
            text, _ = self._phase_text()
            self.status.config(text=text, fg=HIGHLIGHT)

    def _phase_text(self) -> tuple[str, str]:
        state, player = self.sim.state, self.agent is None
        if state.is_terminal:
            return f"STAGE CLEAR in {state.metrics.rolls} rolls!", CHOSEN
        if self.sim.aborted:
            return f"Aborted after {self.sim.max_rolls} rolls", "#ff8a80"
        if state.phase is Phase.CHOOSE_DIE:
            return ("Choose a die (click it or press 1/2/3)" if player else "Choosing a die..."), PANEL_FG
        if state.phase is Phase.CHOOSE_DIRECTION:
            hint = " (click a highlighted tile or press 1/2/3)" if player else "..."
            return f"Branch! {state.steps_remaining} step(s) left - choose a direction{hint}", HIGHLIGHT
        if state.phase is Phase.MOVING:
            return f"Moving... {state.steps_remaining} step(s) left", PANEL_FG
        return "Rolling a new die...", PANEL_FG

    def _draw_dice(self) -> None:
        c = self.dice_canvas
        c.delete("all")
        state = self.sim.state
        size, gap = 84, 24
        for i, value in enumerate(state.dice):
            x, y = 8 + i * (size + gap), 6
            fill, outline, width = "#fafafa", "#0b1020", 2
            if value is None:
                fill = "#3a4562"
            if i == self._flash_slot:
                fill = "#b9f6ca"
            if i == state.active_slot:
                outline, width = HIGHLIGHT, 5
            if i == self._chosen_slot:
                outline, width = CHOSEN, 6
            c.create_rectangle(x, y, x + size, y + size, fill=fill, outline=outline, width=width)
            c.create_text(x + size / 2, y + size / 2, text="·" if value is None else str(value),
                          font=("TkDefaultFont", 30, "bold"), fill="#111" if value else MUTED_FG)
            c.create_text(x + size / 2, y + size + 8, text=f"die {i + 1}", fill=MUTED_FG, font=("TkDefaultFont", 8))

    def _write(self, box: tk.Text, text: str, tag: str | None = None, append: bool = False) -> None:
        box.config(state="normal")
        if not append:
            box.delete("1.0", "end")
        box.insert("end", text + ("\n" if append else ""), tag or ())
        box.see("end")
        box.config(state="disabled")

    def _log(self, text: str, tag: str | None = None) -> None:
        self._write(self.event_text, text, tag, append=True)

    def _show_directions(self, options: tuple[str, ...]) -> None:
        for child in self.directions.winfo_children():
            child.destroy()
        for i, option in enumerate(options):
            tk.Button(self.directions, text=f"{i + 1}: {direction_label(self.game_map, option)}", anchor="w",
                      command=lambda o=option: self._player_choice(o)).pack(fill="x", pady=1)

    # -------------------------------------------------------------- main loop

    def _after(self, ms: int, fn: Callable[[], None]) -> str:
        def run() -> None:
            self._after_ids.discard(after_id)
            if self._alive:
                fn()

        after_id = self.after(ms, run)
        self._after_ids.add(after_id)
        return after_id

    def _schedule_tick(self, delay: int = 0) -> None:
        if self._tick_id is not None:
            self.after_cancel(self._tick_id)
            self._after_ids.discard(self._tick_id)
        self._tick_id = self._after(delay, self._tick)

    def _tick(self) -> None:
        self._tick_id = None
        if self._paused or self._busy or self._halted:
            return
        sim = self.sim
        self._refresh_panel()
        self._update_banner()
        if sim.is_over:
            self._finish()
        elif sim.phase is Phase.MOVING:
            self._play(sim.step(), then=self._schedule_tick)
        elif sim.phase is Phase.ROLL:
            slot = sim.state.active_slot
            events = sim.roll()
            self._flash_slot = slot
            self._play(events, then=lambda: self._after(max(self.speed.step_ms, 120), self._end_flash))
        elif self.agent is None:
            self._await_player()
        else:
            self._agent_turn()

    def _end_flash(self) -> None:
        self._flash_slot = None
        self._draw_dice()
        self._schedule_tick()

    def _play(self, events: list[Event], then: Callable[[], None]) -> None:
        """Animate events one after another, then call ``then``."""
        self._busy = True
        queue = list(events)

        def next_event() -> None:
            if not queue:
                self._busy = False
                self._refresh_panel()
                self._refresh_nodes()
                then()
                return
            event = queue.pop(0)
            if event.kind is not EventKind.MOVE and event.message:
                self._log(f"[roll {self.sim.state.metrics.rolls}] {event.message}")
            if event.kind in POPUPS and event.node:
                fmt, color = POPUPS[event.kind]
                self._popup(event.node, fmt.format(text=event.message, value=event.value), color)
            if event.kind is EventKind.MOVE:
                self._animate_token(event.node, self.speed.step_ms, next_event)
            elif event.kind is EventKind.TELEPORT:
                self._after(self.speed.step_ms, lambda: self._animate_token(event.node, self.speed.step_ms * 3, next_event))
            else:
                self._refresh_nodes()
                next_event()

        next_event()

    def _await_player(self) -> None:
        if self.sim.phase is Phase.CHOOSE_DIRECTION:
            options = self.sim.direction_options()
            self._highlight = set(options)
            self._show_directions(options)
            self._refresh_nodes()

    def _player_choice(self, choice: int | str) -> None:
        if self._busy or self._halted or self.sim.is_over:
            return
        self._apply_choice(choice)

    def _agent_turn(self) -> None:
        state = self.sim.state
        self.status.config(text="Thinking...")
        self.update_idletasks()
        self.agent.last_decision = None
        start = time.perf_counter()
        try:
            if state.phase is Phase.CHOOSE_DIE:
                kind = "die"
                choice = self.agent.choose_die(state, self.game_map)
                if choice not in available_slots(state):
                    raise ValueError(f"choose_die() returned {choice!r}; expected one of {available_slots(state)}")
            else:
                kind = "direction"
                options = self.sim.direction_options()
                choice = self.agent.choose_direction(state, self.game_map, options)
                if choice not in options:
                    raise ValueError(f"choose_direction() returned {choice!r}; expected one of {options}")
        except NotImplementedError as exc:
            self._halt(str(exc))
            return
        except Exception as exc:  # show bugs in agent code in the panel instead of killing the UI
            traceback.print_exc(file=sys.stderr)
            self._halt(f"{type(exc).__name__} in {self.agent.name}:\n{exc}\n(traceback in the terminal)")
            return
        elapsed_ms = (time.perf_counter() - start) * 1000
        self._show_decision(kind, choice, elapsed_ms)
        if kind == "die":
            self._chosen_slot = choice
            self._draw_dice()
        else:
            self._highlight = set(self.sim.direction_options())
            self._chosen_node = choice
            self._refresh_nodes()
        self._after(self.speed.decision_ms, lambda: self._apply_choice(choice))

    def _show_decision(self, kind: str, choice: int | str, elapsed_ms: float) -> None:
        state = self.sim.state
        lines = [f"{self.agent.name} - {kind}"]
        if kind == "die":
            lines.append(f"Current dice: {list(state.dice)}")
        else:
            lines.append(f"Branch at {state.position}, {state.steps_remaining} step(s) left")
        decision = self.agent.last_decision
        if decision is not None:
            lines.append(decision.format())
        else:
            chosen = f"Die {choice + 1}" if kind == "die" else direction_label(self.game_map, choice)
            lines.append(f"Selected: {chosen}")
        lines.append(f"Thinking time: {elapsed_ms:.0f} ms")
        self._write(self.decision_text, "\n".join(lines))

    def _apply_choice(self, choice: int | str) -> None:
        phase = self.sim.phase
        self._chosen_slot = self._chosen_node = None
        self._highlight = set()
        self._show_directions(())
        try:
            events = self.sim.select_die(choice) if phase is Phase.CHOOSE_DIE else self.sim.select_direction(choice)
        except ValueError as exc:
            self._halt(str(exc))
            return
        self._refresh_nodes()
        self._play(events, then=self._schedule_tick)

    def _halt(self, message: str) -> None:
        self._halted = True
        self._write(self.decision_text, message, "error")
        self.status.config(text=message.splitlines()[0], fg="#ff8a80")
        self._update_banner("Stopped - see the AI decision panel", "#ff8a80")
        self._log(message.replace("\n", " | "), "error")
        self._show_end_button()

    def _finish(self) -> None:
        state = self.sim.state
        breakdown = self.objective.breakdown(state.metrics)
        parts = ", ".join(f"{k} {v:+.0f}" for k, v in breakdown.items())
        self._log(f"Final score {self.objective.score(state.metrics):.1f}: {parts}")
        self.pause_button.config(state="disabled")
        self._show_end_button()

    def _show_end_button(self) -> None:
        if not self.end_button.winfo_ismapped():
            # after= puts it ahead of the text boxes in pack order, so it gets space even when the panel is full
            self.end_button.pack(fill="x", padx=12, pady=(0, 4), side="bottom", after=self.button_bar)

    def _back_to_menu(self) -> None:
        self.on_menu(self.run_config)

    def _restart(self) -> None:
        self.on_restart(self.run_config)

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self.pause_button.config(text="Resume" if self._paused else "Pause")
        if self._paused:
            self._update_banner("Paused", HIGHLIGHT)
        else:
            self._schedule_tick()

    # ------------------------------------------------------------------ input

    def _on_key(self, event: tk.Event) -> None:
        if event.keysym == "Escape":
            self._back_to_menu()
            return
        if event.char == " " and self.agent is not None:
            self._toggle_pause()
            return
        if self.agent is not None or event.char not in ("1", "2", "3"):
            return
        index = int(event.char) - 1
        if self.sim.phase is Phase.CHOOSE_DIE and index in available_slots(self.sim.state):
            self._player_choice(index)
        elif self.sim.phase is Phase.CHOOSE_DIRECTION:
            options = self.sim.direction_options()
            if index < len(options):
                self._player_choice(options[index])

    def _on_dice_click(self, event: tk.Event) -> None:
        if self.agent is None and self.sim.phase is Phase.CHOOSE_DIE:
            index = int((event.x - 8) // 108)
            if index in available_slots(self.sim.state):
                self._player_choice(index)

    def _on_canvas_click(self, event: tk.Event) -> None:
        if self.agent is not None or self.sim.phase is not Phase.CHOOSE_DIRECTION:
            return
        for option in self.sim.direction_options():
            x, y = self._xy(option)
            if (event.x - x) ** 2 + (event.y - y) ** 2 <= (self._radius + 4) ** 2:
                self._player_choice(option)
                return

    def destroy(self) -> None:
        self._alive = False
        for after_id in list(self._after_ids):
            self.after_cancel(after_id)
        self.winfo_toplevel().unbind("<Key>")
        super().destroy()
