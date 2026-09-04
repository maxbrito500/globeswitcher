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
"""A small ctypes binding to Xlib, and the EWMH calls this switcher needs.

Deliberately toolkit-free: everything here talks to the X server directly, so
the switcher runs the same on GNOME, Xfce, KDE, i3 or a bare window manager.
Only the parts actually used are bound.
"""

import ctypes
import ctypes.util
import struct

import numpy as np

# --- library -----------------------------------------------------------------

_lib_name = ctypes.util.find_library("X11")
if not _lib_name:
    raise ImportError("libX11 not found")
xlib = ctypes.CDLL(_lib_name)

# --- types -------------------------------------------------------------------

Atom = ctypes.c_ulong
Window = ctypes.c_ulong
Colormap = ctypes.c_ulong
Time = ctypes.c_ulong

NONE = 0
COPY_FROM_PARENT = 0
INPUT_OUTPUT = 1
Z_PIXMAP = 2

# Event types
KEY_PRESS = 2
KEY_RELEASE = 3
EXPOSE = 12
PROPERTY_NOTIFY = 28

# Event masks
KEY_PRESS_MASK = 1 << 0
KEY_RELEASE_MASK = 1 << 1
EXPOSURE_MASK = 1 << 15
PROPERTY_CHANGE_MASK = 1 << 22
SUBSTRUCTURE_NOTIFY_MASK = 1 << 19
SUBSTRUCTURE_REDIRECT_MASK = 1 << 20

# Modifiers
SHIFT_MASK = 1 << 0
LOCK_MASK = 1 << 1
CONTROL_MASK = 1 << 2
MOD1_MASK = 1 << 3          # Alt
MOD2_MASK = 1 << 4          # NumLock, usually
MOD4_MASK = 1 << 6          # Super

GRAB_MODE_SYNC = 0
GRAB_MODE_ASYNC = 1

CW_BACK_PIXEL = 1 << 1
CW_OVERRIDE_REDIRECT = 1 << 9
CW_EVENT_MASK = 1 << 11
CW_COLORMAP = 1 << 13

# Keysyms used by the switcher
XK_Tab = 0xFF09
XK_ISO_Left_Tab = 0xFE20
XK_Escape = 0xFF1B
XK_Alt_L = 0xFFE9
XK_Alt_R = 0xFFEA
XK_Left = 0xFF51
XK_Up = 0xFF52
XK_Right = 0xFF53
XK_Down = 0xFF54
XK_F4 = 0xFFC1
XK_w = 0x0077
XK_W = 0x0057
XK_q = 0x0071
XK_Q = 0x0051


class XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", Window),
        ("root", Window),
        ("subwindow", Window),
        ("time", Time),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class XPropertyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", Window),
        ("atom", Atom),
        ("time", Time),
        ("state", ctypes.c_int),
    ]


class XClientMessageData(ctypes.Union):
    _fields_ = [
        ("b", ctypes.c_char * 20),
        ("s", ctypes.c_short * 10),
        ("l", ctypes.c_long * 5),
    ]


class XClientMessageEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", Window),
        ("message_type", Atom),
        ("format", ctypes.c_int),
        ("data", XClientMessageData),
    ]


class XEvent(ctypes.Union):
    _fields_ = [
        ("type", ctypes.c_int),
        ("xkey", XKeyEvent),
        ("xproperty", XPropertyEvent),
        ("xclient", XClientMessageEvent),
        ("pad", ctypes.c_long * 24),
    ]


class XSetWindowAttributes(ctypes.Structure):
    _fields_ = [
        ("background_pixmap", ctypes.c_ulong),
        ("background_pixel", ctypes.c_ulong),
        ("border_pixmap", ctypes.c_ulong),
        ("border_pixel", ctypes.c_ulong),
        ("bit_gravity", ctypes.c_int),
        ("win_gravity", ctypes.c_int),
        ("backing_store", ctypes.c_int),
        ("backing_planes", ctypes.c_ulong),
        ("backing_pixel", ctypes.c_ulong),
        ("save_under", ctypes.c_int),
        ("event_mask", ctypes.c_long),
        ("do_not_propagate_mask", ctypes.c_long),
        ("override_redirect", ctypes.c_int),
        ("colormap", Colormap),
        ("cursor", ctypes.c_ulong),
    ]


class XImage(ctypes.Structure):
    pass


