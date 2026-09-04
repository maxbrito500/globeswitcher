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

import numpy as np

# --- library -----------------------------------------------------------------

_lib_name = ctypes.util.find_library("X11")
if not _lib_name:
    raise ImportError("libX11 not found")
xlib = ctypes.CDLL(_lib_name)

# The shared-memory extension is optional. With it, a frame is written
# straight into memory the X server already has mapped; without it every
# frame is copied down the socket instead.
try:
    _xext_name = ctypes.util.find_library("Xext")
    xext = ctypes.CDLL(_xext_name) if _xext_name else None
except OSError:
    xext = None

try:
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
except OSError:
    libc = None

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


class XWindowAttributes(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
        ("border_width", ctypes.c_int),
        ("depth", ctypes.c_int),
        ("visual", ctypes.c_void_p),
        ("root", Window),
        ("class_", ctypes.c_int),
        ("bit_gravity", ctypes.c_int),
        ("win_gravity", ctypes.c_int),
        ("backing_store", ctypes.c_int),
        ("backing_planes", ctypes.c_ulong),
        ("backing_pixel", ctypes.c_ulong),
        ("save_under", ctypes.c_int),
        ("colormap", Colormap),
        ("map_installed", ctypes.c_int),
        ("map_state", ctypes.c_int),
        ("all_event_masks", ctypes.c_long),
        ("your_event_mask", ctypes.c_long),
        ("do_not_propagate_mask", ctypes.c_long),
        ("override_redirect", ctypes.c_int),
        ("screen", ctypes.c_void_p),
    ]


IS_VIEWABLE = 2


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

xlib.XGetWindowAttributes.argtypes = [
    ctypes.c_void_p, Window, ctypes.POINTER(XWindowAttributes),
]
xlib.XGetWindowAttributes.restype = ctypes.c_int

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


class XShmSegmentInfo(ctypes.Structure):
    _fields_ = [
        ("shmseg", ctypes.c_ulong),
        ("shmid", ctypes.c_int),
        ("shmaddr", ctypes.c_char_p),
        ("readOnly", ctypes.c_int),
    ]


IPC_PRIVATE = 0
IPC_CREAT = 0o1000
IPC_RMID = 0

if xext is not None:
    xext.XShmQueryExtension.argtypes = [ctypes.c_void_p]
    xext.XShmQueryExtension.restype = ctypes.c_int
    xext.XShmCreateImage.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_int,
        ctypes.c_char_p, ctypes.POINTER(XShmSegmentInfo), ctypes.c_uint,
        ctypes.c_uint,
    ]
    xext.XShmCreateImage.restype = ctypes.POINTER(XImage)
    xext.XShmAttach.argtypes = [ctypes.c_void_p,
                                ctypes.POINTER(XShmSegmentInfo)]
    xext.XShmDetach.argtypes = [ctypes.c_void_p,
                                ctypes.POINTER(XShmSegmentInfo)]
    xext.XShmPutImage.argtypes = [
        ctypes.c_void_p, Window, ctypes.c_void_p, ctypes.POINTER(XImage),
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_uint, ctypes.c_uint, ctypes.c_int,
    ]

