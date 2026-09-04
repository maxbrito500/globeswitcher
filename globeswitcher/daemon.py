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
"""The switcher daemon: grabs Alt+Tab, rolls the globe, activates a window."""

import math
import os
import select
import sys
import time

from PIL import Image

from . import globe as globe_module
from . import ui
from . import x11

FRAME_INTERVAL = 1.0 / 60.0

# How long the globe takes to roll one window round to the front. Rolling
# further -- wrapping from the last window back to the first, which travels
# the whole arc -- is given proportionally longer, up to a limit, so a long
# turn reads as a turn rather than a jump.
ROLL_DURATION = 0.26
ROLL_DURATION_MAX = 0.62

# Window thumbnails. Captured at Alt+Tab time, kept briefly so a second
# Alt+Tab is instant, and bounded so a desktop full of windows cannot make
# opening the switcher feel slow: whatever is left over falls back to the
# application icon and gets captured on the next open.
THUMBNAIL_LONG_EDGE = 480
THUMBNAIL_TTL = 20.0
THUMBNAIL_BUDGET = 0.10

# Windows on other workspaces are hidden, matching what most desktops do by
# default. Set to False to switch across every workspace.
CURRENT_DESKTOP_ONLY = True

ALL_DESKTOPS = 0xFFFFFFFF
TWO_PI = 2.0 * math.pi

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

DEBUG = bool(os.environ.get("GLOBESWITCHER_DEBUG"))


def log(message):
    """Trace switcher activity when GLOBESWITCHER_DEBUG is set."""
    if DEBUG:
        print(f"globeswitcher: {message}", file=sys.stderr, flush=True)


def shortest_turn(delta):
    """Fold an angle difference into the shorter way round the circle."""
    return (delta + math.pi) % TWO_PI - math.pi


def local_meridian():
    """The rotation that turns the user's own part of the world to the front.

    The map already carries the terminator for right now, but a globe pinned
    to the prime meridian shows a dark face all evening while the daylight
    sits round the back. Facing the viewer's own longitude puts the daylight
    where they care about it, and shows whether their own part of the world is
    still in it. Fifteen degrees of longitude an hour, from the clock's own
    offset from UTC.
    """
    local = time.localtime()
    offset_seconds = -(time.altzone if local.tm_isdst and time.daylight
                       else time.timezone)
    return offset_seconds / 3600.0 * (math.pi / 12.0)


