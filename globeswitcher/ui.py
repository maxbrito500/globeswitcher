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

Compositing is done in numpy rather than PIL. Every pixel of the animated
region changes on every frame, and at 60 fps the conversions in and out of PIL
images cost more than the drawing itself.
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .globe import VIEW_TILT_RADIANS

# Layout, as fractions of the screen's short axis.
GLOBE_FRACTION = 0.50
ITEM_FRACTION = 0.377
ITEM_MIN = 218
ITEM_MAX = 494

# The ring the windows ride on, in globe radii. Wide enough that
# ORBIT_RADIUS * sin(view tilt) is about 1, which puts the window at the front
# on the globe's lower rim rather than across its face.
ORBIT_RADIUS = 2.40

# How far the ring floats above the equatorial plane, in globe radii. A ring
# lying exactly on the equator projects far below the globe's centre -- the
# camera tilt multiplies the offset by the ring's radius -- and the windows end
# up sweeping past the south pole. Lifting the ring slides the whole ellipse
# back up, so it crosses just below the equator where it belongs.
ORBIT_LIFT = 0.765

# The gap between neighbouring windows on the ring. Fixed rather than
# 360/n, so a handful of windows sit together as a band across the equator
# instead of being flung out to the four cardinal points. It is only with
# something like twenty windows that the ring closes and they wrap right
# around the world.
ANGULAR_STEP = math.radians(22.0)

# How much nearer windows grow. This is what makes the turn read as three
# dimensional rather than as thumbnails sliding sideways.
DEPTH_SCALE = 0.18

# Windows on the far side are mostly hidden by the globe; the sliver that
# shows past the limb is dimmed so it reads as behind.
BACK_OPACITY = 0.55

BACKDROP_DIM = 0.34             # how much of the desktop's brightness remains

BADGE_FRACTION = 0.34           # app icon badge, relative to the tile's height

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


# --- compositing -------------------------------------------------------------


def blend(canvas, rgb, alpha, x, y):
    """Alpha-blend an RGB block into `canvas` at (x, y), clipped to it.

    `alpha` is uint8 and the arithmetic is 16-bit integer. At these sizes the
    round trip through float is the most expensive thing a frame would do.
    """
    height, width = rgb.shape[:2]
    canvas_height, canvas_width = canvas.shape[:2]

    sx, sy = max(0, -x), max(0, -y)
    ex = min(width, canvas_width - x)
    ey = min(height, canvas_height - y)
    if ex <= sx or ey <= sy:
        return

    target = canvas[y + sy:y + ey, x + sx:x + ex]
    source = rgb[sy:ey, sx:ex]
    a = alpha[sy:ey, sx:ex, None]

    # target + (source - target) * a / 255, in 32-bit integers. A difference
    # times an alpha reaches 255 * 255, which overflows int16, and 8-bit
    # channels are cheap enough to widen.
    delta = source.astype(np.int32)
    delta -= target
    delta *= a
    # Divide by 255 the exact way: (v + 128 + ((v + 128) >> 8)) >> 8.
    delta += 128
    delta += delta >> 8
    delta >>= 8
    delta += target
    np.clip(delta, 0, 255, out=delta)
    target[:] = delta.astype(np.uint8)


def copy_rect(canvas, rgb, x, y):
    """Drop an opaque block into `canvas` at (x, y), clipped to it."""
    height, width = rgb.shape[:2]
    canvas_height, canvas_width = canvas.shape[:2]

    sx, sy = max(0, -x), max(0, -y)
    ex = min(width, canvas_width - x)
    ey = min(height, canvas_height - y)
    if ex <= sx or ey <= sy:
        return

    canvas[y + sy:y + ey, x + sx:x + ex] = rgb[sy:ey, sx:ex]


def opaque_inset(alpha, limit_fraction=0.34):
    """The smallest border width outside which every pixel is solid.

    Window tiles are rounded rectangles: only the corners and the hairline
    edge are partly transparent, and everything inside is opaque. Copying that
    interior instead of alpha-blending it is most of the cost of drawing a
    tile, and at these sizes the tiles are the most expensive thing in a frame.

    Returns None when no such border exists, as for a bare application icon.
    """
    height, width = alpha.shape
    limit = int(min(height, width) * limit_fraction)
    if limit < 1:
        return None

    # The property is monotone in the inset, so binary search finds the edge.
    low, high, found = 0, limit, None
    while low <= high:
        middle = (low + high) // 2
        block = alpha[middle:height - middle, middle:width - middle]
        if block.size and block.min() == 255:
            found = middle
            high = middle - 1
        else:
            low = middle + 1
    return found


