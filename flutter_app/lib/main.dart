// Copyright 2026 Max Brito
// SPDX-License-Identifier: Apache-2.0

/// globeswitcher: Alt+Tab as a rotating Earth.
library;

import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'backend/window_backend.dart';
import 'backend/x11/x11_backend.dart';
import 'model/solar.dart';
import 'ui/globe_shader.dart';
import 'ui/ring.dart';
import 'ui/switcher_view.dart';

/// How long the globe takes to roll one window round to the front, and the cap
/// for the long wrap from the last window back to the first.
const Duration rollDuration = Duration(milliseconds: 260);
const Duration rollDurationMax = Duration(milliseconds: 620);

/// Thumbnails are decoded at this size; bigger than they are ever drawn, small
/// enough that a screenful of windows does not become a screenful of textures.
const int thumbnailLongEdge = 640;

/// Asks the native runner to put the overlay on screen, or take it away.
const MethodChannel _windowChannel = MethodChannel('globeswitcher/window');

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final globe = await GlobeShader.load();
  runApp(GlobeSwitcherApp(globe: globe));
}

class GlobeSwitcherApp extends StatelessWidget {
  const GlobeSwitcherApp({super.key, required this.globe});

  final GlobeShader globe;

  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        home: Scaffold(
          backgroundColor: Colors.transparent,
          body: SwitcherOverlay(globe: globe),
        ),
      );
}

class SwitcherOverlay extends StatefulWidget {
  const SwitcherOverlay({super.key, required this.globe});

  final GlobeShader globe;

  @override
  State<SwitcherOverlay> createState() => _SwitcherOverlayState();
}

