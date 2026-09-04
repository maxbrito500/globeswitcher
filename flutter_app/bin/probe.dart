// SPDX-License-Identifier: Apache-2.0
//
// Checks the X11 backend against the running server, without any UI.
// Run with: dart run bin/probe.dart

import 'dart:io';

import 'package:globeswitcher/backend/x11/x11_backend.dart';

void main() {
  final backend = X11Backend.open();
  if (backend == null) {
    stderr.writeln('no X display');
    exit(1);
  }

  stdout.writeln('screen ${backend.screenWidth}x${backend.screenHeight}');

  final watch = Stopwatch()..start();
  final windows = backend.listWindows();
  stdout.writeln('listWindows: ${windows.length} in ${watch.elapsedMilliseconds} ms');
  for (final window in windows) {
    final icon = window.iconRgba == null
        ? 'no icon'
        : 'icon ${window.iconWidth}x${window.iconHeight}';
    final title =
        window.title.length > 40 ? '${window.title.substring(0, 40)}…' : window.title;
    stdout.writeln('  0x${window.id.toRadixString(16)}  $icon  "$title"');
  }

  if (windows.isNotEmpty) {
    watch.reset();
    final shot = backend.captureWindow(windows.first.id);
    stdout.writeln(shot == null
        ? 'captureWindow: failed'
        : 'captureWindow: ${shot.width}x${shot.height} in ${watch.elapsedMilliseconds} ms');
  }

  watch.reset();
  final screen = backend.captureScreen();
  stdout.writeln(screen == null
      ? 'captureScreen: failed'
      : 'captureScreen: ${screen.width}x${screen.height} in ${watch.elapsedMilliseconds} ms');

  backend.dispose();
  exit(0);
}