XImage._fields_ = [
    ("width", ctypes.c_int),
    ("height", ctypes.c_int),
    ("xoffset", ctypes.c_int),
    ("format", ctypes.c_int),
    ("data", ctypes.c_void_p),
    ("byte_order", ctypes.c_int),
    ("bitmap_unit", ctypes.c_int),
    ("bitmap_bit_order", ctypes.c_int),
    ("bitmap_pad", ctypes.c_int),
    ("depth", ctypes.c_int),
    ("bytes_per_line", ctypes.c_int),
    ("bits_per_pixel", ctypes.c_int),
    ("red_mask", ctypes.c_ulong),
    ("green_mask", ctypes.c_ulong),
    ("blue_mask", ctypes.c_ulong),
    ("obdata", ctypes.c_void_p),
    ("f_create_image", ctypes.c_void_p),
    ("f_destroy_image", ctypes.c_void_p),
    ("f_get_pixel", ctypes.c_void_p),
    ("f_put_pixel", ctypes.c_void_p),
    ("f_sub_image", ctypes.c_void_p),
    ("f_add_pixel", ctypes.c_void_p),
]

# --- prototypes --------------------------------------------------------------

xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
xlib.XOpenDisplay.restype = ctypes.c_void_p
xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
xlib.XDefaultScreen.argtypes = [ctypes.c_void_p]
xlib.XDefaultScreen.restype = ctypes.c_int
xlib.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
xlib.XRootWindow.restype = Window
xlib.XDefaultVisual.argtypes = [ctypes.c_void_p, ctypes.c_int]
xlib.XDefaultVisual.restype = ctypes.c_void_p
xlib.XDefaultDepth.argtypes = [ctypes.c_void_p, ctypes.c_int]
xlib.XDefaultDepth.restype = ctypes.c_int
xlib.XDisplayWidth.argtypes = [ctypes.c_void_p, ctypes.c_int]
xlib.XDisplayWidth.restype = ctypes.c_int
xlib.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
xlib.XDisplayHeight.restype = ctypes.c_int
xlib.XConnectionNumber.argtypes = [ctypes.c_void_p]
xlib.XConnectionNumber.restype = ctypes.c_int

xlib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
xlib.XInternAtom.restype = Atom

xlib.XGetWindowProperty.argtypes = [
    ctypes.c_void_p, Window, Atom, ctypes.c_long, ctypes.c_long, ctypes.c_int,
    Atom, ctypes.POINTER(Atom), ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
]
xlib.XGetWindowProperty.restype = ctypes.c_int
xlib.XFree.argtypes = [ctypes.c_void_p]
xlib.XChangeProperty.argtypes = [
    ctypes.c_void_p, Window, Atom, Atom, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_int,
]

xlib.XSelectInput.argtypes = [ctypes.c_void_p, Window, ctypes.c_long]
xlib.XSendEvent.argtypes = [
    ctypes.c_void_p, Window, ctypes.c_int, ctypes.c_long,
    ctypes.POINTER(XEvent),
]

xlib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
xlib.XKeysymToKeycode.restype = ctypes.c_ubyte
xlib.XKeycodeToKeysym.argtypes = [ctypes.c_void_p, ctypes.c_ubyte, ctypes.c_int]
xlib.XKeycodeToKeysym.restype = ctypes.c_ulong

xlib.XGrabKey.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, Window, ctypes.c_int,
    ctypes.c_int, ctypes.c_int,
]
xlib.XUngrabKey.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, Window,
]
xlib.XGrabKeyboard.argtypes = [
    ctypes.c_void_p, Window, ctypes.c_int, ctypes.c_int, ctypes.c_int, Time,
]
xlib.XGrabKeyboard.restype = ctypes.c_int
xlib.XUngrabKeyboard.argtypes = [ctypes.c_void_p, Time]

xlib.XCreateWindow.argtypes = [
    ctypes.c_void_p, Window, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
    ctypes.c_uint, ctypes.c_uint, ctypes.c_int, ctypes.c_uint,
    ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(XSetWindowAttributes),
]
xlib.XCreateWindow.restype = Window
xlib.XDestroyWindow.argtypes = [ctypes.c_void_p, Window]
xlib.XMapRaised.argtypes = [ctypes.c_void_p, Window]
xlib.XUnmapWindow.argtypes = [ctypes.c_void_p, Window]
xlib.XCreateGC.argtypes = [
    ctypes.c_void_p, Window, ctypes.c_ulong, ctypes.c_void_p,
]
xlib.XCreateGC.restype = ctypes.c_void_p
xlib.XFreeGC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