class _SwitcherOverlayState extends State<SwitcherOverlay>
    with SingleTickerProviderStateMixin {
  WindowBackend? _backend;
  StreamSubscription<SwitcherKey>? _keySubscription;
  StreamSubscription<void>? _releaseSubscription;

  late final AnimationController _roll = AnimationController(vsync: this)
    ..addListener(() => setState(() {}));

  List<WindowInfo> _windows = const [];
  List<SwitcherTile> _tiles = const [];
  ui.Image? _backdrop;

  bool _open = false;
  int _selected = 0;
  double _rotation = 0;
  double _rollFrom = 0;
  double _rollTo = 0;
  double _meridian = localMeridian();

  @override
  void initState() {
    super.initState();
    final backend = X11Backend.open();
    if (backend == null) {
      debugPrint('globeswitcher: no X display; nothing to switch');
      return;
    }
    _backend = backend;
    backend.grabSwitcherShortcut(({required bool backwards}) {
      unawaited(_show(backwards: backwards));
    });
    _keySubscription = backend.keys.listen(_onKey);
    _releaseSubscription = backend.modifiersReleased.listen((_) => _accept());
  }

  // -- opening and closing ----------------------------------------------------

  Future<void> _show({required bool backwards}) async {
    final backend = _backend;
    if (backend == null || _open) {
      if (_open) _step(backwards ? -1 : 1);
      return;
    }

    final windows = backend.listWindows();
    if (windows.isEmpty) return;

    final screen = backend.captureScreen();
    final backdrop = screen == null ? null : await _decode(screen);

    final tiles = <SwitcherTile>[];
    for (final window in windows) {
      final shot = backend.captureWindow(window.id);
      tiles.add(SwitcherTile(
        title: window.title,
        thumbnail: shot == null ? null : await _decode(shot, longEdge: thumbnailLongEdge),
        icon: window.iconRgba == null
            ? null
            : await _decode(WindowShot(
                window.iconRgba!, window.iconWidth, window.iconHeight)),
      ));
    }

    setState(() {
      _windows = windows;
      _tiles = tiles;
      _backdrop = backdrop;
      _meridian = localMeridian();
      _open = true;
      _selected = 0;
      _rotation = 0;
    });

    await _windowChannel.invokeMethod<void>('show');
    if (!backend.grabKeyboard()) {
      await _hide();
      return;
    }
    _step(backwards ? -1 : 1);
  }

  Future<void> _hide() async {
    _backend?.releaseKeyboard();
    _roll.stop();
    setState(() {
      _open = false;
      _tiles = const [];
      _windows = const [];
      _backdrop = null;
    });
    await _windowChannel.invokeMethod<void>('hide');
  }

  void _accept() {
    if (!_open) return;
    final chosen = _selected < _windows.length ? _windows[_selected] : null;
    unawaited(_hide().then((_) {
      if (chosen != null) _backend?.activateWindow(chosen.id);
    }));
  }

  void _onKey(SwitcherKey key) {
    if (!_open) return;
    switch (key) {
      case SwitcherKey.next:
        _step(1);
      case SwitcherKey.previous:
        _step(-1);
      case SwitcherKey.cancel:
        unawaited(_hide());
      case SwitcherKey.accept:
        _accept();
      case SwitcherKey.closeWindow:
        _closeSelected();
    }
  }

  void _closeSelected() {
    if (_selected >= _windows.length) return;
    _backend?.closeWindow(_windows[_selected].id);
    final windows = List<WindowInfo>.from(_windows)..removeAt(_selected);
    final tiles = List<SwitcherTile>.from(_tiles)..removeAt(_selected);
    if (windows.isEmpty) {
      unawaited(_hide());
      return;
    }
    setState(() {
      _windows = windows;
      _tiles = tiles;
      _selected = _selected.clamp(0, windows.length - 1);
      _rotation = RingLayout(_lastSize, windows.length).longitude(_selected);
    });
  }

  // -- rolling ----------------------------------------------------------------

  Size _lastSize = const Size(1920, 1080);

  void _step(int delta) {
    if (_windows.length < 2) return;
    final count = _windows.length;
    final layout = RingLayout(_lastSize, count);

    setState(() => _selected = (_selected + delta) % count);

    // Retarget from wherever the globe is now, so a Tab pressed mid-roll stays
    // smooth instead of queueing up behind the last one.
    final target = layout.longitude(_selected);
    _rollFrom = _rotation;
    _rollTo = _rotation + shortestTurn(target - _rotation);

    // Wrapping from the last window back to the first travels the whole band,
    // so give it proportionally longer, up to a limit.
    final steps = ((_rollTo - _rollFrom).abs() / layout.step).clamp(1.0, 100.0);
    final millis = (rollDuration.inMilliseconds * math.sqrt(steps))
        .clamp(rollDuration.inMilliseconds, rollDurationMax.inMilliseconds)
        .round();

    _roll
      ..stop()
      ..duration = Duration(milliseconds: millis)
      ..reset()
      ..forward();
  }

  double get _animatedRotation {
    if (!_roll.isAnimating && _roll.value == 0) return _rotation;
    final eased = Curves.easeOutCubic.transform(_roll.value);
    final value = _rollFrom + (_rollTo - _rollFrom) * eased;
    if (!_roll.isAnimating) _rotation = _rollTo;
    return value;
  }

  // -- plumbing ---------------------------------------------------------------

  Future<ui.Image> _decode(WindowShot shot, {int? longEdge}) {
    final completer = Completer<ui.Image>();
    int? targetWidth;
    int? targetHeight;
    if (longEdge != null && (shot.width > longEdge || shot.height > longEdge)) {
      final scale = longEdge / (shot.width > shot.height ? shot.width : shot.height);
      targetWidth = (shot.width * scale).round();
      targetHeight = (shot.height * scale).round();
    }
    ui.decodeImageFromPixels(
      shot.rgba,
      shot.width,
      shot.height,
      ui.PixelFormat.rgba8888,
      completer.complete,
      targetWidth: targetWidth,
      targetHeight: targetHeight,
    );
    return completer.future;
  }

  @override
  void dispose() {
    _keySubscription?.cancel();
    _releaseSubscription?.cancel();
    _roll.dispose();
    _backend?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_open) return const SizedBox.expand();

    return LayoutBuilder(builder: (context, constraints) {
      _lastSize = Size(constraints.maxWidth, constraints.maxHeight);
      return CustomPaint(
        size: _lastSize,
        painter: SwitcherPainter(
          backdrop: _backdrop,
          tiles: _tiles,
          rotation: _animatedRotation,
          meridian: _meridian,
          selected: _selected,
          globe: widget.globe,
          when: DateTime.now(),
        ),
      );
    });
  }
}
