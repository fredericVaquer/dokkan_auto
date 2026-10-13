"""Top-level window that switches between the menu and a game view."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from dokkan_pathing.ui.menu import MenuFrame, RunConfig
from dokkan_pathing.ui.visualizer import GameView


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Dokkan Pathing Simulator")
        self.geometry("1360x780")
        self.minsize(1000, 640)
        ttk.Style(self).theme_use("clam")
        self._frame: tk.Widget | None = None
        self.show_menu()

    def _show(self, frame: tk.Widget) -> None:
        if self._frame is not None:
            self._frame.destroy()
        self._frame = frame
        frame.pack(fill="both", expand=True)

    def show_menu(self, config: RunConfig | None = None) -> None:
        self._show(MenuFrame(self, on_start=self.start_game, initial=config))

    def start_game(self, config: RunConfig) -> None:
        self._show(GameView(self, config, on_menu=self.show_menu, on_restart=self.start_game))


def run_app() -> None:
    App().mainloop()
