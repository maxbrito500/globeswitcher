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
"""Laying out and drawing the switcher.

The windows are beads on a ring around the equator of the globe, and they turn
with it. A window's place on screen is therefore a projection of a point in
space, not a position on a flat circle, and which windows are visible falls out
of the drawing order: the far half is drawn first, the globe on top of it, then
the near half. A window crossing the limb is cut exactly at the silhouette
without anyone having to test for it.
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .globe import VIEW_TILT_RADIANS

# Layout, as fractions of the screen's short axis.
GLOBE_FRACTION = 0.40
ITEM_FRACTION = 0.125
ITEM_MIN = 72
ITEM_MAX = 160

# The ring the windows ride on, in globe radii. It has to be wide enough that
# ORBIT_RADIUS * sin(view tilt) > 1, or the window at the front projects inside
# the globe's disc instead of standing clear of it.
ORBIT_RADIUS = 1.75

# How much nearer windows grow. This is what makes the turn read as three
# dimensional rather than as icons sliding sideways.
DEPTH_SCALE = 0.18

# Windows on the far side are mostly hidden by the globe; the sliver that
# shows past the limb is dimmed so it reads as behind.
BACK_OPACITY = 0.55

BACKDROP_DIM = 0.34             # how much of the desktop's brightness remains

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)


def _load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


class Bead:
    """One window, placed in space at a given globe rotation."""

    __slots__ = ("index", "x", "y", "depth", "size", "opacity")

    def __init__(self, index, x, y, depth, size, opacity):
        self.index = index
        self.x = x                  # centre, in screen pixels
        self.y = y
        self.depth = depth          # > 0 towards the viewer
        self.size = size
        self.opacity = opacity

    @property
    def box(self):
        half = self.size // 2 + 1
        return (self.x - half, self.y - half, self.x + half, self.y + half)


class Layout:
    """Where the globe sits, and where each window is at a given rotation."""

    def __init__(self, width, height, count):
        self.width = width
        self.height = height
        self.count = max(count, 1)
        short = min(width, height)

        self.centre = (width // 2, height // 2)
        self.globe_diameter = int(short * GLOBE_FRACTION)
        self.globe_radius = self.globe_diameter / 2.0

        # A crowded equator needs smaller beads or they smear into each other
        # at the limbs, where they bunch up.
        crowding = 1.0 if self.count <= 8 else max(0.62, 8.0 / self.count)
        self.item_size = int(min(ITEM_MAX, max(
            ITEM_MIN, short * ITEM_FRACTION * crowding)))

        # How far above and below the centre the ring reaches on screen.
        self.orbit_rise = (ORBIT_RADIUS * math.sin(VIEW_TILT_RADIANS)
                           * self.globe_radius)

    @property
    def max_item_size(self):
        """The biggest a window gets, which is at the front of the ring."""
        return int(self.item_size * (1.0 + DEPTH_SCALE))

    @property
    def region(self):
        """The rectangle the switcher ever draws in.

        Fixed for the life of a popup: it is the globe, the whole ring at its
        widest, and the title plate. Keeping it constant means the dimmed
        backdrop under it can be prepared once instead of re-cropped every
        frame.
        """
        cx, cy = self.centre
        reach = self.max_item_size / 2 + 4
        half_width = ORBIT_RADIUS * self.globe_radius + reach

        left = cx - half_width
        right = cx + half_width
        top = cy - max(self.globe_radius, self.orbit_rise + reach)
        bottom = max(cy + self.globe_radius,
                     cy + self.orbit_rise + reach,
                     self.title_top + self.title_height)

        return (max(0, int(left)), max(0, int(top)),
                min(self.width, int(right) + 1),
                min(self.height, int(bottom) + 1))

    @property
    def title_height(self):
        return int(self.globe_diameter * 0.075) + 30

    @property
    def title_top(self):
        """Where the title plate sits: below the globe and below the ring."""
        _, cy = self.centre
        clearance = max(self.globe_radius,
                        self.orbit_rise + self.item_size * 0.75)
        return int(cy + clearance + 18)

    @property
    def globe_box(self):
        cx, cy = self.centre
        half = self.globe_diameter // 2
        return (cx - half, cy - half, self.globe_diameter, self.globe_diameter)

    def longitude(self, index):
        """The fixed longitude a window is pinned to on the globe."""
        return index * 2.0 * math.pi / self.count

    def orbit(self, rotation):
        """Every window's place on screen, far ones first.

        `rotation` is the globe's own rotation, in the same sense
        `globe.Globe.render` uses it, so the beads and the coastlines turn
        together.
        """
        cx, cy = self.centre
        tilt = VIEW_TILT_RADIANS
        cos_t, sin_t = math.cos(tilt), math.sin(tilt)

        beads = []
        for index in range(self.count):
            # Where this window has turned to, as seen from here.
            lon = self.longitude(index) - rotation

            mx = ORBIT_RADIUS * math.sin(lon)
            mz = ORBIT_RADIUS * math.cos(lon)

            # The same camera as the globe: lifted above the equator looking
            # down, so the near side of the ring hangs below the centre. The
            # beads sit on the equator, so the world y term is zero.
            ny = -sin_t * mz
            nz = cos_t * mz

            depth = nz
            size = int(self.item_size * (1.0 + DEPTH_SCALE * depth / ORBIT_RADIUS))
            opacity = 1.0 if depth >= 0 else BACK_OPACITY

            beads.append(Bead(
                index,
                int(cx + mx * self.globe_radius),
                int(cy - ny * self.globe_radius),
                depth, size, opacity))

        beads.sort(key=lambda bead: bead.depth)
        return beads


class IconCache:
    """Icons prescaled once, then reused at whatever size a frame asks for.

    A roll only visits a few dozen distinct sizes, so after the first turn
    every lookup is a hit and no frame pays for a resample.
    """

    QUANTUM = 4

    def __init__(self, icons, titles, max_size):
        self._sources = []
        for icon, title in zip(icons, titles):
            self._sources.append(
                _trim(icon) if icon is not None else _letter_tile(title))
        self._max_size = max_size
        self._cache = {}

    def get(self, index, size):
        size = max(8, int(round(size / self.QUANTUM)) * self.QUANTUM)
        key = (index, size)
        tile = self._cache.get(key)
        if tile is None:
            tile = _fit_square(self._sources[index], size)
            self._cache[key] = tile
        return tile


def _trim(icon):
    """Drop an icon's transparent padding.

    Application icons pad themselves by wildly different amounts, and without
    trimming a ring of them looks assembled at random sizes.
    """
    image = Image.fromarray(icon, "RGBA")
    box = image.getchannel("A").getbbox()
    return image.crop(box) if box else image


def _letter_tile(title):
    """A stand-in tile for windows that ship no icon."""
    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(size * 0.18),
                           fill=(70, 80, 100, 235))

    letter = (title.strip()[:1] or "?").upper()
    draw.text((size / 2, size / 2), letter, font=_load_font(int(size * 0.5)),
              fill=(235, 240, 250, 255), anchor="mm")
    return image


def _fit_square(image, size):
    """Scale into a `size` square, keeping the aspect ratio."""
    scale = size / max(image.width, image.height)
    scaled = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.LANCZOS)
    if scaled.size == (size, size):
        return scaled

    square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    square.paste(scaled, ((size - scaled.width) // 2,
                          (size - scaled.height) // 2))
    return square


def dim(rgb, factor=BACKDROP_DIM):
    """Darken the captured desktop so the switcher reads on top of it."""
    return (rgb.astype(np.uint16) * int(factor * 256) >> 8).astype(np.uint8)


class Frame:
    """Draws a frame of the switcher over a fixed, already dimmed backdrop."""

    def __init__(self, backdrop, layout, icons, titles):
        self.backdrop = backdrop            # RGB uint8, screen sized
        self.layout = layout
        self.titles = titles
        self.icons = IconCache(
            icons, titles,
            int(layout.item_size * (1.0 + DEPTH_SCALE)))
        self._title_font = _load_font(
            max(15, int(layout.globe_diameter * 0.075)))

        left, top, right, bottom = layout.region
        self._origin = (left, top)
        self._base = Image.fromarray(
            backdrop[top:bottom, left:right], "RGB").convert("RGBA")

    # -- drawing --------------------------------------------------------------

    def render(self, rotation, selected, globe_rgb, globe_alpha):
        """Compose one frame. Returns (RGB block, x, y) ready to blit."""
        layout = self.layout
        beads = layout.orbit(rotation)
        left, top = self._origin
        canvas = self._base.copy()

        # Far half, then the globe, then the near half. The globe is opaque
        # inside its disc, so it cuts the far half at the silhouette.
        for bead in beads:
            if bead.depth < 0:
                self._draw_bead(canvas, bead, selected, left, top)

        self._draw_globe(canvas, globe_rgb, globe_alpha, left, top)

        for bead in beads:
            if bead.depth >= 0:
                self._draw_bead(canvas, bead, selected, left, top)

        self._draw_title(canvas, self.titles[selected], left, top)

        block = np.asarray(canvas.convert("RGB"), dtype=np.uint8)
        return block, left, top

    def _draw_globe(self, canvas, globe_rgb, globe_alpha, left, top):
        gx, gy, gw, gh = self.layout.globe_box
        rgba = np.empty((gh, gw, 4), dtype=np.uint8)
        rgba[..., :3] = globe_rgb
        rgba[..., 3] = (globe_alpha * 255).astype(np.uint8)
        canvas.alpha_composite(
            Image.fromarray(rgba, "RGBA"), (gx - left, gy - top))

    def _draw_bead(self, canvas, bead, selected, left, top):
        tile = self.icons.get(bead.index, bead.size)
        size = tile.width
        x = bead.x - size // 2 - left
        y = bead.y - size // 2 - top

        if bead.index == selected:
            self._draw_highlight(canvas, x, y, size)

        if bead.opacity < 1.0:
            faded = tile.copy()
            faded.putalpha(faded.getchannel("A").point(
                lambda value: int(value * bead.opacity)))
            tile = faded

        canvas.alpha_composite(tile, (x, y))

    def _draw_highlight(self, canvas, x, y, size):
        """A soft halo behind the window at the front."""
        pad = int(size * 0.22)
        glow = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)

        steps = 6
        for step in range(steps, 0, -1):
            inset = int(pad * (step - 1) / steps)
            alpha = int(26 * (steps - step + 1) / steps)
            draw.rounded_rectangle(
                (inset, inset, glow.width - 1 - inset, glow.height - 1 - inset),
                radius=int(size * 0.24), fill=(130, 180, 255, alpha))

        draw.rounded_rectangle(
            (pad - 3, pad - 3, glow.width - pad + 2, glow.height - pad + 2),
            radius=int(size * 0.20), outline=(255, 255, 255, 235), width=3)

        canvas.alpha_composite(glow, (x - pad, y - pad))

    def _draw_title(self, canvas, title, left, top):
        if not title:
            return

        layout = self.layout
        cx, cy = layout.centre
        draw = ImageDraw.Draw(canvas)

        text = title if len(title) <= 90 else title[:89] + "…"
        box = draw.textbbox((0, 0), text, font=self._title_font)
        text_width, text_height = box[2] - box[0], box[3] - box[1]

        pad_x, pad_y = 16, 9
        plate_top = layout.title_top - top
        plate_left = cx - text_width // 2 - left

        plate = Image.new(
            "RGBA", (text_width + pad_x * 2, text_height + pad_y * 2),
            (0, 0, 0, 0))
        ImageDraw.Draw(plate).rounded_rectangle(
            (0, 0, plate.width - 1, plate.height - 1), radius=10,
            fill=(0, 0, 0, 185))
        canvas.alpha_composite(plate, (plate_left - pad_x, plate_top - pad_y))

        draw.text((cx - left, plate_top - box[1]), text, font=self._title_font,
                  fill=(255, 255, 255, 255), anchor="ma")