def split_rgba(image):
    """A PIL RGBA image as (contiguous RGB array, contiguous alpha array)."""
    data = np.asarray(image, dtype=np.uint8)
    return (np.ascontiguousarray(data[..., :3]),
            np.ascontiguousarray(data[..., 3]))


# --- geometry ----------------------------------------------------------------


class Bead:
    """One window, placed in space at a given globe rotation."""

    __slots__ = ("index", "x", "y", "depth", "height", "opacity")

    def __init__(self, index, x, y, depth, height, opacity):
        self.index = index
        self.x = x                  # centre, in screen pixels
        self.y = y
        self.depth = depth          # > 0 towards the viewer
        self.height = height        # box size; the tile keeps its own aspect
        self.opacity = opacity


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

        # A crowded ring needs smaller tiles, or they smear into each other at
        # the limbs where the spacing foreshortens.
        crowding = 1.0 if self.count <= 8 else max(0.62, 8.0 / self.count)
        self.item_size = int(min(ITEM_MAX, max(
            ITEM_MIN, short * ITEM_FRACTION * crowding)))

        # How far below the centre the near side of the ring reaches. The far
        # side's height depends on how far round the windows actually go, so
        # it is worked out from the span rather than assumed to be the whole
        # ring; see `orbit_top`.
        tilt = VIEW_TILT_RADIANS
        self.orbit_rise = ((ORBIT_RADIUS * math.sin(tilt)
                            - ORBIT_LIFT * math.cos(tilt)) * self.globe_radius)

    @property
    def orbit_top(self):
        """How far above the centre the furthest window can reach.

        Reserving the whole ring's height would leave a band of the screen
        being repainted for windows that are never there: with a handful of
        them the ring is an arc, not a circle.
        """
        tilt = VIEW_TILT_RADIANS
        highest = (math.cos(tilt) * ORBIT_LIFT
                   - math.sin(tilt) * ORBIT_RADIUS * math.cos(self.span))
        return highest * self.globe_radius

    @property
    def max_item_size(self):
        """The biggest a window gets, which is at the front of the ring."""
        return int(self.item_size * (1.0 + DEPTH_SCALE))

    @property
    def title_height(self):
        return int(self.globe_diameter * 0.062) + 30

    @property
    def title_top(self):
        """Where the title plate sits: below the globe and below the ring."""
        _, cy = self.centre
        clearance = max(self.globe_radius,
                        self.orbit_rise + self.item_size * 0.60)
        return int(cy + clearance + 16)

    @property
    def globe_box(self):
        cx, cy = self.centre
        half = self.globe_diameter // 2
        return (cx - half, cy - half, self.globe_diameter, self.globe_diameter)

    @property
    def region(self):
        """The rectangle the switcher ever draws in.

        Fixed for the life of a popup: the globe, the whole ring at its widest,
        and the title plate. Keeping it constant means the dimmed backdrop
        under it can be prepared once instead of re-cropped every frame.
        """
        cx, cy = self.centre
        reach = self.max_item_size / 2 + 6
        span = self.span

        # Only the arc the windows can actually reach needs room. With a few
        # windows they never swing far from the front, and the region stays
        # small enough to keep a frame cheap.
        widest = 1.0 if span >= math.pi / 2 else math.sin(span)
        half_width = ORBIT_RADIUS * self.globe_radius * widest + reach

        # Leave room for the title plate even when a single window makes the
        # ring itself narrow, or a long title would be cut off at the edge.
        half_width = max(half_width, self.width * 0.32)

        top = cy - max(self.globe_radius, reach + max(0.0, self.orbit_top))
        bottom = max(cy + self.globe_radius,
                     cy + self.orbit_rise + reach,
                     self.title_top + self.title_height)

        return (max(0, int(cx - half_width)), max(0, int(top)),
                min(self.width, int(cx + half_width) + 1),
                min(self.height, int(bottom) + 1))

    @property
    def step(self):
        """Angle between neighbouring windows, never more than a full turn."""
        return min(ANGULAR_STEP, 2.0 * math.pi / self.count)

    @property
    def span(self):
        """How far round the globe the windows reach, from first to last."""
        return min((self.count - 1) * self.step, math.pi)

    def longitude(self, index):
        """The fixed longitude a window is pinned to on the globe."""
        return index * self.step

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
            # down, so the near side of the ring hangs below the centre.
            # ORBIT_LIFT raises the ring's plane, which on screen is a plain
            # upward shift of the whole ellipse.
            ny = cos_t * ORBIT_LIFT - sin_t * mz
            nz = sin_t * ORBIT_LIFT + cos_t * mz

            depth = nz
            height = int(self.item_size *
                         (1.0 + DEPTH_SCALE * depth / ORBIT_RADIUS))
            opacity = 1.0 if depth >= 0 else BACK_OPACITY

            beads.append(Bead(
                index,
                int(cx + mx * self.globe_radius),
                int(cy - ny * self.globe_radius),
                depth, height, opacity))

        beads.sort(key=lambda bead: bead.depth)
        return beads