if libc is not None:
    libc.shmget.argtypes = [ctypes.c_int, ctypes.c_size_t, ctypes.c_int]
    libc.shmget.restype = ctypes.c_int
    libc.shmat.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
    libc.shmat.restype = ctypes.c_void_p
    libc.shmdt.argtypes = [ctypes.c_void_p]
    libc.shmctl.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]


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

        # string_at copies the block in one go. Slicing the ctypes pointer
        # instead would build a Python list with one int per byte, which on a
        # window shipping a megabyte of icons costs a third of a second.
        raw = ctypes.string_at(ctypes.cast(data, ctypes.c_void_p), size) \
            if size else b""
        xlib.XFree(data)
        return raw, actual_format.value, nitems.value

    def get_cardinals(self, window, name):
        """A 32-bit CARDINAL/WINDOW/ATOM property, as an array of ints.

        Returned as numpy rather than a list: `_NET_WM_ICON` can hold a
        million entries, and building a Python list of those is slower than
        everything else the switcher does put together.
        """
        raw, fmt, count = self._property(window, name)
        if not raw or fmt != 32:
            return np.empty(0, dtype=np.uint64)

        stride = ctypes.sizeof(ctypes.c_long)
        usable = (len(raw) // stride) * stride
        return np.frombuffer(raw[:usable], dtype=np.uint64)

    def get_ints(self, window, name):
        """The same, as a plain list. For properties known to be short."""
        return self.get_cardinals(window, name).tolist()

    def get_text(self, window, name):
        """A UTF8_STRING or STRING property, decoded."""
        raw, _, _ = self._property(window, name)
        if not raw:
            return ""
        return raw.split(b"\x00")[0].decode("utf-8", "replace")

    # -- window queries -------------------------------------------------------

    def client_list(self):
        """Managed windows, bottom of the stack first."""
        return (self.get_ints(self.root, "_NET_CLIENT_LIST_STACKING") or
                self.get_ints(self.root, "_NET_CLIENT_LIST"))

    def active_window(self):
        values = self.get_ints(self.root, "_NET_ACTIVE_WINDOW")
        return values[0] if values else 0

    def window_title(self, window):
        return (self.get_text(window, "_NET_WM_NAME") or
                self.get_text(window, "WM_NAME"))

    def window_states(self, window):
        return set(self.get_ints(window, "_NET_WM_STATE"))

    def window_types(self, window):
        return set(self.get_ints(window, "_NET_WM_WINDOW_TYPE"))

    def window_desktop(self, window):
        values = self.get_ints(window, "_NET_WM_DESKTOP")
        return values[0] if values else -1

    def current_desktop(self):
        values = self.get_ints(self.root, "_NET_CURRENT_DESKTOP")
        return values[0] if values else -1

    def window_icon(self, window, prefer=128):
        """The best `_NET_WM_ICON` image as an RGBA array, or None.

        The property holds one or more images back to back, each prefixed by
        its width and height. Pick the smallest one that is at least `prefer`
        pixels wide, else the largest available.
        """
        values = self.get_cardinals(window, "_NET_WM_ICON")
        if values.size < 3:
            return None

        best = None
        offset = 0
        while offset + 2 <= values.size:
            width = int(values[offset])
            height = int(values[offset + 1])
            offset += 2
            if width <= 0 or height <= 0 or offset + width * height > values.size:
                break

            block = values[offset:offset + width * height]
            offset += width * height

            if best is None:
                best = (width, height, block)
                continue
            # The smallest icon that is still at least `prefer` wide, or the
            # largest one on offer if none of them reach it.
            current = best[0]
            if current < prefer and width > current:
                best = (width, height, block)
            elif width >= prefer and (current < prefer or width < current):
                best = (width, height, block)

        if best is None:
            return None

        width, height, block = best
        argb = block.astype(np.uint32).reshape(height, width)
        image = np.empty((height, width, 4), dtype=np.uint8)
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
        self._shm = None
        self._image = None
        self._buffer = None
        self._setup_image()
        self._buffer[..., 3] = 255
        self.mapped = False

    def _setup_image(self):
        """Prefer a shared-memory image; fall back to a normal one."""
        if self._setup_shared_image():
            return

        self._buffer = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self._image = xlib.XCreateImage(
            self.display.ptr, self.display.visual, self.display.depth,
            Z_PIXMAP, 0, self._buffer.ctypes.data_as(ctypes.c_char_p),
            self.width, self.height, 32, 0)

    def _setup_shared_image(self):
        if xext is None or libc is None:
            return False
        if not xext.XShmQueryExtension(self.display.ptr):
            return False

        info = XShmSegmentInfo()
        image = xext.XShmCreateImage(
            self.display.ptr, self.display.visual, self.display.depth,
            Z_PIXMAP, None, ctypes.byref(info), self.width, self.height)
        if not image:
            return False

        size = image.contents.bytes_per_line * image.contents.height
        info.shmid = libc.shmget(IPC_PRIVATE, size, IPC_CREAT | 0o600)
        if info.shmid < 0:
            xlib.XDestroyImage(image)
            return False

        address = libc.shmat(info.shmid, None, 0)
        if address in (None, ctypes.c_void_p(-1).value):
            libc.shmctl(info.shmid, IPC_RMID, None)
            xlib.XDestroyImage(image)
            return False

        info.shmaddr = ctypes.cast(address, ctypes.c_char_p)
        image.contents.data = address
        info.readOnly = False

        if not xext.XShmAttach(self.display.ptr, ctypes.byref(info)):
            libc.shmdt(ctypes.c_void_p(address))
            libc.shmctl(info.shmid, IPC_RMID, None)
            xlib.XDestroyImage(image)
            return False
        self.display.sync()

        # Marked for destruction now; the segment survives until both the
        # server and this process detach, so nothing is leaked on a crash.
        libc.shmctl(info.shmid, IPC_RMID, None)

        buffer_type = ctypes.c_uint8 * size
        raw = buffer_type.from_address(address)
        stride = image.contents.bytes_per_line // 4
        self._buffer = np.frombuffer(raw, dtype=np.uint8).reshape(
            self.height, stride, 4)[:, :self.width]
        self._image = image
        self._shm = info
        return True

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
        if self._shm is not None:
            xext.XShmPutImage(self.display.ptr, self.window, self.gc,
                              self._image, x, y, x, y, width, height, False)
        else:
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
        if self._shm is not None:
            self._buffer = None
            xext.XShmDetach(self.display.ptr, ctypes.byref(self._shm))
            self.display.sync()
            libc.shmdt(ctypes.c_void_p(
                ctypes.cast(self._shm.shmaddr, ctypes.c_void_p).value))
            self._shm = None

    @property
    def shared(self):
        """Whether frames go through shared memory rather than the socket."""
        return self._shm is not None


def _image_to_rgb(image):
    """An XImage of 32-bit pixels as an RGB array, or None."""
    info = image.contents
    if info.bits_per_pixel != 32 or info.width <= 0 or info.height <= 0:
        return None

    raw = ctypes.string_at(info.data, info.bytes_per_line * info.height)
    stride = info.bytes_per_line // 4
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(
        info.height, stride, 4)[:, :info.width]

    rgb = np.empty((info.height, info.width, 3), dtype=np.uint8)
    rgb[..., 0] = pixels[..., 2]
    rgb[..., 1] = pixels[..., 1]
    rgb[..., 2] = pixels[..., 0]
    return rgb


def grab_screen(display):
    """The current screen contents as an RGB array, or None if unreadable."""
    image = xlib.XGetImage(
        display.ptr, display.root, 0, 0, display.width, display.height,
        0xFFFFFFFF, Z_PIXMAP)
    if not image:
        return None
    try:
        return _image_to_rgb(image)
    finally:
        xlib.XDestroyImage(image)


def capture_window(display, window):
    """A window's own contents as an RGB array, or None.

    Under a compositing window manager the server keeps the contents of every
    mapped window, so this works even for windows buried behind others. Without
    a compositor an obscured window has no stored contents and the result is
    whatever happens to be on top of it, which is why the caller treats this as
    best effort and falls back to the application icon.
    """
    attributes = XWindowAttributes()
    if not xlib.XGetWindowAttributes(display.ptr, window,
                                     ctypes.byref(attributes)):
        return None
    if attributes.map_state != IS_VIEWABLE:
        return None
    if attributes.width < 16 or attributes.height < 16:
        return None

    image = xlib.XGetImage(
        display.ptr, window, 0, 0, attributes.width, attributes.height,
        0xFFFFFFFF, Z_PIXMAP)
    if not image:
        return None
    try:
        return _image_to_rgb(image)
    finally:
        xlib.XDestroyImage(image)
