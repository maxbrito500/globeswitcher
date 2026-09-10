# globeswitcher

An Alt+Tab window switcher built around a **rotating Earth**, drawn from NASA
satellite imagery and lit by the real position of the sun.

![The globe switcher](docs/preview.jpg)

Your open windows ride on a ring around the globe's equator, each one shown as
a live picture of what is inside it. Each Tab rolls the globe one step, so the
next window comes round to the front and the rest travel with it. A few windows
sit together as a band across the equator; it takes something like twenty
before the ring closes and they wrap right around the world, with the far side
passing behind the Earth.

The daylight on the globe is the daylight happening right now, and the view is
turned to your own longitude, so you can see whether your part of the world is
still in it.

It is a plain X11 program, not a desktop extension. Nothing is plugged into
GNOME Shell, so there is nothing to break when GNOME updates, and it works the
same on Xfce, KDE on X11, i3 or a bare window manager.

## Keys

| Key | Action |
|---|---|
| `Alt+Tab` | open the switcher and roll the next window to the front |
| `Shift+Alt+Tab` | open backwards, roll the other way |
| `→` `↓` / `←` `↑` | keep rolling while it is open (keypad arrows too) |
| `Home` / `End` | jump to the first or last window |
| release `Alt`, `Enter` or `Space` | activate the window at the front |
| `Escape` | close without switching |
| `w`, `q` or `F4` | close the window at the front |
| click a window | activate it |
| middle-click a window | close it |
| scroll wheel | keep rolling |
| click the backdrop | close without switching |

Windows are offered in most-recently-used order, so a single Alt+Tab flips
between the last two windows, the way every other switcher behaves.

## Settings

A globe sits in the system tray. Its menu opens a settings window whose
**Switcher** tab carries the tuning that used to mean editing constants: globe
size, window size, ring width and height, camera tilt, the spacing between
windows, roll time, how far the desktop is dimmed, and how much daylight is
left in the night side. Each slider says what moving it does. There are also
switches for whether other workspaces are included and whether the window title
is shown, and a button to put everything back.

Settings are saved as you move them, and apply the next time you press Alt+Tab.

## Requirements

- An **X11** session. Wayland gives no way to list or raise other windows, so
  there is nothing this program could do there
