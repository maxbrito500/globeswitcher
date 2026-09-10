// Copyright 2026 Max Brito
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// SPDX-License-Identifier: Apache-2.0

/// Bindings to the parts of Xlib the switcher needs.
///
/// Only what is actually called is bound. Calling libX11 from Dart directly
/// means the Linux backend needs no C plugin of its own: the same trick works
/// against user32.dll on Windows, so each platform stays one Dart file.
library;

import 'dart:ffi';

import 'package:ffi/ffi.dart';

// --- constants ---------------------------------------------------------------

const int zPixmap = 2;

// Event types.
const int keyPress = 2;
const int keyRelease = 3;
const int expose = 12;
const int clientMessage = 33;
const int propertyNotify = 28;

// Event masks.
const int keyPressMask = 1 << 0;
const int keyReleaseMask = 1 << 1;
const int exposureMask = 1 << 15;
const int substructureNotifyMask = 1 << 19;
const int substructureRedirectMask = 1 << 20;
const int propertyChangeMask = 1 << 22;

// Modifiers.
const int shiftMask = 1 << 0;
const int lockMask = 1 << 1;
const int controlMask = 1 << 2;
const int mod1Mask = 1 << 3; // Alt
const int mod2Mask = 1 << 4; // NumLock, usually
const int mod4Mask = 1 << 6; // Super

const int grabModeAsync = 1;
const int isViewable = 2;

// Keysyms.
const int xkTab = 0xFF09;
const int xkIsoLeftTab = 0xFE20;
const int xkEscape = 0xFF1B;
const int xkAltL = 0xFFE9;
const int xkAltR = 0xFFEA;
const int xkMetaL = 0xFFE7;
const int xkMetaR = 0xFFE8;
const int xkReturn = 0xFF0D;
const int xkKpEnter = 0xFF8D;
const int xkSpace = 0x0020;
const int xkLeft = 0xFF51;
const int xkUp = 0xFF52;
const int xkRight = 0xFF53;
const int xkDown = 0xFF54;
const int xkKpLeft = 0xFF96;
const int xkKpUp = 0xFF97;
const int xkKpRight = 0xFF98;
const int xkKpDown = 0xFF99;
const int xkHome = 0xFF50;
const int xkEnd = 0xFF57;
const int xkF4 = 0xFFC1;
const int xkW = 0x0077;
const int xkQ = 0x0071;

// --- structures --------------------------------------------------------------

/// Big enough for any XEvent; the union is read through the views below.
const int xEventSize = 256;

final class XAnyEvent extends Struct {
  @Int32()
  external int type;
  @IntPtr()
  external int serial;
  @Int32()
  external int sendEvent;
  external Pointer<Void> display;
  @IntPtr()
  external int window;
}

final class XKeyEvent extends Struct {
  @Int32()
  external int type;
  @IntPtr()
  external int serial;
  @Int32()
  external int sendEvent;
  external Pointer<Void> display;
  @IntPtr()
  external int window;
  @IntPtr()
  external int root;
  @IntPtr()
  external int subwindow;
  @IntPtr()
  external int time;
  @Int32()
  external int x;
  @Int32()
  external int y;
  @Int32()
  external int xRoot;
  @Int32()
  external int yRoot;
  @Uint32()
  external int state;
  @Uint32()
  external int keycode;
  @Int32()
  external int sameScreen;
}

final class XPropertyEvent extends Struct {
  @Int32()
  external int type;
  @IntPtr()
  external int serial;
  @Int32()
  external int sendEvent;
  external Pointer<Void> display;
  @IntPtr()
  external int window;
  @IntPtr()
  external int atom;
  @IntPtr()
  external int time;
  @Int32()
  external int state;
}

final class XClientMessageEvent extends Struct {
  @Int32()
  external int type;
  @IntPtr()
  external int serial;
  @Int32()
  external int sendEvent;
  external Pointer<Void> display;
  @IntPtr()
  external int window;
  @IntPtr()
  external int messageType;
  @Int32()
  external int format;
  @Array(5)
  external Array<IntPtr> data;
}

final class XWindowAttributes extends Struct {
  @Int32()
  external int x;
  @Int32()
  external int y;
  @Int32()
  external int width;
  @Int32()
  external int height;
  @Int32()
  external int borderWidth;
  @Int32()
  external int depth;
  external Pointer<Void> visual;
  @IntPtr()
  external int root;
  @Int32()
  external int classId;
  @Int32()
  external int bitGravity;
  @Int32()
  external int winGravity;
  @Int32()
  external int backingStore;
  @IntPtr()
  external int backingPlanes;
  @IntPtr()
  external int backingPixel;
  @Int32()
  external int saveUnder;
  @IntPtr()
  external int colormap;
  @Int32()
  external int mapInstalled;
  @Int32()
  external int mapState;
  @IntPtr()
  external int allEventMasks;
  @IntPtr()
  external int yourEventMask;
  @IntPtr()
  external int doNotPropagateMask;
  @Int32()
  external int overrideRedirect;
  external Pointer<Void> screen;
}

