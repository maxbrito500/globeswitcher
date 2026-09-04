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
import random

import numpy as np
from PIL import Image, ImageDraw

from . import globe as globe_module
from . import ui

# Title, icon names to look for, window shape, and the palette its invented
# contents are drawn in.
DEMO_WINDOWS = [
    ("Firefox", ("firefox", "firefox-esr"), (16, 10), (38, 42, 58)),
    ("Terminal", ("utilities-terminal", "org.gnome.Terminal"), (4, 3), (18, 20, 26)),
    ("Files", ("system-file-manager", "org.gnome.Nautilus", "Thunar"), (16, 11), (46, 48, 54)),
    ("Text Editor", ("accessories-text-editor", "org.gnome.TextEditor"), (3, 4), (30, 33, 40)),
    ("LibreOffice Writer", ("libreoffice-writer",), (4, 3), (240, 240, 238)),
    ("Image Viewer", ("multimedia-photo-viewer", "org.gnome.eog", "gimp"), (16, 9), (26, 28, 34)),
]

ICON_DIRS = (
    "/usr/share/icons/hicolor/256x256/apps",
    "/usr/share/icons/hicolor/128x128/apps",
    "/usr/share/icons/hicolor/96x96/apps",
    "/usr/share/pixmaps",
)


class DemoWindow:
    def __init__(self, title, icon, thumbnail):
        self.title = title
        self.icon = icon
        self.thumbnail = thumbnail


def _mock_window(shape, palette, seed):
    """An invented window screenshot.

    The real switcher shows a capture of each window. For the screenshot in
    the README that would mean publishing whatever happened to be on the
    author's desktop, so the demo draws plausible windows instead.
    """
    aspect_w, aspect_h = shape
    width, height = aspect_w * 34, aspect_h * 34
    image = Image.new("RGB", (width, height), palette)
    draw = ImageDraw.Draw(image)

    light = sum(palette) > 380
    ink = (60, 62, 68) if light else (196, 202, 214)
    chrome = tuple(min(255, channel + (14 if light else 22)) for channel in palette)

    bar = max(14, height // 12)
    draw.rectangle((0, 0, width, bar), fill=chrome)
    for i in range(3):
        cx = 12 + i * 14
        draw.ellipse((cx - 4, bar // 2 - 4, cx + 4, bar // 2 + 4),
                     fill=(232, 116, 96) if i == 0 else
                          (230, 190, 96) if i == 1 else (128, 200, 128))

    rng = random.Random(seed)
    y = bar + 14
    while y < height - 10:
        run = rng.randint(int(width * 0.18), int(width * 0.82))
        thickness = max(3, height // 46)
        draw.rounded_rectangle((16, y, 16 + run, y + thickness),
                               radius=thickness // 2,
                               fill=tuple(int(c * rng.uniform(0.55, 1.0)) for c in ink))
        y += thickness + max(6, height // 28)

    return image


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


def render(path, width=1920, height=1080, selected=2, rotation=None):
    """Draw one switcher frame to `path`.

    `rotation` defaults to a little short of the selected window's longitude,
    so the still shows the globe caught mid-roll rather than perfectly settled.
    """
    windows = [
        DemoWindow(title, _find_icon(names), _mock_window(shape, palette, index))
        for index, (title, names, shape, palette) in enumerate(DEMO_WINDOWS)]

    backdrop = ui.dim(_backdrop(width, height))
    layout = ui.Layout(width, height, len(windows))
    frame = ui.Frame(backdrop, layout,
                     [w.thumbnail for w in windows],
                     [w.icon for w in windows],
                     [w.title for w in windows])

    if rotation is None:
        step = 2.0 * math.pi / len(windows)
        rotation = layout.longitude(selected) - step * 0.18

    earth = globe_module.Globe(layout.globe_diameter)
    globe_rgb = earth.render(rotation)

    canvas = np.array(backdrop, copy=True)
    block, x, y = frame.render(rotation, selected, globe_rgb, earth.alpha)
    canvas[y:y + block.shape[0], x:x + block.shape[1]] = block

    Image.fromarray(canvas, "RGB").save(path)
    return path
