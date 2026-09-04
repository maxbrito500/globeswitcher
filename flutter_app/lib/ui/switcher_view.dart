// Copyright 2026 Max Brito
// SPDX-License-Identifier: Apache-2.0

/// Drawing the switcher: the dimmed desktop, the ring of windows, the globe.
library;

import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../model/settings.dart';
import 'globe_shader.dart';
import 'ring.dart';

/// The application icon badged on a thumbnail, relative to the tile's height.
const double badgeFraction = 0.34;

class SwitcherTile {
  const SwitcherTile({required this.title, this.thumbnail, this.icon});

  final String title;
  final ui.Image? thumbnail;
  final ui.Image? icon;
}

class SwitcherPainter extends CustomPainter {
  SwitcherPainter({
    required this.backdrop,
    required this.tiles,
    required this.rotation,
    required this.meridian,
    required this.selected,
    required this.globe,
    required this.when,
    required this.settings,
  });

  final ui.Image? backdrop;
  final List<SwitcherTile> tiles;
  final double rotation;
  final double meridian;
  final int selected;
  final GlobeShader globe;
  final DateTime when;
  final SwitcherSettings settings;

  @override
  void paint(Canvas canvas, Size size) {
    _paintBackdrop(canvas, size);
    if (tiles.isEmpty) return;

    final layout = RingLayout(size, tiles.length, settings.ringConfig);
    final beads = layout.beads(rotation);

    // Far half, then the globe, then the near half: the globe is opaque
    // inside its disc, so a window crossing the limb is cut at the
    // silhouette without anyone having to test for it.
    for (final bead in beads) {
      if (bead.depth < 0) _paintBead(canvas, layout, bead);
    }
    _paintGlobe(canvas, layout);
    for (final bead in beads) {
      if (bead.depth >= 0) _paintBead(canvas, layout, bead);
    }

    _paintTitle(canvas, layout);
  }

  void _paintBackdrop(Canvas canvas, Size size) {
    final area = Offset.zero & size;
    if (backdrop != null) {
      canvas.drawImageRect(
          backdrop!,
          Rect.fromLTWH(
              0, 0, backdrop!.width.toDouble(), backdrop!.height.toDouble()),
          area,
          Paint());
      canvas.drawRect(
          area,
          Paint()
            ..color = Colors.black.withValues(alpha: 1 - settings.backdropDim));
    } else {
      canvas.drawRect(area, Paint()..color = const Color(0xFF0B0D13));
    }
  }

  void _paintGlobe(Canvas canvas, RingLayout layout) {
    final rect = layout.globeRect;
    final shader = globe.shaderFor(
      rect: rect,
      rotation: rotation + meridian,
      when: when,
      tilt: settings.viewTiltRadians,
      nightAmbient: settings.nightAmbient,
    );
    canvas.drawRect(rect, Paint()..shader = shader);
  }

  void _paintBead(Canvas canvas, RingLayout layout, Bead bead) {
    final tile = tiles[bead.index];
    final image = tile.thumbnail ?? tile.icon;
    if (image == null) return;

    // Keep the window's own shape: half of recognising it at a glance.
    final scale = math.min(
        bead.size / image.width.toDouble(), bead.size / image.height.toDouble());
    final width = image.width * scale;
    final height = image.height * scale;
    final rect = Rect.fromCenter(
        center: bead.centre, width: width, height: height);
    final radius = Radius.circular(math.max(4, math.min(width, height) * 0.09));
    final rounded = RRect.fromRectAndRadius(rect, radius);

    if (bead.index == selected) {
      canvas.drawRRect(
          rounded.inflate(bead.size * 0.06),
          Paint()
            ..color = const Color(0xFF7AB4FF).withValues(alpha: 0.35)
            ..maskFilter = MaskFilter.blur(BlurStyle.normal, bead.size * 0.10));
    }

    final paint = Paint()
      ..filterQuality = FilterQuality.medium
      ..color = Colors.white.withValues(alpha: bead.opacity);

    canvas.save();
    canvas.clipRRect(rounded);
    canvas.drawImageRect(
        image,
        Rect.fromLTWH(0, 0, image.width.toDouble(), image.height.toDouble()),
        rect,
        paint);
    canvas.restore();

    if (bead.index == selected) {
      canvas.drawRRect(
          rounded,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 3
            ..color = Colors.white.withValues(alpha: 0.94));
    }

    if (tile.thumbnail != null && tile.icon != null) {
      final badge = bead.size * badgeFraction;
      final at = Rect.fromLTWH(
          rect.right - badge - 3, rect.bottom - badge - 3, badge, badge);
      canvas.drawImageRect(
          tile.icon!,
          Rect.fromLTWH(0, 0, tile.icon!.width.toDouble(),
              tile.icon!.height.toDouble()),
          at,
          paint);
    }
  }

  void _paintTitle(Canvas canvas, RingLayout layout) {
    if (!settings.showTitles) return;
    if (selected < 0 || selected >= tiles.length) return;
    final title = tiles[selected].title;
    if (title.isEmpty) return;

    final painter = TextPainter(
      text: TextSpan(
        text: title.length <= 90 ? title : '${title.substring(0, 89)}…',
        style: TextStyle(
          color: Colors.white,
          fontSize: math.max(15, layout.globeDiameter * 0.062),
          fontWeight: FontWeight.bold,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();

    final plate = RRect.fromRectAndRadius(
        Rect.fromLTWH(layout.centre.dx - painter.width / 2 - 18,
            layout.titleTop - 10, painter.width + 36, painter.height + 20),
        const Radius.circular(11));
    canvas.drawRRect(
        plate, Paint()..color = Colors.black.withValues(alpha: 0.75));
    painter.paint(canvas,
        Offset(layout.centre.dx - painter.width / 2, layout.titleTop));
  }

  @override
  bool shouldRepaint(SwitcherPainter old) =>
      old.rotation != rotation ||
      old.selected != selected ||
      old.tiles != tiles ||
      old.backdrop != backdrop ||
      old.settings != settings;
}
