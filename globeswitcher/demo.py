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
"""Render a switcher frame to a file, using invented windows.

Used for the screenshot in the README and for checking layout changes without
an X server. Nothing here reads the real desktop, so the output never contains
anything private.
"""

import math
import os

import numpy as np
from PIL import Image

from . import globe as globe_module
from . import ui

DEMO_WINDOWS = [
    ("Firefox", ("firefox", "firefox-esr")),
    ("Terminal", ("utilities-terminal", "org.gnome.Terminal")),
    ("Files", ("system-file-manager", "org.gnome.Nautilus", "Thunar")),
    ("Text Editor", ("accessories-text-editor", "org.gnome.TextEditor")),
    ("LibreOffice Writer", ("libreoffice-writer",)),
    ("Image Viewer", ("multimedia-photo-viewer", "org.gnome.eog", "gimp")),
]

ICON_DIRS = (
    "/usr/share/icons/hicolor/256x256/apps",
    "/usr/share/icons/hicolor/128x128/apps",
    "/usr/share/icons/hicolor/96x96/apps",
    "/usr/share/pixmaps",
)


class DemoWindow:
    def __init__(self, title, icon):
        self.title = title
        self.icon = icon


def _find_icon(names):
    for directory in ICON_DIRS:
        for name in names:
            path = os.path.join(directory, f"{name}.png")
            if os.path.exists(path):
                try:
                    with Image.open(path) as image:
                        return np.asarray(image.convert("RGBA"), dtype=np.uint8)
                except OSError:
                    continue
    return None


def _backdrop(width, height):
    """A neutral gradient standing in for a desktop."""
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    fade = (0.55 * y + 0.45 * (1.0 - x))

    rgb = np.empty((height, width, 3), dtype=np.float32)
    rgb[..., 0] = 24 + 26 * fade
    rgb[..., 1] = 28 + 34 * fade
    rgb[..., 2] = 40 + 52 * fade
    return rgb.astype(np.uint8)


def render(path, width=1920, height=1080, selected=1, rotation=None):
    windows = [DemoWindow(title, _find_icon(names))
               for title, names in DEMO_WINDOWS]

    layout = ui.Layout(width, height, len(windows))
    frame = ui.Frame(_backdrop(width, height), layout)
    background = frame.build_background(
        windows, [w.icon for w in windows], selected, windows[selected].title)

    canvas = background.copy()
    earth = globe_module.Globe(layout.globe_diameter)
    if earth.ready:
        # A view centred on the Atlantic shows land on both sides of the
        # terminator, which reads better in a still image than a random angle.
        turn = math.pi * 0.15 if rotation is None else rotation
        frame.compose(earth.render(turn), earth.alpha, canvas)

    Image.fromarray(canvas, "RGB").save(path)
    return path