# --- tiles -------------------------------------------------------------------


def _trim(icon):
    """Drop an icon's transparent padding.

    Application icons pad themselves by wildly different amounts, and without
    trimming a row of them looks assembled at random sizes.
    """
    image = Image.fromarray(icon, "RGBA")
    box = image.getchannel("A").getbbox()
    return image.crop(box) if box else image


def _letter_tile(title):
    """A stand-in for windows with neither a thumbnail nor an icon."""
    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(size * 0.18),
                           fill=(70, 80, 100, 235))

    letter = (title.strip()[:1] or "?").upper()
    draw.text((size / 2, size / 2), letter, font=_load_font(int(size * 0.5)),
              fill=(235, 240, 250, 255), anchor="mm")
    return image


def _fit_box(image, width, height):
    """Scale into a box, keeping the aspect ratio, centred on transparency."""
    scale = min(width / image.width, height / image.height)
    scaled = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.LANCZOS)
    if scaled.size == (width, height):
        return scaled

    box = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    box.paste(scaled, ((width - scaled.width) // 2,
                       (height - scaled.height) // 2))
    return box


def _rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


class TileFactory:
    """Builds the tile drawn for each window, at whatever size a frame wants.

    A roll only visits a few dozen distinct sizes, so after the first turn
    every lookup is a cache hit and no frame pays to rescale anything.
    """

    QUANTUM = 4

    def __init__(self, thumbnails, icons, titles):
        self._thumbnails = thumbnails       # PIL RGB images, or None
        self._icons = [
            _trim(icon) if icon is not None else None for icon in icons]
        self._fallbacks = [
            self._icons[i] if self._icons[i] is not None else _letter_tile(title)
            for i, title in enumerate(titles)]
        self._cache = {}

    def get(self, index, height):
        """(RGB, alpha, opaque inset) for window `index`, at `height` tall."""
        height = max(16, int(round(height / self.QUANTUM)) * self.QUANTUM)
        key = (index, height)
        tile = self._cache.get(key)
        if tile is None:
            rgb, alpha = split_rgba(self._build(index, height))
            tile = (rgb, alpha, opaque_inset(alpha))
            self._cache[key] = tile
        return tile

    def _build(self, index, height):
        thumbnail = self._thumbnails[index]
        if thumbnail is None:
            return _fit_box(self._fallbacks[index], height, height)

        # Fit the window's own shape inside the box, so a wide window reads as
        # wide: that shape is half of recognising it at a glance.
        scale = min(height / thumbnail.width, height / thumbnail.height)
        width = max(24, round(thumbnail.width * scale))
        tall = max(24, round(thumbnail.height * scale))

        tile = thumbnail.resize((width, tall), Image.LANCZOS).convert("RGBA")
        radius = max(4, int(min(width, tall) * 0.09))
        tile.putalpha(_rounded_mask((width, tall), radius))

        # A hairline edge stops pale window contents dissolving into the
        # dimmed desktop behind them.
        ImageDraw.Draw(tile).rounded_rectangle(
            (0, 0, width - 1, tall - 1), radius=radius,
            outline=(255, 255, 255, 90), width=2)

        icon = self._icons[index]
        if icon is not None:
            badge = max(18, int(height * BADGE_FRACTION))
            tile.alpha_composite(
                icon.resize((badge, badge), Image.LANCZOS),
                (width - badge - 3, tall - badge - 3))

        return tile


# --- frame -------------------------------------------------------------------


def dim(rgb, factor=BACKDROP_DIM):
    """Darken the captured desktop so the switcher reads on top of it."""
    return (rgb.astype(np.uint16) * int(factor * 256) >> 8).astype(np.uint8)


class Frame:
    """Draws a frame of the switcher over a fixed, already dimmed backdrop."""

    def __init__(self, backdrop, layout, thumbnails, icons, titles):
        # `backdrop` is the captured desktop, already dimmed. It has to be
        # dimmed as a whole rather than only under the drawn region: the rest
        # of it still shows on screen, and a brightness step at the region's
        # edge would draw a rectangle across the desktop.
        self.backdrop = backdrop            # RGB uint8, screen sized
        self.layout = layout
        self.titles = titles
        self.tiles = TileFactory(thumbnails, icons, titles)

        left, top, right, bottom = layout.region
        self._origin = (left, top)
        self._base = np.ascontiguousarray(backdrop[top:bottom, left:right])
        self._canvas = np.empty_like(self._base)

        self._title_font = _load_font(
            max(15, int(layout.globe_diameter * 0.062)))
        self._title_cache = {}
        self._highlight_cache = {}

    def render(self, rotation, selected, globe_rgb, globe_alpha):
        """Compose one frame. Returns (RGB block, x, y) ready to blit."""
        layout = self.layout
        beads = layout.orbit(rotation)
        left, top = self._origin

        canvas = self._canvas
        np.copyto(canvas, self._base)

        # Far half, then the globe, then the near half. The globe is opaque
        # inside its disc, so it cuts the far half at the silhouette.
        for bead in beads:
            if bead.depth < 0:
                self._draw_bead(canvas, bead, selected, left, top)

        gx, gy, _, _ = layout.globe_box
        blend(canvas, globe_rgb, globe_alpha, gx - left, gy - top)

        for bead in beads:
            if bead.depth >= 0:
                self._draw_bead(canvas, bead, selected, left, top)

        self._draw_title(canvas, selected, left, top)
        return canvas, left, top

    def _draw_bead(self, canvas, bead, selected, left, top):
        rgb, alpha, inset = self.tiles.get(bead.index, bead.height)
        height, width = rgb.shape[:2]
        x = bead.x - width // 2 - left
        y = bead.y - height // 2 - top

        if bead.index == selected:
            glow_rgb, glow_alpha, pad = self._highlight(width, height)
            blend(canvas, glow_rgb, glow_alpha, x - pad, y - pad)

        if bead.opacity < 1.0:
            faded = (alpha.astype(np.uint16) *
                     int(bead.opacity * 256) >> 8).astype(np.uint8)
            blend(canvas, rgb, faded, x, y)
            return

        if not inset:
            blend(canvas, rgb, alpha, x, y)
            return

        # Solid middle straight in, and only the soft border blended.
        k = inset
        copy_rect(canvas, rgb[k:height - k, k:width - k], x + k, y + k)
        blend(canvas, rgb[:k], alpha[:k], x, y)
        blend(canvas, rgb[height - k:], alpha[height - k:], x, y + height - k)
        blend(canvas, rgb[k:height - k, :k], alpha[k:height - k, :k], x, y + k)
        blend(canvas, rgb[k:height - k, width - k:],
              alpha[k:height - k, width - k:], x + width - k, y + k)

    def _highlight(self, width, height):
        """A soft halo behind the window at the front, cached per size."""
        cached = self._highlight_cache.get((width, height))
        if cached is not None:
            return cached

        pad = int(min(width, height) * 0.20)
        glow = Image.new("RGBA", (width + pad * 2, height + pad * 2),
                         (0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)
        radius = max(6, int(min(width, height) * 0.12))

        steps = 6
        for step in range(steps, 0, -1):
            inset = int(pad * (step - 1) / steps)
            alpha = int(30 * (steps - step + 1) / steps)
            draw.rounded_rectangle(
                (inset, inset, glow.width - 1 - inset, glow.height - 1 - inset),
                radius=radius + pad - inset, fill=(130, 180, 255, alpha))

        draw.rounded_rectangle(
            (pad - 4, pad - 4, glow.width - pad + 3, glow.height - pad + 3),
            radius=radius + 4, outline=(255, 255, 255, 240), width=3)

        rgb, alpha = split_rgba(glow)
        cached = (rgb, alpha, pad)
        self._highlight_cache[(width, height)] = cached
        return cached

    def _draw_title(self, canvas, selected, left, top):
        if selected >= len(self.titles) or not self.titles[selected]:
            return

        plate = self._title_cache.get(selected)
        if plate is None:
            plate = self._build_title(self.titles[selected])
            self._title_cache[selected] = plate

        rgb, alpha, width = plate
        cx, _ = self.layout.centre
        blend(canvas, rgb, alpha,
              cx - width // 2 - left, self.layout.title_top - top)

    def _build_title(self, title):
        text = title if len(title) <= 90 else title[:89] + "…"
        measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        box = measure.textbbox((0, 0), text, font=self._title_font)
        text_width, text_height = box[2] - box[0], box[3] - box[1]

        pad_x, pad_y = 18, 10
        plate = Image.new("RGBA", (text_width + pad_x * 2,
                                   text_height + pad_y * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(plate)
        draw.rounded_rectangle((0, 0, plate.width - 1, plate.height - 1),
                               radius=11, fill=(0, 0, 0, 190))
        draw.text((plate.width // 2, pad_y - box[1]), text,
                  font=self._title_font, fill=(255, 255, 255, 255), anchor="ma")

        rgb, alpha = split_rgba(plate)
        return rgb, alpha, plate.width