xlib.XCreateImage.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_int,
    ctypes.c_int, ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint,
    ctypes.c_int, ctypes.c_int,
]
xlib.XCreateImage.restype = ctypes.POINTER(XImage)
xlib.XPutImage.argtypes = [
    ctypes.c_void_p, Window, ctypes.c_void_p, ctypes.POINTER(XImage),
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_uint, ctypes.c_uint,
]
xlib.XGetImage.argtypes = [
    ctypes.c_void_p, Window, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
    ctypes.c_uint, ctypes.c_ulong, ctypes.c_int,
]
xlib.XGetImage.restype = ctypes.POINTER(XImage)
xlib.XDestroyImage.argtypes = [ctypes.POINTER(XImage)]

xlib.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.POINTER(XEvent)]
xlib.XPending.argtypes = [ctypes.c_void_p]
xlib.XPending.restype = ctypes.c_int
xlib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
xlib.XFlush.argtypes = [ctypes.c_void_p]
xlib.XSetErrorHandler.argtypes = [ctypes.c_void_p]
xlib.XSetErrorHandler.restype = ctypes.c_void_p

# X errors on windows that vanish mid-query are routine in a switcher, and the
# default handler kills the process. Swallow them.
_ERROR_HANDLER_TYPE = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
_error_handler = _ERROR_HANDLER_TYPE(lambda display, event: 0)
xlib.XSetErrorHandler(_error_handler)


