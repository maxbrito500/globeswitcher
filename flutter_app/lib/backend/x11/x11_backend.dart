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

/// The X11 backend: EWMH for the window list, XGetImage for the pictures.
library;

import 'dart:async';
import 'dart:ffi';
import 'dart:convert';
import 'dart:typed_data';

import 'package:ffi/ffi.dart';

import '../window_backend.dart';
import 'xlib.dart';

/// Window types that are never worth switching to.
const List<String> _skippedTypes = [
  '_NET_WM_WINDOW_TYPE_DESKTOP',
  '_NET_WM_WINDOW_TYPE_DOCK',
  '_NET_WM_WINDOW_TYPE_TOOLBAR',
  '_NET_WM_WINDOW_TYPE_MENU',
  '_NET_WM_WINDOW_TYPE_SPLASH',
  '_NET_WM_WINDOW_TYPE_POPUP_MENU',
  '_NET_WM_WINDOW_TYPE_TOOLTIP',
  '_NET_WM_WINDOW_TYPE_NOTIFICATION',
];

const int _allDesktops = 0xFFFFFFFF;

/// How often the X connection is drained. The keyboard is held while the
/// switcher is up, so this is what turns a key press into a frame.
const Duration _pollInterval = Duration(milliseconds: 4);

class X11Backend implements WindowBackend {
  X11Backend._(this._display, this.screenWidth, this.screenHeight)
      : _root = xRootWindow(_display, xDefaultScreen(_display));

  /// Opens the display, or returns null when there is no X server to talk to.
  static X11Backend? open() {
    installErrorHandler();
    final display = xOpenDisplay(nullptr);
    if (display == nullptr) return null;

    final screen = xDefaultScreen(display);
    final backend = X11Backend._(
        display, xDisplayWidth(display, screen), xDisplayHeight(display, screen));
    backend._start();
    return backend;
  }

  final Pointer<Void> _display;
  final int _root;
  final int screenWidth;
  final int screenHeight;

  final Map<String, int> _atoms = {};
  final List<int> _mru = [];
  final List<int> _grabbedKeys = [];

  final StreamController<SwitcherKey> _keys = StreamController.broadcast();
  final StreamController<void> _released = StreamController.broadcast();

  void Function({required bool backwards})? _onShortcut;
  Timer? _pump;
  bool _keyboardHeld = false;
  late final Pointer<Uint8> _eventBuffer = calloc<Uint8>(xEventSize);

  @override
  bool get isAvailable => true;

  @override
  Stream<SwitcherKey> get keys => _keys.stream;

  @override
  Stream<void> get modifiersReleased => _released.stream;

  void _start() {
    xSelectInput(_display, _root, propertyChangeMask);
    _syncMru();
    _pump = Timer.periodic(_pollInterval, (_) => _drain());
  }

  // -- atoms and properties ---------------------------------------------------

  int _atom(String name) => _atoms.putIfAbsent(name, () {
        final native = name.toNativeUtf8();
        try {
          return xInternAtom(_display, native, 0);
        } finally {
          calloc.free(native);
        }
      });

  /// A 32-bit property as a list of ints. X hands these back as C longs, which
  /// are 64 bits here; that is Xlib's documented behaviour, not a bug.
  Int64List _cardinals(int window, String name) {
    final actualType = calloc<IntPtr>();
    final actualFormat = calloc<Int32>();
    final items = calloc<IntPtr>();
    final after = calloc<IntPtr>();
    final data = calloc<Pointer<Uint8>>();

    try {
      final status = xGetWindowProperty(_display, window, _atom(name), 0,
          0x7FFFFFFF, 0, 0, actualType, actualFormat, items, after, data);
      if (status != 0 || data.value == nullptr || actualFormat.value != 32) {
        if (data.value != nullptr) xFree(data.value.cast());
        return Int64List(0);
      }
      final count = items.value;
      final view = data.value.cast<Int64>().asTypedList(count);
      final copy = Int64List.fromList(view);
      xFree(data.value.cast());
      return copy;
    } finally {
      calloc.free(actualType);
      calloc.free(actualFormat);
      calloc.free(items);
      calloc.free(after);
      calloc.free(data);
    }
  }

  String _text(int window, String name) {
    final actualType = calloc<IntPtr>();
    final actualFormat = calloc<Int32>();
    final items = calloc<IntPtr>();
    final after = calloc<IntPtr>();
    final data = calloc<Pointer<Uint8>>();

    try {
      final status = xGetWindowProperty(_display, window, _atom(name), 0,
          0x7FFFFFFF, 0, 0, actualType, actualFormat, items, after, data);
      if (status != 0 || data.value == nullptr) return '';
      final bytes = Uint8List.fromList(data.value.asTypedList(items.value));
      xFree(data.value.cast());

      final end = bytes.indexOf(0);
      return utf8.decode(end < 0 ? bytes : bytes.sublist(0, end),
          allowMalformed: true);
    } finally {
      calloc.free(actualType);
      calloc.free(actualFormat);
      calloc.free(items);
      calloc.free(after);
      calloc.free(data);
    }
  }

  // -- window list ------------------------------------------------------------