final class XImage extends Struct {
  @Int32()
  external int width;
  @Int32()
  external int height;
  @Int32()
  external int xoffset;
  @Int32()
  external int format;
  external Pointer<Uint8> data;
  @Int32()
  external int byteOrder;
  @Int32()
  external int bitmapUnit;
  @Int32()
  external int bitmapBitOrder;
  @Int32()
  external int bitmapPad;
  @Int32()
  external int depth;
  @Int32()
  external int bytesPerLine;
  @Int32()
  external int bitsPerPixel;
  @IntPtr()
  external int redMask;
  @IntPtr()
  external int greenMask;
  @IntPtr()
  external int blueMask;
}

// --- library -----------------------------------------------------------------

final DynamicLibrary _x11 = DynamicLibrary.open('libX11.so.6');

final Pointer<Void> Function(Pointer<Utf8>) xOpenDisplay = _x11
    .lookupFunction<Pointer<Void> Function(Pointer<Utf8>),
        Pointer<Void> Function(Pointer<Utf8>)>('XOpenDisplay');

final int Function(Pointer<Void>) xDefaultScreen =
    _x11.lookupFunction<Int32 Function(Pointer<Void>), int Function(Pointer<Void>)>(
        'XDefaultScreen');

final int Function(Pointer<Void>, int) xRootWindow = _x11.lookupFunction<
    IntPtr Function(Pointer<Void>, Int32), int Function(Pointer<Void>, int)>(
    'XRootWindow');

final int Function(Pointer<Void>, int) xDisplayWidth = _x11.lookupFunction<
    Int32 Function(Pointer<Void>, Int32), int Function(Pointer<Void>, int)>(
    'XDisplayWidth');

final int Function(Pointer<Void>, int) xDisplayHeight = _x11.lookupFunction<
    Int32 Function(Pointer<Void>, Int32), int Function(Pointer<Void>, int)>(
    'XDisplayHeight');

final int Function(Pointer<Void>, Pointer<Utf8>, int) xInternAtom =
    _x11.lookupFunction<IntPtr Function(Pointer<Void>, Pointer<Utf8>, Int32),
        int Function(Pointer<Void>, Pointer<Utf8>, int)>('XInternAtom');

final int Function(
    Pointer<Void>,
    int,
    int,
    int,
    int,
    int,
    int,
    Pointer<IntPtr>,
    Pointer<Int32>,
    Pointer<IntPtr>,
    Pointer<IntPtr>,
    Pointer<Pointer<Uint8>>) xGetWindowProperty = _x11.lookupFunction<
    Int32 Function(
        Pointer<Void>,
        IntPtr,
        IntPtr,
        IntPtr,
        IntPtr,
        Int32,
        IntPtr,
        Pointer<IntPtr>,
        Pointer<Int32>,
        Pointer<IntPtr>,
        Pointer<IntPtr>,
        Pointer<Pointer<Uint8>>),
    int Function(
        Pointer<Void>,
        int,
        int,
        int,
        int,
        int,
        int,
        Pointer<IntPtr>,
        Pointer<Int32>,
        Pointer<IntPtr>,
        Pointer<IntPtr>,
        Pointer<Pointer<Uint8>>)>('XGetWindowProperty');

final void Function(Pointer<Void>) xFree =
    _x11.lookupFunction<Void Function(Pointer<Void>), void Function(Pointer<Void>)>(
        'XFree');

final int Function(Pointer<Void>, int, Pointer<XWindowAttributes>)
    xGetWindowAttributes = _x11.lookupFunction<
        Int32 Function(Pointer<Void>, IntPtr, Pointer<XWindowAttributes>),
        int Function(Pointer<Void>, int,
            Pointer<XWindowAttributes>)>('XGetWindowAttributes');

final Pointer<XImage> Function(Pointer<Void>, int, int, int, int, int, int, int)
    xGetImage = _x11.lookupFunction<
        Pointer<XImage> Function(
            Pointer<Void>, IntPtr, Int32, Int32, Uint32, Uint32, IntPtr, Int32),
        Pointer<XImage> Function(Pointer<Void>, int, int, int, int, int, int,
            int)>('XGetImage');

