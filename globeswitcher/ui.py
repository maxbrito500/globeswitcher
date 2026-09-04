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

The frame is built in two parts. Everything that only changes when the
selection changes -- the dimmed desktop, the ring of windows, the title -- is
drawn once into a background image. The globe is drawn on top of a copy of
that background, and only the globe's rectangle is pushed to the X server on
each animation frame.
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Layout, as fractions of the screen's short axis.
GLOBE_FRACTION = 0.40
RING_FRACTION = 0.335
ITEM_FRACTION = 0.125
ITEM_MIN = 72
ITEM_MAX = 160
INNER_RING_RATIO = 0.58
SINGLE_RING_MAX = 12

SELECTED_GROWTH = 1.22
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


class Layout:
    """Where the globe and each window sit on screen."""

    def __init__(self, width, height, count):
        self.width = width
        self.height = height
        short = min(width, height)

        self.centre = (width // 2, height // 2)
        self.globe_diameter = int(short * GLOBE_FRACTION)

        self.two_rings = count > SINGLE_RING_MAX
        crowding = 0.82 if self.two_rings else 1.0
        self.item_size = int(min(ITEM_MAX, max(
            ITEM_MIN, short * ITEM_FRACTION * crowding)))

        self.radius = short * RING_FRACTION
        self.count = count
        self.positions = [self._position(i) for i in range(count)]

    def _position(self, index):
        outer_count = math.ceil(self.count / 2) if self.two_rings else self.count
        on_outer = not self.two_rings or index < outer_count

        count = outer_count if on_outer else self.count - outer_count
        index_in_ring = index if on_outer else index - outer_count
        radius = self.radius * (1.0 if on_outer else INNER_RING_RATIO)

        # Start at twelve o'clock and run clockwise, matching how people read
        # a tab order.
        angle = -math.pi / 2 + (index_in_ring / max(count, 1)) * 2 * math.pi
        cx, cy = self.centre
        return (int(cx + math.cos(angle) * radius),
                int(cy + math.sin(angle) * radius))

    @property
    def globe_box(self):
        cx, cy = self.centre
        half = self.globe_diameter // 2
        return (cx - half, cy - half, self.globe_diameter, self.globe_diameter)


def _rounded_icon(icon, size, radius_fraction=0.18):
    """An icon scaled to `size` with softly rounded corners.

    Icons are trimmed to their visible content first. Application icons pad
    themselves by wildly different amounts, and without trimming a ring of
    them looks like it was assembled at random sizes.
    """
    image = Image.fromarray(icon, "RGBA")
    box = image.getchannel("A").getbbox()
    if box:
        image = image.crop(box)

    # Keep the aspect ratio; letterbox into the square tile.
    scale = size / max(image.width, image.height)
    scaled = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.LANCZOS)
    if scaled.size != (size, size):
        square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        square.paste(scaled, ((size - scaled.width) // 2,
                              (size - scaled.height) // 2))
        image = square
    else:
        image = scaled

    radius = int(size * radius_fraction)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=255)

    alpha = Image.fromarray(
        np.minimum(np.asarray(image.getchannel("A")), np.asarray(mask)))
    image.putalpha(alpha)
    return image


def _placeholder_icon(size, title):
    """A tile with the window's initial, for windows that ship no icon."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    radius = int(size * 0.18)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius,
                           fill=(70, 80, 100, 235))

    letter = (title.strip()[:1] or "?").upper()
    font = _load_font(int(size * 0.5))
    draw.text((size / 2, size / 2), letter, font=font,
              fill=(235, 240, 250, 255), anchor="mm")
    return image


class Frame:
    """Builds the images the canvas blits."""

    def __init__(self, backdrop, layout):
        self.layout = layout
        self.backdrop = backdrop            # RGB uint8, screen sized
        self._background = None

    def build_background(self, windows, icons, selected, title):
        """Redraw everything except the globe. Call on selection change."""
        base = Image.fromarray(self.backdrop, "RGB").convert("RGBA")
        layout = self.layout

        for index, position in enumerate(layout.positions):
            is_selected = index == selected
            size = int(layout.item_size *
                       (SELECTED_GROWTH if is_selected else 1.0))

            icon = icons[index]
            tile = (_rounded_icon(icon, size) if icon is not None
                    else _placeholder_icon(size, windows[index].title))

            x = position[0] - size // 2
            y = position[1] - size // 2

            if is_selected:
                self._draw_selection(base, x, y, size)
            else:
                tile = Image.blend(
                    Image.new("RGBA", tile.size, (0, 0, 0, 0)), tile, 0.82)

            base.alpha_composite(tile, (x, y))

        self._draw_title(base, title)

        self._background = np.asarray(base.convert("RGB"), dtype=np.uint8)
        return self._background

    def _draw_selection(self, base, x, y, size):
        """A soft halo behind the highlighted window."""
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

        base.alpha_composite(glow, (x - pad, y - pad))

    def _draw_title(self, base, title):
        if not title:
            return

        layout = self.layout
        cx, cy = layout.centre
        font = _load_font(max(15, int(layout.globe_diameter * 0.075)))

        draw = ImageDraw.Draw(base)
        text = title if len(title) <= 90 else title[:89] + "…"
        box = draw.textbbox((0, 0), text, font=font)
        text_width = box[2] - box[0]
        text_height = box[3] - box[1]

        pad_x, pad_y = 16, 9
        top = cy + layout.globe_diameter // 2 + 22
        left = cx - text_width // 2

        plate = Image.new(
            "RGBA", (text_width + pad_x * 2, text_height + pad_y * 2),
            (0, 0, 0, 0))
        ImageDraw.Draw(plate).rounded_rectangle(
            (0, 0, plate.width - 1, plate.height - 1), radius=10,
            fill=(0, 0, 0, 165))
        base.alpha_composite(plate, (left - pad_x, top - pad_y))

        draw.text((cx, top - box[1]), text, font=font,
                  fill=(255, 255, 255, 255), anchor="ma")

    def compose(self, globe_rgb, globe_alpha, target):
        """Draw the globe onto `target`, which must be the background image."""
        x, y, width, height = self.layout.globe_box
        region = target[y:y + height, x:x + width].astype(np.float32)
        alpha = globe_alpha[..., None]

        blended = region * (1.0 - alpha) + globe_rgb.astype(np.float32) * alpha
        target[y:y + height, x:x + width] = blended.astype(np.uint8)

    @property
    def background(self):
        return self._background


def dim(rgb, factor=BACKDROP_DIM):
    """Darken the captured desktop so the switcher reads on top of it."""
    return (rgb.astype(np.uint16) * int(factor * 256) >> 8).astype(np.uint8)
