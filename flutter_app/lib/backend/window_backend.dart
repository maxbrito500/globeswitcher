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

/// What the switcher needs from an operating system.
///
/// Flutter draws the same everywhere, but nothing about actually switching
/// windows is portable: listing them, picturing them, raising one, and taking
/// over Alt+Tab are different on every desktop. Everything platform-specific
/// lives behind this one interface, so adding Windows or macOS means writing
/// another implementation of it and nothing else.
library;

import 'dart:typed_data';

/// One switchable window.
class WindowInfo {
  WindowInfo({
    required this.id,
    required this.title,
    this.iconRgba,
    this.iconWidth = 0,
    this.iconHeight = 0,
  });

  /// Opaque to everything above the backend; an X window id here.
  final int id;
  final String title;

  /// The application icon as straight RGBA, if the window offers one.
  final Uint8List? iconRgba;
  final int iconWidth;
  final int iconHeight;
}

/// A picture of a window's contents, as straight RGBA.
class WindowShot {
  WindowShot(this.rgba, this.width, this.height);

  final Uint8List rgba;
  final int width;
  final int height;
}

/// What the user did while the switcher was open.
enum SwitcherKey { next, previous, first, last, cancel, accept, closeWindow }

abstract class WindowBackend {
  /// Whether this backend can run here at all.
  bool get isAvailable;

  /// Windows worth offering, most recently used first.
  List<WindowInfo> listWindows();

  /// A picture of a window's contents, or null if it cannot be had.
  WindowShot? captureWindow(int id);

  /// The whole screen, for the dimmed backdrop.
  WindowShot? captureScreen();

  /// Raise a window and give it the keyboard.
  void activateWindow(int id);

  /// Ask a window to close itself.
  void closeWindow(int id);

  /// Take over the switcher shortcut. The callback fires with `backwards`
  /// set when Shift was held.
  void grabSwitcherShortcut(void Function({required bool backwards}) onPress);

  void releaseSwitcherShortcut();

  /// Hold the keyboard while the switcher is on screen, so the keys reach us
  /// and releasing Alt is something we can see.
  bool grabKeyboard();

  void releaseKeyboard();

  /// Keys pressed while the keyboard is held.
  Stream<SwitcherKey> get keys;

  /// Fires when every modifier has been let go, which is the moment a
  /// hold-to-browse switcher commits to its selection.
  Stream<void> get modifiersReleased;

  /// Whether the shortcut's modifier (Alt) is down right now. Asked once the
  /// switcher is up: a quick tap can let go of Alt before the overlay has
  /// finished taking its pictures, and that release is never delivered.
  bool get shortcutModifierHeld;

  void dispose();
}
