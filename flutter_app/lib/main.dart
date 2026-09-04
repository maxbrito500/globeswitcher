// Copyright 2026 Max Brito
// SPDX-License-Identifier: Apache-2.0

/// globeswitcher: Alt+Tab as a rotating Earth.
library;

import 'dart:async';
import 'dart:io';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tray_manager/tray_manager.dart';

import 'backend/window_backend.dart';
import 'backend/x11/x11_backend.dart';
import 'model/settings.dart';
import 'model/solar.dart';
import 'ui/globe_shader.dart';
import 'ui/ring.dart';
import 'ui/settings_page.dart';
import 'ui/switcher_view.dart';

/// The cap on a long roll: wrapping from the last window back to the first
/// travels the whole band, and should read as a turn rather than a jump.
const Duration rollDurationMax = Duration(milliseconds: 620);

/// Thumbnails are decoded at this size: bigger than they are ever drawn, small
/// enough that a screenful of windows does not become a screenful of textures.
const int thumbnailLongEdge = 640;

/// Asks the native runner to be an overlay, a settings window, or nothing.
const MethodChannel _windowChannel = MethodChannel('globeswitcher/window');

enum AppMode { hidden, overlay, settings }

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final settings = SwitcherSettings();
  await settings.load();
  final globe = await GlobeShader.load();
  runApp(GlobeSwitcherApp(globe: globe, settings: settings));
}

class GlobeSwitcherApp extends StatelessWidget {
  const GlobeSwitcherApp(
      {super.key, required this.globe, required this.settings});

  final GlobeShader globe;
  final SwitcherSettings settings;

  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'globeswitcher',
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
              seedColor: const Color(0xFF2E6FD8), brightness: Brightness.dark),
          useMaterial3: true,
        ),
        home: SwitcherHome(globe: globe, settings: settings),
      );
}

class SwitcherHome extends StatefulWidget {
  const SwitcherHome({super.key, required this.globe, required this.settings});

  final GlobeShader globe;
  final SwitcherSettings settings;

  @override
  State<SwitcherHome> createState() => _SwitcherHomeState();
}