class Display:
    """An X connection plus the handful of EWMH operations we need."""

    def __init__(self, name=None):
        self.ptr = xlib.XOpenDisplay(name.encode() if name else None)
        if not self.ptr:
            raise RuntimeError("cannot open X display")

        self.screen = xlib.XDefaultScreen(self.ptr)
        self.root = xlib.XRootWindow(self.ptr, self.screen)
        self.visual = xlib.XDefaultVisual(self.ptr, self.screen)
        self.depth = xlib.XDefaultDepth(self.ptr, self.screen)
        self.width = xlib.XDisplayWidth(self.ptr, self.screen)
        self.height = xlib.XDisplayHeight(self.ptr, self.screen)
        self.fd = xlib.XConnectionNumber(self.ptr)

        self._atoms = {}

    # -- atoms and properties -------------------------------------------------

    def atom(self, name):
        if name not in self._atoms:
            self._atoms[name] = xlib.XInternAtom(self.ptr, name.encode(), False)
        return self._atoms[name]

    def _property(self, window, name, want_type=0):
        """Raw property bytes, or None. Reads the whole value."""
        actual_type = Atom()
        actual_format = ctypes.c_int()
        nitems = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        data = ctypes.POINTER(ctypes.c_ubyte)()

        status = xlib.XGetWindowProperty(
            self.ptr, window, self.atom(name), 0, 0x7FFFFFFF, False,
            want_type, ctypes.byref(actual_type), ctypes.byref(actual_format),
            ctypes.byref(nitems), ctypes.byref(bytes_after),
            ctypes.byref(data))

        if status != 0 or not data:
            return None, 0, 0

        width = actual_format.value // 8
        # A 32-bit X property is returned as an array of C longs, which are
        # 64-bit here; that is Xlib's documented behaviour, not a bug.
        if actual_format.value == 32:
            width = ctypes.sizeof(ctypes.c_long)
        size = nitems.value * width
        raw = bytes(bytearray(data[:size])) if size else b""
        xlib.XFree(data)
        return raw, actual_format.value, nitems.value

    def get_cardinals(self, window, name):
        """A 32-bit CARDINAL/WINDOW/ATOM property as a list of ints."""
        raw, fmt, count = self._property(window, name)
        if not raw or fmt != 32:
            return []
        longs = struct.unpack(f"{count}l", raw[:count * ctypes.sizeof(ctypes.c_long)])
        return [v & 0xFFFFFFFFFFFFFFFF if v < 0 else v for v in longs]

    def get_text(self, window, name):
        """A UTF8_STRING or STRING property, decoded."""
        raw, _, _ = self._property(window, name)
        if not raw:
            return ""
        return raw.split(b"\x00")[0].decode("utf-8", "replace")

    # -- window queries -------------------------------------------------------

    def client_list(self):
        """Managed windows, bottom of the stack first."""
        return self.get_cardinals(self.root, "_NET_CLIENT_LIST_STACKING") or \
            self.get_cardinals(self.root, "_NET_CLIENT_LIST")

    def active_window(self):
        values = self.get_cardinals(self.root, "_NET_ACTIVE_WINDOW")
        return values[0] if values else 0

    def window_title(self, window):
        return (self.get_text(window, "_NET_WM_NAME") or
                self.get_text(window, "WM_NAME"))

    def window_states(self, window):
        return set(self.get_cardinals(window, "_NET_WM_STATE"))

    def window_types(self, window):
        return set(self.get_cardinals(window, "_NET_WM_TYPE") or
                   self.get_cardinals(window, "_NET_WM_WINDOW_TYPE"))

    def window_desktop(self, window):
        values = self.get_cardinals(window, "_NET_WM_DESKTOP")
        return values[0] if values else -1

    def current_desktop(self):
        values = self.get_cardinals(self.root, "_NET_CURRENT_DESKTOP")
        return values[0] if values else -1

    def window_icon(self, window, prefer=128):
        """The best `_NET_WM_ICON` image as an RGBA array, or None.

        The property holds one or more images back to back, each prefixed by
        its width and height. Pick the smallest one that is at least `prefer`
        pixels wide, else the largest available.
        """
        values = self.get_cardinals(window, "_NET_WM_ICON")
        if not values:
            return None

        best = None
        i = 0
        while i + 2 <= len(values):
            w, h = values[i], values[i + 1]
            i += 2
            if w <= 0 or h <= 0 or i + w * h > len(values):
                break
            pixels = values[i:i + w * h]
            i += w * h

            if best is None:
                best = (w, h, pixels)
                continue
            bw = best[0]
            if bw < prefer and w > bw:
                best = (w, h, pixels)
            elif w >= prefer and (bw < prefer or w < bw):
                best = (w, h, pixels)

        if best is None:
            return None

        w, h, pixels = best
        argb = np.array(pixels, dtype=np.uint64).astype(np.uint32).reshape(h, w)
        image = np.empty((h, w, 4), dtype=np.uint8)
        image[..., 0] = (argb >> 16) & 0xFF     # R
        image[..., 1] = (argb >> 8) & 0xFF      # G
        image[..., 2] = argb & 0xFF             # B
        image[..., 3] = (argb >> 24) & 0xFF     # A
        return image

    # -- window actions -------------------------------------------------------

    def _send_root_message(self, window, message, data):
        event = XEvent()
        event.xclient.type = 33                 # ClientMessage
        event.xclient.send_event = True
        event.xclient.display = self.ptr
        event.xclient.window = window
        event.xclient.message_type = self.atom(message)
        event.xclient.format = 32
        for index, value in enumerate(data[:5]):
            event.xclient.data.l[index] = value

        xlib.XSendEvent(
            self.ptr, self.root, False,
            SUBSTRUCTURE_NOTIFY_MASK | SUBSTRUCTURE_REDIRECT_MASK,
            ctypes.byref(event))
        xlib.XFlush(self.ptr)

    def activate_window(self, window, timestamp=0):
        # Source indication 2 means "a pager", which window managers honour
        # without the focus-stealing prevention they apply to applications.
        self._send_root_message(
            window, "_NET_ACTIVE_WINDOW", [2, timestamp, 0, 0, 0])

    def close_window(self, window, timestamp=0):
        self._send_root_message(
            window, "_NET_CLOSE_WINDOW", [timestamp, 2, 0, 0, 0])

    # -- input ----------------------------------------------------------------

    def keycode(self, keysym):
        return xlib.XKeysymToKeycode(self.ptr, keysym)

    def keysym(self, keycode, index=0):
        return xlib.XKeycodeToKeysym(self.ptr, keycode, index)

    def grab_key(self, keycode, modifiers):
        """Grab a key, including the CapsLock/NumLock variants of it."""
        for extra in (0, LOCK_MASK, MOD2_MASK, LOCK_MASK | MOD2_MASK):
            xlib.XGrabKey(self.ptr, keycode, modifiers | extra, self.root,
                          True, GRAB_MODE_ASYNC, GRAB_MODE_ASYNC)
        xlib.XSync(self.ptr, False)

    def ungrab_key(self, keycode, modifiers):
        for extra in (0, LOCK_MASK, MOD2_MASK, LOCK_MASK | MOD2_MASK):
            xlib.XUngrabKey(self.ptr, keycode, modifiers | extra, self.root)
        xlib.XSync(self.ptr, False)

    def grab_keyboard(self, window, timestamp=0):
        return xlib.XGrabKeyboard(self.ptr, window, True, GRAB_MODE_ASYNC,
                                  GRAB_MODE_ASYNC, timestamp) == 0

    def ungrab_keyboard(self, timestamp=0):
        xlib.XUngrabKeyboard(self.ptr, timestamp)
        xlib.XFlush(self.ptr)

    def select_input(self, window, mask):
        xlib.XSelectInput(self.ptr, window, mask)

    # -- events ---------------------------------------------------------------

    def pending(self):
        return xlib.XPending(self.ptr)

    def next_event(self):
        event = XEvent()
        xlib.XNextEvent(self.ptr, ctypes.byref(event))
        return event

    def flush(self):
        xlib.XFlush(self.ptr)

    def sync(self):
        xlib.XSync(self.ptr, False)


