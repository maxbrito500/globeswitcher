// Copyright 2026 Max Brito
// SPDX-License-Identifier: Apache-2.0

/// The tuning the settings panel writes and the switcher reads.
library;

import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../ui/ring.dart' as ring;

/// One adjustable number, with the range the panel offers and a word on what
/// moving it actually does.
class Tunable {
  const Tunable(this.key, this.label, this.help, this.min, this.max,
      this.defaultValue,
      {this.unit = ''});

  final String key;
  final String label;
  final String help;
  final double min;
  final double max;
  final double defaultValue;
  final String unit;
}

const List<Tunable> switcherTunables = [
  Tunable('globeFraction', 'Globe size',
      'How much of the screen the Earth takes up.', 0.25, 0.70, 0.50),
  Tunable('itemFraction', 'Window size',
      'How large each window preview is drawn.', 0.15, 0.50, 0.32),
  Tunable('orbitRadius', 'Ring width',
      'How far out the windows orbit, in globe radii.', 1.40, 3.40, 2.40,
      unit: '×'),
  Tunable(
      'orbitLift',
      'Ring height',
      'Raises the ring. Too low and the windows sweep past the south pole; '
          'too high and they ride over the globe.',
      0.0,
      1.60,
      0.765,
      unit: '×'),
  Tunable('viewTilt', 'Camera tilt',
      'How far above the equator you look from.', 10, 50, 24.06, unit: '°'),
  Tunable(
      'angularStep',
      'Window spacing',
      'Degrees between neighbouring windows. Smaller packs more in before '
          'the ring closes and wraps the world.',
      8,
      60,
      22,
      unit: '°'),
  Tunable('rollMillis', 'Roll time',
      'How long the globe takes to turn one window to the front.', 80, 600, 260,
      unit: 'ms'),
  Tunable('backdropDim', 'Desktop dimming',
      'How much of your desktop still shows behind the switcher.', 0.0, 1.0,
      0.34),
  Tunable(
      'nightAmbient',
      'Night brightness',
      'Daylight left in the dark half. At zero only city lights show and the '
          'night side nearly disappears.',
      0.0,
      0.45,
      0.14),
];

class SwitcherSettings extends ChangeNotifier {
  final Map<String, double> _values = {
    for (final tunable in switcherTunables) tunable.key: tunable.defaultValue
  };

  bool _currentWorkspaceOnly = true;
  bool _showTitles = true;

  double value(String key) =>
      _values[key] ?? _tunable(key).defaultValue;

  bool get currentWorkspaceOnly => _currentWorkspaceOnly;
  bool get showTitles => _showTitles;

  static Tunable _tunable(String key) =>
      switcherTunables.firstWhere((tunable) => tunable.key == key);

  /// The ring's own dials, with the angles converted from the degrees the
  /// panel shows into the radians the geometry wants.
  ring.RingConfig get ringConfig => ring.RingConfig(
        globeFraction: value('globeFraction'),
        itemFraction: value('itemFraction'),
        orbitRadius: value('orbitRadius'),
        orbitLift: value('orbitLift'),
        viewTilt: value('viewTilt') * math.pi / 180.0,
        angularStep: value('angularStep') * math.pi / 180.0,
      );

  Duration get rollDuration =>
      Duration(milliseconds: value('rollMillis').round());

  double get backdropDim => value('backdropDim');
  double get nightAmbient => value('nightAmbient');
  double get viewTiltRadians => value('viewTilt') * math.pi / 180.0;

  void set(String key, double newValue) {
    final tunable = _tunable(key);
    final clamped = newValue.clamp(tunable.min, tunable.max).toDouble();
    if (_values[key] == clamped) return;
    _values[key] = clamped;
    notifyListeners();
    unawaited(save());
  }

  void setCurrentWorkspaceOnly(bool value) {
    if (_currentWorkspaceOnly == value) return;
    _currentWorkspaceOnly = value;
    notifyListeners();
    unawaited(save());
  }

  void setShowTitles(bool value) {
    if (_showTitles == value) return;
    _showTitles = value;
    notifyListeners();
    unawaited(save());
  }

  void restoreDefaults() {
    for (final tunable in switcherTunables) {
      _values[tunable.key] = tunable.defaultValue;
    }
    _currentWorkspaceOnly = true;
    _showTitles = true;
    notifyListeners();
    unawaited(save());
  }

  Future<void> load() async {
    final store = await SharedPreferences.getInstance();
    for (final tunable in switcherTunables) {
      final stored = store.getDouble('switcher.${tunable.key}');
      if (stored != null) {
        _values[tunable.key] =
            stored.clamp(tunable.min, tunable.max).toDouble();
      }
    }
    _currentWorkspaceOnly = store.getBool('switcher.currentWorkspaceOnly') ?? true;
    _showTitles = store.getBool('switcher.showTitles') ?? true;
    notifyListeners();
  }

  Future<void> save() async {
    final store = await SharedPreferences.getInstance();
    for (final entry in _values.entries) {
      await store.setDouble('switcher.${entry.key}', entry.value);
    }
    await store.setBool('switcher.currentWorkspaceOnly', _currentWorkspaceOnly);
    await store.setBool('switcher.showTitles', _showTitles);
  }
}

// ignore_for_file: unused_element
/// Fire and forget, without the analyzer complaining.
void unawaited(Future<void> future) {}
