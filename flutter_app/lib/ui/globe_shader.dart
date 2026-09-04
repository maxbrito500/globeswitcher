// Copyright 2026 Max Brito
// SPDX-License-Identifier: Apache-2.0

/// Loading and feeding the globe's fragment shader.
library;

import 'dart:ui' as ui;

import 'package:flutter/services.dart';

import '../model/solar.dart';

/// Solar elevations bounding the twilight blend, in radians.
const double twilightLow = -12.0 * 3.14159265358979 / 180.0;
const double twilightHigh = 6.0 * 3.14159265358979 / 180.0;

class GlobeShader {
  GlobeShader._(this._program, this.dayTexture, this.nightTexture);

  static Future<GlobeShader> load() async {
    final program = await ui.FragmentProgram.fromAsset('shaders/globe.frag');
    final day = await _loadImage('assets/earth_day.jpg');
    final night = await _loadImage('assets/earth_night.jpg');
    return GlobeShader._(program, day, night);
  }

  static Future<ui.Image> _loadImage(String asset) async {
    final data = await rootBundle.load(asset);
    final codec = await ui.instantiateImageCodec(data.buffer.asUint8List());
    final frame = await codec.getNextFrame();
    return frame.image;
  }

  final ui.FragmentProgram _program;
  final ui.Image dayTexture;
  final ui.Image nightTexture;

  /// A shader ready to paint the globe into `rect`, lit for `when`.
  ui.FragmentShader shaderFor({
    required ui.Rect rect,
    required double rotation,
    required DateTime when,
    required double tilt,
    required double nightAmbient,
    double opacity = 1.0,
  }) {
    final sun = subsolarPoint(when);
    final shader = _program.fragmentShader();

    var slot = 0;
    void setFloat(double value) => shader.setFloat(slot++, value);

    setFloat(rect.left);
    setFloat(rect.top);
    setFloat(rect.width);
    setFloat(rect.height);
    setFloat(rotation);
    setFloat(tilt);
    setFloat(sun.latitude);
    setFloat(sun.longitude);
    setFloat(twilightLow);
    setFloat(twilightHigh);
    setFloat(nightAmbient);
    setFloat(opacity);

    shader.setImageSampler(0, dayTexture);
    shader.setImageSampler(1, nightTexture);
    return shader;
  }
}