final int Function(Pointer<XImage>) xDestroyImage = _x11.lookupFunction<
    Int32 Function(Pointer<XImage>), int Function(Pointer<XImage>)>(
    'XDestroyImage');

final int Function(Pointer<Void>, int, int, int, Pointer<Uint8>) xSendEvent =
    _x11.lookupFunction<
        Int32 Function(Pointer<Void>, IntPtr, Int32, IntPtr, Pointer<Uint8>),
        int Function(Pointer<Void>, int, int, int,
            Pointer<Uint8>)>('XSendEvent');

final int Function(Pointer<Void>, int) xKeysymToKeycode = _x11.lookupFunction<
    Uint8 Function(Pointer<Void>, IntPtr), int Function(Pointer<Void>, int)>(
    'XKeysymToKeycode');

final int Function(Pointer<Void>, int, int) xKeycodeToKeysym =
    _x11.lookupFunction<IntPtr Function(Pointer<Void>, Uint8, Int32),
        int Function(Pointer<Void>, int, int)>('XKeycodeToKeysym');

final int Function(Pointer<Void>, int, int, int, int, int, int) xGrabKey =
    _x11.lookupFunction<
        Int32 Function(
            Pointer<Void>, Int32, Uint32, IntPtr, Int32, Int32, Int32),
        int Function(
            Pointer<Void>, int, int, int, int, int, int)>('XGrabKey');

final int Function(Pointer<Void>, int, int, int) xUngrabKey =
    _x11.lookupFunction<Int32 Function(Pointer<Void>, Int32, Uint32, IntPtr),
        int Function(Pointer<Void>, int, int, int)>('XUngrabKey');

final int Function(Pointer<Void>, int, int, int, int, int) xGrabKeyboard =
    _x11.lookupFunction<
        Int32 Function(Pointer<Void>, IntPtr, Int32, Int32, Int32, IntPtr),
        int Function(
            Pointer<Void>, int, int, int, int, int)>('XGrabKeyboard');

final int Function(Pointer<Void>, int) xUngrabKeyboard = _x11.lookupFunction<
    Int32 Function(Pointer<Void>, IntPtr), int Function(Pointer<Void>, int)>(
    'XUngrabKeyboard');

final int Function(Pointer<Void>, int, Pointer<IntPtr>, Pointer<IntPtr>,
        Pointer<Int32>, Pointer<Int32>, Pointer<Int32>, Pointer<Int32>,
        Pointer<Uint32>) xQueryPointer =
    _x11.lookupFunction<
        Int32 Function(Pointer<Void>, IntPtr, Pointer<IntPtr>, Pointer<IntPtr>,
            Pointer<Int32>, Pointer<Int32>, Pointer<Int32>, Pointer<Int32>,
            Pointer<Uint32>),
        int Function(Pointer<Void>, int, Pointer<IntPtr>, Pointer<IntPtr>,
            Pointer<Int32>, Pointer<Int32>, Pointer<Int32>, Pointer<Int32>,
            Pointer<Uint32>)>('XQueryPointer');

final int Function(Pointer<Void>, int, int) xSelectInput = _x11.lookupFunction<
    Int32 Function(Pointer<Void>, IntPtr, IntPtr),
    int Function(Pointer<Void>, int, int)>('XSelectInput');

final int Function(Pointer<Void>) xPending =
    _x11.lookupFunction<Int32 Function(Pointer<Void>), int Function(Pointer<Void>)>(
        'XPending');

final int Function(Pointer<Void>, Pointer<Uint8>) xNextEvent =
    _x11.lookupFunction<Int32 Function(Pointer<Void>, Pointer<Uint8>),
        int Function(Pointer<Void>, Pointer<Uint8>)>('XNextEvent');

final int Function(Pointer<Void>, int) xSync = _x11.lookupFunction<
    Int32 Function(Pointer<Void>, Int32), int Function(Pointer<Void>, int)>(
    'XSync');

final int Function(Pointer<Void>) xFlush =
    _x11.lookupFunction<Int32 Function(Pointer<Void>), int Function(Pointer<Void>)>(
        'XFlush');

// There is deliberately no XSetErrorHandler binding here. Xlib's error handler
// is one per process and is called from whatever thread and whatever moment an
// error comes back in -- GDK's connection, the GL layer, a GTK idle -- and a
// Dart callback invoked with no Dart frame on the stack aborts the process
// ("Cannot invoke native callback outside an isolate"). The runner installs a
// native no-op handler instead; see linux/runner/my_application.cc.