class Canvas:
    """A full-screen, unmanaged window that numpy arrays are blitted into.

    The window is override-redirect, so no window manager touches it: it never
    appears in a taskbar, never steals a workspace, and is always on top. That
    also means it behaves identically under every desktop.
    """

    def __init__(self, display):
        self.display = display
        self.width = display.width
        self.height = display.height

        attrs = XSetWindowAttributes()
        attrs.background_pixel = 0
        attrs.override_redirect = True
        attrs.event_mask = KEY_PRESS_MASK | KEY_RELEASE_MASK | EXPOSURE_MASK

        self.window = xlib.XCreateWindow(
            display.ptr, display.root, 0, 0, self.width, self.height, 0,
            display.depth, INPUT_OUTPUT, display.visual,
            CW_BACK_PIXEL | CW_OVERRIDE_REDIRECT | CW_EVENT_MASK,
            ctypes.byref(attrs))

        # Announce ourselves anyway, for the benefit of compositors that peek.
        utf8 = display.atom("UTF8_STRING")
        name = b"globeswitcher"
        xlib.XChangeProperty(
            display.ptr, self.window, display.atom("_NET_WM_NAME"), utf8, 8,
            0, name, len(name))

        self.gc = xlib.XCreateGC(display.ptr, self.window, 0, None)

        # One buffer and one XImage for the life of the process: the screen
        # size does not change under us, and reusing them keeps opening the
        # switcher free of allocation.
        self._buffer = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self._buffer[..., 3] = 255
        self._image = xlib.XCreateImage(
            display.ptr, display.visual, display.depth, Z_PIXMAP, 0,
            self._buffer.ctypes.data_as(ctypes.c_char_p),
            self.width, self.height, 32, 0)
        self.mapped = False

    def set_frame(self, rgb):
        """Replace the whole frame with an RGB uint8 array of screen size."""
        if rgb.shape[:2] != (self.height, self.width):
            raise ValueError("frame is not the size of the screen")
        self.write_rect(rgb, 0, 0, blit=False)

    def write_rect(self, rgb, x, y, blit=True):
        """Write an RGB block into the frame at (x, y), and optionally show it.

        X wants each pixel as a little-endian 32-bit value, which puts the
        bytes in memory in B, G, R, unused order.
        """
        height, width = rgb.shape[:2]
        region = self._buffer[y:y + height, x:x + width]
        region[..., 0] = rgb[..., 2]
        region[..., 1] = rgb[..., 1]
        region[..., 2] = rgb[..., 0]
        if blit:
            self.blit(x, y, width, height)

    def blit(self, x=0, y=0, width=None, height=None):
        """Push part of the current frame to the server."""
        width = self.width if width is None else width
        height = self.height if height is None else height
        xlib.XPutImage(self.display.ptr, self.window, self.gc, self._image,
                       x, y, x, y, width, height)
        xlib.XFlush(self.display.ptr)

    def show(self):
        xlib.XMapRaised(self.display.ptr, self.window)
        self.mapped = True
        xlib.XFlush(self.display.ptr)

    def hide(self):
        xlib.XUnmapWindow(self.display.ptr, self.window)
        self.mapped = False
        xlib.XFlush(self.display.ptr)

    def destroy(self):
        if self.gc:
            xlib.XFreeGC(self.display.ptr, self.gc)
            self.gc = None
        if self.window:
            xlib.XDestroyWindow(self.display.ptr, self.window)
            self.window = 0


def grab_screen(display):
    """The current screen contents as an RGB array, or None if unreadable."""
    image = xlib.XGetImage(
        display.ptr, display.root, 0, 0, display.width, display.height,
        0xFFFFFFFF, Z_PIXMAP)
    if not image:
        return None

    info = image.contents
    if info.bits_per_pixel != 32:
        return None

    size = info.bytes_per_line * info.height
    raw = ctypes.string_at(info.data, size)
    stride = info.bytes_per_line // 4
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(
        info.height, stride, 4)[:, :info.width]

    rgb = np.empty((info.height, info.width, 3), dtype=np.uint8)
    rgb[..., 0] = pixels[..., 2]
    rgb[..., 1] = pixels[..., 1]
    rgb[..., 2] = pixels[..., 0]
    return rgb
