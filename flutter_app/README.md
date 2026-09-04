# globeswitcher, in Flutter

A rewrite of the switcher with Flutter doing the drawing, so the same interface
can eventually run on more than X11. It is not a replacement yet — the Python
app in the parent directory is still the one that gets installed.

## What Flutter carries across, and what it does not

Flutter ports the **drawing**: the globe, the ring, the thumbnails and the
animation are one codebase, and they run on the GPU rather than on numpy.

It carries nothing of the **switching**. Listing another application's windows,
picturing them, raising one, taking over Alt+Tab and putting up an overlay that
holds the keyboard are different on every desktop, and Flutter has no API for
any of them. All of that sits behind `WindowBackend`
(`lib/backend/window_backend.dart`), and each platform implements that one
interface.

`lib/backend/x11/` is the X11 implementation, written with `dart:ffi` straight
against libX11 — no C plugin needed. The same approach works against
`user32.dll` on Windows. macOS needs Accessibility permission, and Apple does
not allow replacing Cmd+Tab. Wayland offers no way to do this at all.

## The globe is a shader now

The Python version regenerates a day/night map every ten minutes and wraps that
around a sphere. Here `shaders/globe.frag` does the projection *and* the
lighting: it samples a plain day map and a plain night map, and works out the
solar elevation for each pixel from the subsolar point handed in as a uniform.
The terminator is therefore exact on every frame, there is nothing to
regenerate, and nothing can go stale.

`lib/model/solar.dart` works out where the sun is, from the clock alone, and
`lib/ui/ring.dart` is a port of the ring geometry.

## Building and running

```sh
flutter test          # solar position and ring layout
flutter run -d linux
```

On this machine builds go through the machine-wide lock:

```sh
~/bin/android-build-locked flutter build linux --release
./build/linux/x64/release/bundle/globeswitcher
```

Only one program can hold the Alt+Tab grab, so stop the Python daemon first, or
neither will get the key:

```sh
pkill -f globeswitcher.__main__
```

## What is not done yet

- No installer and no autostart; it is started by hand.
- Thumbnails are captured on every open, without the Python version's cache, so
  opening costs more than it needs to.
- The overlay is an ordinary window kept above the others and fullscreened,
  rather than a true override-redirect window.
- Windows and macOS backends do not exist. `WindowBackend` is where they go.
