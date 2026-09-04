# Copyright 2026 Max Brito
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
"""The switcher daemon: grabs Alt+Tab, shows the globe, activates a window."""

import os
import select
import sys
import time

from . import globe as globe_module
from . import ui
from . import x11

SPIN_PERIOD_SECONDS = 48.0
FRAME_INTERVAL = 1.0 / 30.0

# Windows on other workspaces are hidden, matching what most desktops do by
# default. Set to False to switch across every workspace.
CURRENT_DESKTOP_ONLY = True

ALL_DESKTOPS = 0xFFFFFFFF

DEBUG = bool(os.environ.get("GLOBESWITCHER_DEBUG"))


def log(message):
    """Trace switcher activity when GLOBESWITCHER_DEBUG is set."""
    if DEBUG:
        print(f"globeswitcher: {message}", file=sys.stderr, flush=True)

SKIPPED_TYPES = (
    "_NET_WM_WINDOW_TYPE_DESKTOP",
    "_NET_WM_WINDOW_TYPE_DOCK",
    "_NET_WM_WINDOW_TYPE_TOOLBAR",
    "_NET_WM_WINDOW_TYPE_MENU",
    "_NET_WM_WINDOW_TYPE_SPLASH",
    "_NET_WM_WINDOW_TYPE_POPUP_MENU",
    "_NET_WM_WINDOW_TYPE_TOOLTIP",
    "_NET_WM_WINDOW_TYPE_NOTIFICATION",
)


class WindowEntry:
    __slots__ = ("xid", "title", "icon")

    def __init__(self, xid, title, icon):
        self.xid = xid
        self.title = title
        self.icon = icon


