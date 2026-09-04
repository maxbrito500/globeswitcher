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
"""Rendering the spinning Earth.

The globe is an orthographic projection of an equirectangular map. Every
mapping from screen pixel to map row is fixed, and the only thing rotation
changes is a horizontal offset into the map, so the per-frame work collapses
to one integer add and one gather. That is fast enough in numpy to animate
smoothly without a GPU, a shader, or a toolkit.
"""

import math
import os
import subprocess

import numpy as np
from PIL import Image

TEXTURE_PATH = os.path.join(
    os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
    "globeswitcher", "globe-equirect.png")

# Regenerate the map when it is older than this, so the daylight shown is
# never more than a few minutes stale.
MAX_TEXTURE_AGE_SECONDS = 600

VIEW_TILT_RADIANS = 0.62        # look down on the globe from ~35 degrees
ATMOSPHERE_RGB = (0.32, 0.55, 0.95)
ATMOSPHERE_STRENGTH = 0.45
RIM_START = 0.72                # fraction of the radius where the rim begins


class Globe:
    """A globe of a fixed pixel size, ready to be rendered at any rotation."""

    def __init__(self, diameter, texture_path=TEXTURE_PATH):
        self.diameter = int(diameter)
        self.texture_path = texture_path
        self._map = None
        self._map_mtime = 0
        self._refreshing = None

        self._build_projection()
        self.reload_texture()

    # -- setup ----------------------------------------------------------------

    def _build_projection(self):
        """Precompute, for every pixel of the disc, where it looks in the map.

        Latitude is fixed for a pixel. Longitude is fixed too, apart from the
        rotation added at render time, so it is stored as a fraction of a full
        turn rather than as a column index.
        """
        d = self.diameter
        axis = (np.arange(d, dtype=np.float32) + 0.5) / d * 2.0 - 1.0
        px, py = np.meshgrid(axis, axis)

        radius = np.sqrt(px * px + py * py)
        inside = radius <= 1.0

        # Orthographic projection: the visible hemisphere faces the viewer.
        nz = np.sqrt(np.clip(1.0 - (px * px + py * py), 0.0, 1.0))
        nx = px
        ny = -py                                    # screen y grows downward

        # Camera lifted VIEW_TILT_RADIANS above the equator, looking north
        # down onto the globe. Rotating screen space back into world space is
        # what turns a pixel into a latitude and longitude.
        tilt = VIEW_TILT_RADIANS
        my = math.cos(tilt) * ny + math.sin(tilt) * nz
        mz = -math.sin(tilt) * ny + math.cos(tilt) * nz

        latitude = np.arcsin(np.clip(my, -1.0, 1.0))
        longitude = np.arctan2(nx, mz)

        self._inside = inside
        self._row = ((0.5 - latitude / math.pi))    # 0 at north pole, 1 at south
        self._turn = (longitude / (2.0 * math.pi) + 0.5).astype(np.float32)

        # Shading: an atmospheric rim near the limb, and a soft outer edge so
        # the globe does not look like a cut-out circle.
        rim = np.clip((radius - RIM_START) / (1.0 - RIM_START), 0.0, 1.0)
        self._rim = (rim * rim * ATMOSPHERE_STRENGTH).astype(np.float32)
        edge = np.clip((1.0 - radius) * self.diameter / 2.0, 0.0, 1.0)
        self.alpha = np.where(inside, edge, 0.0).astype(np.float32)

        self._flat_inside = np.flatnonzero(inside)
        self._turn_inside = self._turn.ravel()[self._flat_inside]
        self._rim_inside = self._rim.ravel()[self._flat_inside]

    # -- texture --------------------------------------------------------------

    def reload_texture(self):
        """Re-read the map if it changed on disk. Returns True if it is usable."""
        try:
            mtime = os.path.getmtime(self.texture_path)
        except OSError:
            return self._map is not None

        if self._map is not None and mtime == self._map_mtime:
            return True

        try:
            with Image.open(self.texture_path) as image:
                self._map = np.asarray(image.convert("RGB"), dtype=np.uint8)
        except Exception:
            return self._map is not None

        self._map_mtime = mtime
        height = self._map.shape[0]
        self._row_index = np.clip(
            (self._row.ravel()[self._flat_inside] * height).astype(np.int32),
            0, height - 1)
        return True

    def refresh_if_stale(self, generator):
        """Start regenerating the map in the background if it has aged out."""
        if self._refreshing is not None:
            if self._refreshing.poll() is None:
                return
            self._refreshing = None
            self.reload_texture()

        try:
            age = os.path.getmtime(self.texture_path)
        except OSError:
            age = None

        import time
        if age is not None and time.time() - age < MAX_TEXTURE_AGE_SECONDS:
            return

        try:
            self._refreshing = subprocess.Popen(
                [generator], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self._refreshing = None

    @property
    def ready(self):
        return self._map is not None

    # -- rendering ------------------------------------------------------------

    def render(self, rotation):
        """The globe at `rotation` radians, as an RGB uint8 array."""
        out = np.zeros((self.diameter, self.diameter, 3), dtype=np.uint8)
        if self._map is None:
            return out

        width = self._map.shape[1]
        turn = self._turn_inside + rotation / (2.0 * math.pi)
        columns = (np.modf(turn)[0] * width).astype(np.int32)
        np.mod(columns, width, out=columns)

        samples = self._map[self._row_index, columns].astype(np.float32)

        # Blend towards the atmosphere colour near the limb.
        rim = self._rim_inside[:, None]
        tint = np.array(ATMOSPHERE_RGB, dtype=np.float32) * 255.0
        samples += (tint - samples) * rim

        flat = out.reshape(-1, 3)
        flat[self._flat_inside] = samples.astype(np.uint8)
        return out