class _SwitcherHomeState extends State<SwitcherHome>
    with SingleTickerProviderStateMixin, TrayListener {
  X11Backend? _backend;
  StreamSubscription<SwitcherKey>? _keySubscription;
  StreamSubscription<void>? _releaseSubscription;

  late final AnimationController _roll = AnimationController(vsync: this)
    ..addListener(() => setState(() {}));

  List<WindowInfo> _windows = const [];
  List<SwitcherTile> _tiles = const [];
  ui.Image? _backdrop;

  AppMode _mode = AppMode.hidden;
  int _selected = 0;
  double _rotation = 0;
  double _rollFrom = 0;
  double _rollTo = 0;
  double _meridian = localMeridian();
  Size _lastSize = const Size(1920, 1080);

  SwitcherSettings get _settings => widget.settings;

  @override
  void initState() {
    super.initState();
    _settings.addListener(_onSettingsChanged);
    _setUpTray();

    final backend = X11Backend.open();
    if (backend == null) {
      debugPrint('globeswitcher: no X display; nothing to switch');
      return;
    }
    _backend = backend;
    backend.currentDesktopOnly = _settings.currentWorkspaceOnly;
    backend.grabSwitcherShortcut(({required bool backwards}) {
      unawaited(_open(backwards: backwards));
    });
    _keySubscription = backend.keys.listen(_onKey);
    _releaseSubscription = backend.modifiersReleased.listen((_) => _accept());
  }

  void _onSettingsChanged() {
    _backend?.currentDesktopOnly = _settings.currentWorkspaceOnly;
    if (mounted) setState(() {});
  }

  // -- tray -------------------------------------------------------------------

  Future<void> _setUpTray() async {
    // The bundle keeps its assets next to the executable, and the tray wants a
    // path on disk rather than an asset key.
    final root = File(Platform.resolvedExecutable).parent.path;
    final icon = '$root/data/flutter_assets/assets/tray_globe.png';

    trayManager.addListener(this);
    try {
      await trayManager.setIcon(icon);
      await trayManager.setContextMenu(Menu(items: [
        MenuItem(key: 'settings', label: 'Settings…'),
        MenuItem.separator(),
        MenuItem(key: 'quit', label: 'Quit'),
      ]));
    } catch (error) {
      debugPrint('globeswitcher: no tray icon ($error)');
    }

    // Not every platform implements a tooltip, and it is not worth losing the
    // icon over.
    try {
      await trayManager.setToolTip('globeswitcher');
    } catch (_) {}
  }

  @override
  void onTrayIconMouseDown() => unawaited(_showSettings());

  @override
  void onTrayIconRightMouseDown() => unawaited(trayManager.popUpContextMenu());

  @override
  void onTrayMenuItemClick(MenuItem menuItem) {
    switch (menuItem.key) {
      case 'settings':
        unawaited(_showSettings());
      case 'quit':
        unawaited(_quit());
    }
  }

  Future<void> _quit() async {
    await trayManager.destroy();
    _backend?.dispose();
    exit(0);
  }

  // -- window modes -----------------------------------------------------------

  Future<void> _setMode(AppMode mode) async {
    if (mounted) setState(() => _mode = mode);
    await _windowChannel.invokeMethod<void>('setMode', mode.name);
  }

  Future<void> _showSettings() async {
    if (_mode == AppMode.overlay) return;
    await _setMode(AppMode.settings);
  }

  Future<void> _hideSettings() async => _setMode(AppMode.hidden);

  // -- the switcher -----------------------------------------------------------

  Future<void> _open({required bool backwards}) async {
    final backend = _backend;
    if (backend == null) return;
    if (_mode == AppMode.overlay) {
      _step(backwards ? -1 : 1);
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
        thumbnail:
            shot == null ? null : await _decode(shot, longEdge: thumbnailLongEdge),
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
      _selected = 0;
      _rotation = 0;
    });

    await _setMode(AppMode.overlay);
    if (!backend.grabKeyboard()) {
      await _close();
      return;
    }
    _step(backwards ? -1 : 1);
  }

  Future<void> _close() async {
    _backend?.releaseKeyboard();
    _roll.stop();
    setState(() {
      _tiles = const [];
      _windows = const [];
      _backdrop = null;
    });
    await _setMode(AppMode.hidden);
  }

  void _accept() {
    if (_mode != AppMode.overlay) return;
    final chosen = _selected < _windows.length ? _windows[_selected] : null;
    unawaited(_close().then((_) {
      if (chosen != null) _backend?.activateWindow(chosen.id);
    }));
  }

  void _onKey(SwitcherKey key) {
    if (_mode != AppMode.overlay) return;
    switch (key) {
      case SwitcherKey.next:
        _step(1);
      case SwitcherKey.previous:
        _step(-1);
      case SwitcherKey.cancel:
        unawaited(_close());
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
      unawaited(_close());
      return;
    }
    setState(() {
      _windows = windows;
      _tiles = tiles;
      _selected = _selected.clamp(0, windows.length - 1);
      _rotation = RingLayout(_lastSize, windows.length, _settings.ringConfig)
          .longitude(_selected);
    });
  }

  // -- rolling ----------------------------------------------------------------

  void _step(int delta) {
    if (_windows.length < 2) return;
    final layout =
        RingLayout(_lastSize, _windows.length, _settings.ringConfig);

    setState(() => _selected = (_selected + delta) % _windows.length);

    // Retarget from wherever the globe is now, so a Tab pressed mid-roll stays
    // smooth instead of queueing up behind the last one.
    _rollFrom = _rotation;
    _rollTo = _rotation +
        shortestTurn(layout.longitude(_selected) - _rotation);

    final steps = ((_rollTo - _rollFrom).abs() / layout.step).clamp(1.0, 100.0);
    final base = _settings.rollDuration.inMilliseconds;
    final millis = (base * math.sqrt(steps))
        .clamp(base.toDouble(), rollDurationMax.inMilliseconds.toDouble())
        .round();

    _roll
      ..stop()
      ..duration = Duration(milliseconds: millis)
      ..reset()
      ..forward();
  }

  double get _animatedRotation {
    if (!_roll.isAnimating && _roll.value == 0) return _rotation;
    final value = _rollFrom +
        (_rollTo - _rollFrom) * Curves.easeOutCubic.transform(_roll.value);
    if (!_roll.isAnimating) _rotation = _rollTo;
    return value;
  }

  // -- plumbing ---------------------------------------------------------------

  Future<ui.Image> _decode(WindowShot shot, {int? longEdge}) {
    final completer = Completer<ui.Image>();
    int? targetWidth;
    int? targetHeight;
    if (longEdge != null && (shot.width > longEdge || shot.height > longEdge)) {
      final scale =
          longEdge / (shot.width > shot.height ? shot.width : shot.height);
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
    trayManager.removeListener(this);
    _settings.removeListener(_onSettingsChanged);
    _keySubscription?.cancel();
    _releaseSubscription?.cancel();
    _roll.dispose();
    _backend?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    switch (_mode) {
      case AppMode.hidden:
        return const SizedBox.expand();
      case AppMode.settings:
        return SettingsPage(
            settings: _settings, onClose: () => unawaited(_hideSettings()));
      case AppMode.overlay:
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
              settings: _settings,
            ),
          );
        });
    }
  }
}