- The [Flutter SDK](https://docs.flutter.dev/get-started/install/linux) to
  build it, with the usual Linux desktop toolchain
- A window manager that supports EWMH, which in practice means all of them

On Debian/Ubuntu:

```sh
sudo apt install cmake ninja-build clang libgtk-3-dev \
    libayatana-appindicator3-dev
```

## Install

```sh
git clone https://github.com/maxbrito500/globeswitcher.git
cd globeswitcher
./install.sh
```

The installer builds the app, copies it to `~/.local/share/globeswitcher/app`,
starts it, and adds it to `~/.config/autostart` so it comes back on login.

X11 only lets one program grab a given key, so whatever your desktop has bound
to Alt+Tab has to let go of it first. On GNOME the installer does that for you
and saves the old value; on other desktops, clear Alt+Tab in your keyboard
settings yourself.

## If it dies

Every start, exit and crash is written to
`~/.local/share/globeswitcher/globeswitcher.log`, along with whatever the app
printed before it went. Look there first:

```sh
tail -50 ~/.local/share/globeswitcher/globeswitcher.log
```

## Uninstall

```sh
./uninstall.sh
```

This stops the app, restores the Alt+Tab binding it took, and deletes
everything it installed.

## How it works

**The map.** Two equirectangular NASA images ship with the app: *Blue Marble*
for daylight and *Black Marble* for city lights.

**The globe.** `flutter_app/shaders/globe.frag` does the projection and the
lighting together. For each pixel of the disc it works out the surface normal,
turns that into a latitude and longitude, looks both maps up, and mixes them by
the solar elevation at that same point — computed from the subsolar position,
which comes from the clock alone and no network service. The terminator is
therefore exact on every frame, with nothing to regenerate and nothing that can
go stale. A little daylight is left in the night side, because city lights
alone are close enough to black that half the globe would disappear.

**The windows.** Window `i` is pinned to a longitude on the equator, and its
place on screen is that point projected through the same camera the globe is
drawn with, lifted about 24° above the equator so the ring is a shallow band
around the waist rather than an arc over the poles. The ring also floats above
the equatorial plane: one lying exactly on it projects far below the globe's
centre, because the camera tilt multiplies the offset by the ring's radius
rather than the globe's, and the windows end up sweeping past the south pole.

The spacing is a fixed angle rather than `360°/n`. Dividing the circle would
fling four windows out to the four cardinal points and leave the globe ringed
by empty space; a fixed step keeps a handful of windows together in front of
you, and only closes the ring once there are enough to go the whole way round.

Which windows are hidden needs no test. The far half is drawn first, then the
globe, then the near half; because the globe is opaque inside its disc, a
window crossing the limb is cut exactly at the silhouette.

**Rolling.** The selected window is whichever one faces you, so selection and
rotation are the same thing: Tab picks the next window and sets the globe's
target angle to that window's longitude, and the globe eases there, always
taking the shorter way round. A Tab pressed mid-roll retargets from wherever
the globe currently is, so drumming on Tab stays smooth. Wrapping from the last
window back to the first travels the whole band, so that roll is given
proportionally longer and reads as a turn rather than a jump.

**The window list.** Read from the X server through EWMH: `_NET_CLIENT_LIST`
for the windows, `_NET_WM_ICON` for the icons, `_NET_WM_NAME` for the titles,
`XGetImage` for the pictures, and a `_NET_ACTIVE_WINDOW` message to raise the
one you chose. X has no most-recently-used list, so the app keeps its own by
watching which window the window manager makes active.

All of that is `dart:ffi` straight against libX11 — no C plugin — and it sits
behind one `WindowBackend` interface. That is the part Flutter does not carry
across: listing another application's windows, picturing them, raising one and
taking over Alt+Tab have no Flutter API and differ on every desktop. Adding
Windows or macOS means writing one more implementation of that interface and
nothing else; the same `dart:ffi` approach would work against `user32.dll`.

**One window, two hats.** Flutter desktop gives an application a single window,
so the same one is reconfigured rather than duplicated: undecorated, fullscreen
and above everything as the switcher; an ordinary titled window as the settings
panel; hidden the rest of the time.

## The original Python version

`globeswitcher/` and `tools/` hold the first implementation, in Python with
numpy compositing on the CPU. It still works, and `./install-python.sh` installs
it instead. Only one of the two can run at a time, because only one X client can
hold the Alt+Tab grab.

It is worth keeping as the reference the port was made from, and as the way to
run this on a machine without the Flutter SDK. It has no tray icon and no
settings panel; its tuning lives in constants at the top of
`globeswitcher/ui.py`, `globeswitcher/globe.py` and `tools/globe-texture`.

## Known limits

- **X11 only.** Wayland has no protocol for listing or activating another
  application's windows, short of a compositor-specific extension.
- The switcher covers the whole X screen rather than one monitor.
- Thumbnails of windows buried behind others depend on a compositing window
  manager keeping their contents. Without a compositor an obscured window has
  nothing to capture, and it falls back to its application icon.
- The tray menu is the way in to settings: under GNOME's AppIndicator support a
  left click opens that menu rather than firing an activate event.
- Past about twenty windows the ring closes and the tiles start to overlap near
  the limbs, where the spacing foreshortens.

## Credits

Satellite imagery courtesy of [NASA Visible Earth](https://visibleearth.nasa.gov/):
*Blue Marble: Next Generation* and *Black Marble*. NASA imagery is in the
public domain.

## Licence

Apache License 2.0 — see [LICENSE](LICENSE).