  List<int> _clientList() {
    final stacking = _cardinals(_root, '_NET_CLIENT_LIST_STACKING');
    if (stacking.isNotEmpty) return stacking.toList();
    return _cardinals(_root, '_NET_CLIENT_LIST').toList();
  }

  int _activeWindow() {
    final values = _cardinals(_root, '_NET_ACTIVE_WINDOW');
    return values.isEmpty ? 0 : values.first;
  }

  void _syncMru() {
    final current = _clientList();
    final known = _mru.toSet();
    for (final id in current.reversed) {
      if (!known.contains(id)) _mru.add(id);
    }
    final alive = current.toSet();
    _mru.removeWhere((id) => !alive.contains(id));
  }

  void _noteActivation() {
    final active = _activeWindow();
    if (active == 0) return;
    _mru.remove(active);
    _mru.insert(0, active);
  }

  bool _isSwitchable(int id) {
    final states = _cardinals(id, '_NET_WM_STATE');
    if (states.contains(_atom('_NET_WM_STATE_SKIP_TASKBAR'))) return false;

    final types = _cardinals(id, '_NET_WM_WINDOW_TYPE');
    for (final name in _skippedTypes) {
      if (types.contains(_atom(name))) return false;
    }

    final desktop = _cardinals(id, '_NET_WM_DESKTOP');
    final current = _cardinals(_root, '_NET_CURRENT_DESKTOP');
    if (desktop.isNotEmpty && current.isNotEmpty) {
      final on = desktop.first;
      if (on != _allDesktops && on != current.first) return false;
    }
    return true;
  }

  @override
  List<WindowInfo> listWindows() {
    _syncMru();
    final windows = <WindowInfo>[];
    for (final id in _mru) {
      if (!_isSwitchable(id)) continue;
      final icon = _icon(id);
      windows.add(WindowInfo(
        id: id,
        title: _text(id, '_NET_WM_NAME').isNotEmpty
            ? _text(id, '_NET_WM_NAME')
            : _text(id, 'WM_NAME'),
        iconRgba: icon?.rgba,
        iconWidth: icon?.width ?? 0,
        iconHeight: icon?.height ?? 0,
      ));
    }
    return windows;
  }

  /// The best `_NET_WM_ICON` image. The property holds several sizes back to
  /// back, each prefixed by its width and height.
  WindowShot? _icon(int id, {int prefer = 128}) {
    final values = _cardinals(id, '_NET_WM_ICON');
    if (values.length < 3) return null;

    int offset = 0;
    int bestWidth = 0, bestHeight = 0, bestStart = -1;
    while (offset + 2 <= values.length) {
      final width = values[offset];
      final height = values[offset + 1];
      offset += 2;
      if (width <= 0 || height <= 0 || offset + width * height > values.length) {
        break;
      }
      final start = offset;
      offset += width * height;

      final better = bestStart < 0 ||
          (bestWidth < prefer && width > bestWidth) ||
          (width >= prefer && (bestWidth < prefer || width < bestWidth));
      if (better) {
        bestWidth = width;
        bestHeight = height;
        bestStart = start;
      }
    }
    if (bestStart < 0) return null;

    final rgba = Uint8List(bestWidth * bestHeight * 4);
    for (int i = 0; i < bestWidth * bestHeight; i++) {
      final argb = values[bestStart + i];
      rgba[i * 4] = (argb >> 16) & 0xFF;
      rgba[i * 4 + 1] = (argb >> 8) & 0xFF;
      rgba[i * 4 + 2] = argb & 0xFF;
      rgba[i * 4 + 3] = (argb >> 24) & 0xFF;
    }
    return WindowShot(rgba, bestWidth, bestHeight);
  }

  // -- pictures ---------------------------------------------------------------

  WindowShot? _grab(int drawable, int width, int height) {
    if (width < 1 || height < 1) return null;
    final image =
        xGetImage(_display, drawable, 0, 0, width, height, 0xFFFFFFFF, zPixmap);
    if (image == nullptr) return null;

    try {
      final info = image.ref;
      if (info.bitsPerPixel != 32) return null;

      final stride = info.bytesPerLine;
      final bytes = info.data.asTypedList(stride * info.height);
      final rgba = Uint8List(info.width * info.height * 4);

      for (int y = 0; y < info.height; y++) {
        final row = y * stride;
        var out = y * info.width * 4;
        for (int x = 0; x < info.width; x++) {
          final at = row + x * 4;
          rgba[out] = bytes[at + 2];
          rgba[out + 1] = bytes[at + 1];
          rgba[out + 2] = bytes[at];
          rgba[out + 3] = 255;
          out += 4;
        }
      }
      return WindowShot(rgba, info.width, info.height);
    } finally {
      xDestroyImage(image);
    }
  }

  @override
  WindowShot? captureWindow(int id) {
    final attributes = calloc<XWindowAttributes>();
    try {
      if (xGetWindowAttributes(_display, id, attributes) == 0) return null;
      final a = attributes.ref;
      if (a.mapState != isViewable || a.width < 16 || a.height < 16) return null;
      return _grab(id, a.width, a.height);
    } finally {
      calloc.free(attributes);
    }
  }