class Switcher:
    def __init__(self, generator=None):
        self.display = x11.Display()
        self.canvas = x11.Canvas(self.display)
        self.generator = generator

        short = min(self.display.width, self.display.height)
        self.globe = globe_module.Globe(int(short * ui.GLOBE_FRACTION))

        self._skip_atoms = {self.display.atom(name) for name in SKIPPED_TYPES}
        self._skip_taskbar = self.display.atom("_NET_WM_STATE_SKIP_TASKBAR")

        # Most-recently-used order, newest first. X has no such list, so we
        # keep our own by watching which window the WM makes active.
        self._mru = []
        self._sync_mru()

        self.display.select_input(self.display.root, x11.PROPERTY_CHANGE_MASK)
        self._active_atom = self.display.atom("_NET_ACTIVE_WINDOW")

        self._grabs = []
        self._open = False
        self._entries = []
        self._selected = 0
        self._frame = None
        self._layout = None
        self._opened_at = 0.0
        self._base_rotation = _timezone_rotation()

    # -- key grabs ------------------------------------------------------------

    def grab_shortcuts(self):
        tab = self.display.keycode(x11.XK_Tab)
        for modifiers in (x11.MOD1_MASK, x11.MOD1_MASK | x11.SHIFT_MASK):
            self.display.grab_key(tab, modifiers)
            self._grabs.append((tab, modifiers))

    def ungrab_shortcuts(self):
        for keycode, modifiers in self._grabs:
            self.display.ungrab_key(keycode, modifiers)
        self._grabs.clear()

    # -- window list ----------------------------------------------------------

    def _is_switchable(self, xid):
        if self._skip_taskbar in self.display.window_states(xid):
            return False
        if self._skip_atoms & self.display.window_types(xid):
            return False
        if CURRENT_DESKTOP_ONLY:
            desktop = self.display.window_desktop(xid)
            current = self.display.current_desktop()
            if current >= 0 and desktop >= 0 and desktop != ALL_DESKTOPS \
                    and desktop != current:
                return False
        return True

    def _sync_mru(self):
        """Fold newly seen windows into the MRU list, drop the departed."""
        current = self.display.client_list()
        known = set(self._mru)
        # New windows appear at the top of the stack, so add them front-first.
        for xid in reversed(current):
            if xid not in known:
                self._mru.append(xid)
        alive = set(current)
        self._mru = [xid for xid in self._mru if xid in alive]

    def _note_activation(self):
        active = self.display.active_window()
        if not active:
            return
        if active in self._mru:
            self._mru.remove(active)
        self._mru.insert(0, active)

    def _collect(self):
        self._sync_mru()
        entries = []
        for xid in self._mru:
            if not self._is_switchable(xid):
                continue
            entries.append(WindowEntry(
                xid, self.display.window_title(xid),
                self.display.window_icon(xid)))
        return entries

    # -- the popup ------------------------------------------------------------

    def open(self, backward, timestamp):
        entries = self._collect()
        log(f"open backward={backward} windows={len(entries)}")
        if not entries:
            return False

        if self.generator:
            self.globe.refresh_if_stale(self.generator)
        self.globe.reload_texture()

        screen = x11.grab_screen(self.display)
        if screen is None:
            return False

        self._entries = entries
        self._layout = ui.Layout(
            self.display.width, self.display.height, len(entries))
        self._frame = ui.Frame(ui.dim(screen), self._layout)

        # The window you are on is index 0, so a forward Tab lands on the next
        # one, exactly like every other switcher.
        self._selected = (len(entries) - 1) if backward else min(1, len(entries) - 1)

        self._open = True
        self._opened_at = time.monotonic()

        # Fill the buffer before mapping, so the window never flashes empty.
        self._frame.build_background(
            self._entries, [e.icon for e in self._entries],
            self._selected, self._entries[self._selected].title)
        self.canvas.set_frame(self._frame.background)

        self.canvas.show()
        self.display.sync()

        # XGrabKeyboard only works on a viewable window, so this has to come
        # after the map, not before it.
        if not self.display.grab_keyboard(self.canvas.window, timestamp):
            self._open = False
            self.canvas.hide()
            self._entries = []
            self._frame = None
            self._layout = None
            log("keyboard grab refused")
            return False

        self._paint_globe(blit_all=True)
        log(f"opened, selected={self._selected}")
        return True

    def close(self, activate, timestamp):
        if not self._open:
            return

        self._open = False
        self.canvas.hide()
        self.display.ungrab_keyboard(timestamp)

        log(f"close activate={activate} selected={self._selected}")
        if activate and self._entries:
            entry = self._entries[self._selected]
            self.display.activate_window(entry.xid, timestamp)
            if entry.xid in self._mru:
                self._mru.remove(entry.xid)
            self._mru.insert(0, entry.xid)

        self._entries = []
        self._frame = None
        self._layout = None

    def _redraw_background(self):
        entry = self._entries[self._selected]
        self._frame.build_background(
            self._entries, [e.icon for e in self._entries],
            self._selected, entry.title)
        self.canvas.set_frame(self._frame.background)
        self._paint_globe(blit_all=True)

    def _paint_globe(self, blit_all=False):
        if not self.globe.ready:
            if blit_all:
                self.canvas.blit()
            return

        elapsed = time.monotonic() - self._opened_at
        rotation = self._base_rotation + \
            elapsed / SPIN_PERIOD_SECONDS * 2 * 3.141592653589793

        x, y, width, height = self._layout.globe_box
        patch = self._frame.background[y:y + height, x:x + width].copy()
        rendered = self.globe.render(rotation)

        alpha = self.globe.alpha[..., None]
        blended = patch.astype("float32") * (1.0 - alpha) + \
            rendered.astype("float32") * alpha
        self.canvas.write_rect(blended.astype("uint8"), x, y, blit=not blit_all)

        if blit_all:
            self.canvas.blit()

    def _tick(self):
        if self._open:
            self._paint_globe()

    def select(self, delta):
        if not self._entries:
            return
        self._selected = (self._selected + delta) % len(self._entries)
        log(f"select -> index {self._selected} of {len(self._entries)}")
        self._redraw_background()

    def close_selected(self, timestamp):
        if not self._entries:
            return
        entry = self._entries[self._selected]
        self.display.close_window(entry.xid, timestamp)

        del self._entries[self._selected]
        if not self._entries:
            self.close(False, timestamp)
            return

        self._selected = min(self._selected, len(self._entries) - 1)
        self._layout = ui.Layout(
            self.display.width, self.display.height, len(self._entries))
        self._frame.layout = self._layout
        self._redraw_background()

    # -- main loop ------------------------------------------------------------

    def run(self):
        self.grab_shortcuts()
        try:
            self._loop()
        finally:
            self.ungrab_shortcuts()
            self.canvas.destroy()

    def _loop(self):
        fd = self.display.fd
        while True:
            timeout = FRAME_INTERVAL if self._open else None
            if not self.display.pending():
                select.select([fd], [], [], timeout)

            while self.display.pending():
                self._handle(self.display.next_event())

            self._tick()

    def _handle(self, event):
        if event.type == x11.KEY_PRESS:
            self._on_key_press(event.xkey)
        elif event.type == x11.KEY_RELEASE:
            self._on_key_release(event.xkey)
        elif event.type == x11.EXPOSE and self._open:
            self.canvas.blit()
        elif event.type == x11.PROPERTY_NOTIFY:
            if event.xproperty.atom == self._active_atom and not self._open:
                self._note_activation()

    def _on_key_press(self, key):
        keysym = self.display.keysym(key.keycode, 1 if key.state & x11.SHIFT_MASK else 0)
        backward = bool(key.state & x11.SHIFT_MASK)

        if keysym in (x11.XK_Tab, x11.XK_ISO_Left_Tab):
            if not self._open:
                self.open(backward, key.time)
            else:
                self.select(-1 if backward else 1)
            return

        if not self._open:
            return

        if keysym == x11.XK_Escape:
            self.close(False, key.time)
        elif keysym in (x11.XK_Right, x11.XK_Down):
            self.select(1)
        elif keysym in (x11.XK_Left, x11.XK_Up):
            self.select(-1)
        elif keysym in (x11.XK_w, x11.XK_W, x11.XK_F4, x11.XK_q, x11.XK_Q):
            self.close_selected(key.time)

    def _on_key_release(self, key):
        if not self._open:
            return
        keysym = self.display.keysym(key.keycode, 0)
        if keysym in (x11.XK_Alt_L, x11.XK_Alt_R):
            self.close(True, key.time)


def _timezone_rotation():
    """Rotation that puts the user's own timezone towards the viewer."""
    offset_seconds = -time.timezone if not time.daylight else -time.altzone
    hours = offset_seconds / 3600.0
    return -hours * (3.141592653589793 / 12.0)


def main():
    generator = os.environ.get("GLOBESWITCHER_TEXTURE_TOOL")
    if not generator:
        candidate = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "tools", "globe-texture")
        generator = candidate if os.path.exists(candidate) else None

    Switcher(generator).run()
