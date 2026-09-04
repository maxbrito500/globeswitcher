# globeswitcher

An Alt+Tab window switcher built around a **rotating Earth**, drawn from NASA
satellite imagery and lit by the real position of the sun.

![The globe switcher](docs/preview.jpg)

Hold Alt, and the globe turns while your open windows sit in a ring around it.
The daylight on the globe is the daylight happening right now, so while you
pick a window you can see which half of the world is awake.

It is a plain X11 program, not a desktop extension. Nothing is plugged into
GNOME Shell, so there is nothing to break when GNOME updates, and it works the
same on Xfce, KDE on X11, i3 or a bare window manager.

It is a companion to [globewallpaper](https://github.com/maxbrito500/globewallpaper),
which puts the same imagery on your desktop background. Neither needs the
other, but installing both means the NASA imagery is only downloaded once.

## Keys

| Key | Action |
|---|---|
| `Alt+Tab` | open the switcher, move to the next window |
| `Shift+Alt+Tab` | open backwards, move to the previous window |
| `→` `↓` / `←` `↑` | move through the ring while it is open |
| release `Alt` | activate the highlighted window |
| `Escape` | close without switching |
| `w`, `q` or `F4` | close the highlighted window |

Windows are offered in most-recently-used order, so a single Alt+Tab flips
between the last two windows, the way every other switcher behaves.

## Requirements

- An **X11** session. Wayland gives no way to list or raise other windows, so
  there is nothing this program could do there
- `python3` with `numpy` and `Pillow`
- A window manager that supports EWMH, which in practice means all of them

On Debian/Ubuntu:

```sh
sudo apt install python3-numpy python3-pil
```

## Install

```sh
git clone https://github.com/maxbrito500/globeswitcher.git
cd globeswitcher
./install.sh
```

The installer copies the program into `~/.local/share/globeswitcher`, renders
the first world map, starts the daemon, and adds it to
`~/.config/autostart` so it comes back on login.

X11 only lets one program grab a given key, so whatever your desktop has bound
to Alt+Tab has to let go of it first. On GNOME the installer does that for you
and saves the old value; on other desktops, clear Alt+Tab in your keyboard
settings yourself.

## Uninstall

```sh
./uninstall.sh
```

This stops the daemon, restores the Alt+Tab binding it took, and deletes
everything it installed.

## How it works

**The map.** `tools/globe-texture` renders a 2048x1024 equirectangular image
from NASA's *Blue Marble* (day) and *Black Marble* (night lights). Each pixel
is mixed according to the sun's elevation there, across a smoothstep twilight
band, so the terminator is a soft edge rather than a hard line. The subsolar
point comes from the low-precision solar formulas in the *Astronomical
Almanac* — no network service is involved, only your system clock. The imagery
is downloaded once and cached; everything after that works offline.

**The globe.** No GPU, no shader, no toolkit. Rotating a sphere whose texture
is an equirectangular map only shifts the longitude, so the mapping from screen
pixel to map row never changes and the mapping to map column changes by a
constant. Both are precomputed once. Each frame is then a single numpy gather —
about 5 ms for a 360-pixel globe, comfortably faster than the 30 fps it is
animated at.

**The window list.** Read from the X server through EWMH: `_NET_CLIENT_LIST`
for the windows, `_NET_WM_ICON` for the icons, `_NET_WM_NAME` for the titles,
and a `_NET_ACTIVE_WINDOW` message to raise the one you chose. X has no
most-recently-used list, so the daemon keeps its own by watching which window
the window manager makes active.

**The window on screen.** An override-redirect X window covering the screen,
which means no window manager touches it: it never lands in a taskbar and is
always on top, identically on every desktop. Instead of asking a compositor
for transparency, the daemon captures the screen when you press Alt+Tab and
dims it itself, so the switcher looks the same whether or not a compositor is
running.

Everything that only changes with the selection is drawn once into a
background image; each animation frame redraws only the globe's rectangle and
pushes just that rectangle to the X server.

## Configuration

Constants at the top of the source:

| File | Constant | Meaning |
|---|---|---|
| `globeswitcher/daemon.py` | `SPIN_PERIOD_SECONDS` | Seconds per full rotation (default 48) |
| `globeswitcher/daemon.py` | `CURRENT_DESKTOP_ONLY` | Hide windows on other workspaces |
| `globeswitcher/globe.py` | `VIEW_TILT_RADIANS` | How far above the equator you view from |
| `globeswitcher/globe.py` | `MAX_TEXTURE_AGE_SECONDS` | How stale the map may get before a refresh |
| `globeswitcher/ui.py` | `GLOBE_FRACTION` | Globe diameter, as a share of the screen's short axis |
| `globeswitcher/ui.py` | `RING_FRACTION` | Ring radius, same units |
| `globeswitcher/ui.py` | `BACKDROP_DIM` | How much of the desktop's brightness remains |
| `globeswitcher/ui.py` | `SINGLE_RING_MAX` | Window count above which a second, inner ring opens |
| `tools/globe-texture` | `TWILIGHT_LO` / `TWILIGHT_HI` | Solar elevations bounding the twilight blend |

After editing, re-run `./install.sh`.

## Testing

Render a switcher frame to a file, with invented windows and no real desktop
behind it:

```sh
python3 -m globeswitcher --demo /tmp/preview.png
```

Point the map generator at any moment in time, which makes the lighting easy
to check without waiting for the Earth to turn:

```sh
GLOBE_FAKE_UTC=2026-06-21T12:00 GLOBE_OUTPUT=/tmp/solstice.png \
    ./tools/globe-texture
```

At the solstices the solar declination should be near ±23.44°, at the
equinoxes near 0°, and at 12:00 UTC the sunlit centre sits near longitude 0°.

Trace what the daemon is doing:

```sh
pkill -f globeswitcher.__main__
GLOBESWITCHER_DEBUG=1 ~/.local/bin/globeswitcher
```

## Known limits

- **X11 only.** Wayland has no protocol for listing or activating another
  application's windows, short of a compositor-specific extension.
- The switcher is drawn on the primary screen's geometry; on a multi-monitor
  setup it covers the full X screen rather than one monitor.
- Windows are shown as application icons, not live thumbnails. Live thumbnails
  on X11 need a compositing detour that would cost more than it is worth here.

## Credits

Satellite imagery courtesy of [NASA Visible Earth](https://visibleearth.nasa.gov/):
*Blue Marble: Next Generation* and *Black Marble*. NASA imagery is in the
public domain and is downloaded at runtime — it is not redistributed by this
repository.

## Licence

Apache License 2.0 — see [LICENSE](LICENSE).