  @override
  WindowShot? captureScreen() => _grab(_root, screenWidth, screenHeight);

  // -- actions ----------------------------------------------------------------

  void _sendToRoot(int window, String message, List<int> data) {
    final event = calloc<Uint8>(xEventSize);
    try {
      final client = event.cast<XClientMessageEvent>();
      client.ref.type = clientMessage;
      client.ref.sendEvent = 1;
      client.ref.display = _display;
      client.ref.window = window;
      client.ref.messageType = _atom(message);
      client.ref.format = 32;
      for (int i = 0; i < 5; i++) {
        client.ref.data[i] = i < data.length ? data[i] : 0;
      }
      xSendEvent(_display, _root, 0,
          substructureNotifyMask | substructureRedirectMask, event);
      xFlush(_display);
    } finally {
      calloc.free(event);
    }
  }

  @override
  void activateWindow(int id) {
    // Source indication 2 is "a pager", which window managers honour without
    // the focus-stealing prevention they apply to ordinary applications.
    _sendToRoot(id, '_NET_ACTIVE_WINDOW', [2, 0, 0, 0, 0]);
    _mru.remove(id);
    _mru.insert(0, id);
  }

  @override
  void closeWindow(int id) => _sendToRoot(id, '_NET_CLOSE_WINDOW', [0, 2, 0, 0, 0]);

  // -- input ------------------------------------------------------------------

  @override
  void grabSwitcherShortcut(void Function({required bool backwards}) onPress) {
    _onShortcut = onPress;
    final tab = xKeysymToKeycode(_display, xkTab);
    for (final modifiers in [mod1Mask, mod1Mask | shiftMask]) {
      // CapsLock and NumLock are modifiers too, so each has to be grabbed with
      // and without them or the shortcut stops working with the lights on.
      for (final extra in [0, lockMask, mod2Mask, lockMask | mod2Mask]) {
        xGrabKey(_display, tab, modifiers | extra, _root, 1, grabModeAsync,
            grabModeAsync);
      }
      _grabbedKeys.add(modifiers);
    }
    xSync(_display, 0);
  }

  @override
  void releaseSwitcherShortcut() {
    final tab = xKeysymToKeycode(_display, xkTab);
    for (final modifiers in _grabbedKeys) {
      for (final extra in [0, lockMask, mod2Mask, lockMask | mod2Mask]) {
        xUngrabKey(_display, tab, modifiers | extra, _root);
      }
    }
    _grabbedKeys.clear();
    _onShortcut = null;
    xSync(_display, 0);
  }

  @override
  bool grabKeyboard() {
    _keyboardHeld = xGrabKeyboard(
            _display, _root, 1, grabModeAsync, grabModeAsync, 0) ==
        0;
    return _keyboardHeld;
  }

  @override
  void releaseKeyboard() {
    if (!_keyboardHeld) return;
    xUngrabKeyboard(_display, 0);
    xFlush(_display);
    _keyboardHeld = false;
  }

  // -- event pump -------------------------------------------------------------

  void _drain() {
    while (xPending(_display) > 0) {
      xNextEvent(_display, _eventBuffer);
      final type = _eventBuffer.cast<Int32>().value;

      switch (type) {
        case keyPress:
          _onKeyPress(_eventBuffer.cast<XKeyEvent>().ref);
        case keyRelease:
          _onKeyRelease(_eventBuffer.cast<XKeyEvent>().ref);
        case propertyNotify:
          final property = _eventBuffer.cast<XPropertyEvent>().ref;
          if (property.atom == _atom('_NET_ACTIVE_WINDOW') && !_keyboardHeld) {
            _noteActivation();
          }
      }
    }
  }

  void _onKeyPress(XKeyEvent key) {
    final backwards = key.state & shiftMask != 0;
    final symbol = xKeycodeToKeysym(_display, key.keycode, backwards ? 1 : 0);

    if (symbol == xkTab || symbol == xkIsoLeftTab) {
      if (_keyboardHeld) {
        _keys.add(backwards ? SwitcherKey.previous : SwitcherKey.next);
      } else {
        _onShortcut?.call(backwards: backwards);
      }
      return;
    }
    if (!_keyboardHeld) return;

    switch (symbol) {
      case xkEscape:
        _keys.add(SwitcherKey.cancel);
      case xkRight:
      case xkDown:
        _keys.add(SwitcherKey.next);
      case xkLeft:
      case xkUp:
        _keys.add(SwitcherKey.previous);
      case xkW:
      case xkQ:
      case xkF4:
        _keys.add(SwitcherKey.closeWindow);
    }
  }

  void _onKeyRelease(XKeyEvent key) {
    if (!_keyboardHeld) return;
    final symbol = xKeycodeToKeysym(_display, key.keycode, 0);
    if (symbol == xkAltL || symbol == xkAltR) _released.add(null);
  }

  @override
  void dispose() {
    _pump?.cancel();
    releaseKeyboard();
    releaseSwitcherShortcut();
    calloc.free(_eventBuffer);
    _keys.close();
    _released.close();
  }
}