class WindowEntry:
    __slots__ = ("xid", "title", "icon", "thumbnail")

    def __init__(self, xid, title, icon):
        self.xid = xid
        self.title = title
        self.icon = icon
        self.thumbnail = None


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

        self._thumbnails = {}       # xid -> (image, captured at)
        self._icons = {}            # xid -> icon array, or None

        self.display.select_input(self.display.root, x11.PROPERTY_CHANGE_MASK)
        self._active_atom = self.display.atom("_NET_ACTIVE_WINDOW")

        self._grabs = []
        self._open = False
        self._entries = []
        self._selected = 0
        self._frame = None
        self._layout = None

        # Rotation animation.
        self._rotation = 0.0
        self._roll_from = 0.0
        self._roll_to = 0.0
        self._roll_start = 0.0
        self._roll_duration = ROLL_DURATION

        # Added to the ring's rotation when sampling the map, so the geography
        # on show is set by the clock while the ring still lines up with the
        # selected window.
        self._meridian = local_meridian()

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
                xid, self.display.window_title(xid), self._icon(xid)))
        return entries

    def _icon(self, xid):
        """A window's application icon, read once and remembered.

        Some applications ship a megabyte of icon sizes in the property, and
        an icon does not change over a window's life.
        """
        if xid not in self._icons:
            self._icons[xid] = self.display.window_icon(xid)
        return self._icons[xid]

    def _thumbnail(self, xid, deadline):
        """A small picture of a window's contents, or None.

        Returns a cached image straight away; otherwise captures one, unless
        the time budget for this open has already run out.
        """
        cached = self._thumbnails.get(xid)
        now = time.monotonic()
        if cached is not None and now - cached[1] < THUMBNAIL_TTL:
            return cached[0]

        if now >= deadline:
            return cached[0] if cached else None

        rgb = x11.capture_window(self.display, xid)
        if rgb is None:
            return cached[0] if cached else None

        image = Image.fromarray(rgb, "RGB")
        image.thumbnail((THUMBNAIL_LONG_EDGE, THUMBNAIL_LONG_EDGE),
                        Image.BILINEAR)
        self._thumbnails[xid] = (image, now)
        return image

    def _forget_dead_windows(self):
        alive = set(self._mru)
        for cache in (self._thumbnails, self._icons):
            for xid in [xid for xid in cache if xid not in alive]:
                del cache[xid]

    # -- rotation -------------------------------------------------------------

    def _roll_to_selected(self, immediate=False):
        """Aim the globe so the selected window ends up facing the viewer."""
        target = self._layout.longitude(self._selected)
        if immediate:
            self._rotation = target
            self._roll_from = self._roll_to = target
            self._roll_start = 0.0
            self._roll_duration = ROLL_DURATION
            return

        # Retarget from wherever the globe is right now, so a Tab pressed
        # mid-roll stays smooth instead of queueing up behind the last one.
        self._roll_from = self._rotation
        self._roll_to = self._rotation + shortest_turn(target - self._rotation)
        self._roll_start = time.monotonic()

        steps = abs(self._roll_to - self._roll_from) / max(self._layout.step, 1e-6)
        self._roll_duration = min(
            ROLL_DURATION_MAX, ROLL_DURATION * max(1.0, steps ** 0.5))

    @property
    def _rolling(self):
        return self._roll_start > 0.0

    def _advance(self):
        """Step the roll animation. Returns True if the globe moved."""
        if not self._rolling:
            return False

        progress = (time.monotonic() - self._roll_start) / self._roll_duration
        if progress >= 1.0:
            self._rotation = self._roll_to
            self._roll_start = 0.0
            return True

        eased = 1.0 - (1.0 - progress) ** 3          # ease out cubic
        self._rotation = self._roll_from + \
            (self._roll_to - self._roll_from) * eased
        return True

    # -- the popup ------------------------------------------------------------

    def open(self, backward, timestamp):
        started = time.monotonic()
        entries = self._collect()
        log(f"open backward={backward} windows={len(entries)}")
        if not entries:
            return False

        if self.generator:
            self.globe.refresh_if_stale(self.generator)
        self.globe.reload_texture()
        self._meridian = local_meridian()

        screen = x11.grab_screen(self.display)
        if screen is None:
            return False

        deadline = time.monotonic() + THUMBNAIL_BUDGET
        for entry in entries:
            entry.thumbnail = self._thumbnail(entry.xid, deadline)
        self._forget_dead_windows()

        self._entries = entries
        self._layout = ui.Layout(
            self.display.width, self.display.height, len(entries))
        self._frame = ui.Frame(
            ui.dim(screen), self._layout,
            [entry.thumbnail for entry in entries],
            [entry.icon for entry in entries],
            [entry.title for entry in entries])

        # Start with the window you are on facing you, then roll to the next
        # one, so opening the switcher is itself a visible turn.
        self._selected = 0
        self._roll_to_selected(immediate=True)
        self._selected = (len(entries) - 1) if backward else \
            min(1, len(entries) - 1)
        self._roll_to_selected()

        self._open = True

        # Fill the whole buffer with the dimmed desktop before mapping, so the
        # window never flashes empty and the area outside the animated region
        # is already correct.
        self.canvas.set_frame(self._frame.backdrop)
        self.canvas.show()
        self.display.sync()

        # XGrabKeyboard only works on a viewable window, so this has to come
        # after the map, not before it.
        if not self.display.grab_keyboard(self.canvas.window, timestamp):
            log("keyboard grab refused")
            self._teardown()
            return False

        self._paint(blit_all=True)
        thumbs = sum(1 for entry in entries if entry.thumbnail is not None)
        log(f"opened selected={self._selected} thumbnails={thumbs}/{len(entries)}"
            f" in {(time.monotonic() - started) * 1000:.0f} ms")
        return True

    def _teardown(self):
        self._open = False
        self.canvas.hide()
        self._entries = []
        self._frame = None
        self._layout = None
        self._roll_start = 0.0

    def close(self, activate, timestamp):
        if not self._open:
            return

        log(f"close activate={activate} selected={self._selected}")
        entry = self._entries[self._selected] if self._entries else None

        self._teardown()
        self.display.ungrab_keyboard(timestamp)

        if activate and entry is not None:
            self.display.activate_window(entry.xid, timestamp)
            if entry.xid in self._mru:
                self._mru.remove(entry.xid)
            self._mru.insert(0, entry.xid)

    def select(self, delta):
        if len(self._entries) < 2:
            return
        self._selected = (self._selected + delta) % len(self._entries)
        log(f"select -> index {self._selected} of {len(self._entries)}")
        self._roll_to_selected()
        self._paint()

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
        self._frame = ui.Frame(
            self._frame.backdrop, self._layout,
            [e.thumbnail for e in self._entries],
            [e.icon for e in self._entries],
            [e.title for e in self._entries])
        self._roll_to_selected(immediate=True)
        self._paint(blit_all=True)

    # -- painting -------------------------------------------------------------

    def _paint(self, blit_all=False):
        if not self._open:
            return

        # render() hands back its own reusable buffer, and returns a blank
        # sphere rather than nothing when the map has not been generated yet.
        rendered = self.globe.render(self._rotation + self._meridian)

        block, x, y = self._frame.render(
            self._rotation, self._selected, rendered, self.globe.alpha)
        self.canvas.write_rect(block, x, y, blit=not blit_all)

        if blit_all:
            self.canvas.blit()

    def _tick(self):
        if self._open and self._advance():
            self._paint()

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
            # Only wake for frames while the globe is actually turning; a
            # switcher sitting still should cost nothing.
            timeout = FRAME_INTERVAL if (self._open and self._rolling) else None
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
        keysym = self.display.keysym(
            key.keycode, 1 if key.state & x11.SHIFT_MASK else 0)
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


def main():
    generator = os.environ.get("GLOBESWITCHER_TEXTURE_TOOL")
    if not generator:
        candidate = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "tools", "globe-texture")
        generator = candidate if os.path.exists(candidate) else None

    Switcher(generator).run()
