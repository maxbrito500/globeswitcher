// Copyright 2026 Max Brito
// SPDX-License-Identifier: Apache-2.0

/// Where the globe sits, and where each window rides on the ring around it.
///
/// The windows are beads on a ring around the equator and turn with the globe,
/// so a window's place on screen is a projection of a point in space rather
/// than a position on a flat circle.
library;

import 'dart:math' as math;
import 'dart:ui';

/// Layout, as fractions of the screen's short axis.
const double defaultGlobeFraction = 0.50;
const double defaultItemFraction = 0.32;
const double itemMin = 185;
const double itemMax = 420;

/// The ring the windows ride on, in globe radii.
const double defaultOrbitRadius = 2.40;

/// How far the ring floats above the equatorial plane. A ring lying exactly on
/// the equator projects far below the globe's centre, because the camera tilt
/// multiplies the offset by the ring's radius rather than the globe's, and the
/// windows end up sweeping past the south pole.
const double defaultOrbitLift = 0.765;

/// Camera lift above the equator, shared with the globe shader so the beads
/// and the coastlines agree about which way is up.
const double defaultViewTilt = 0.42;

/// Fixed spacing, so a handful of windows sit together as a band in front of
/// you instead of being flung out to the cardinal points. Only around twenty
/// windows does the ring close and wrap right around the world.
const double defaultAngularStep = 22.0 * math.pi / 180.0;

const double depthScale = 0.18;
const double backOpacity = 0.55;

/// How much bigger the window at the front is than its neighbours: the size
/// difference is what says "this one" before the highlight is even noticed.
const double frontScale = 0.20;

/// The dials that decide how the ring looks. Defaults are the constants
/// above; the settings panel hands in the user's own.
class RingConfig {
  const RingConfig({
    this.globeFraction = defaultGlobeFraction,
    this.itemFraction = defaultItemFraction,
    this.orbitRadius = defaultOrbitRadius,
    this.orbitLift = defaultOrbitLift,
    this.viewTilt = defaultViewTilt,
    this.angularStep = defaultAngularStep,
  });

  final double globeFraction;
  final double itemFraction;
  final double orbitRadius;
  final double orbitLift;
  final double viewTilt;
  final double angularStep;
}

/// One window, placed in space at a given rotation.
class Bead {
  const Bead(this.index, this.centre, this.depth, this.size, this.opacity);

  final int index;
  final Offset centre;

  /// Positive towards the viewer.
  final double depth;

  /// The tile's box; a thumbnail keeps its own shape inside it.
  final double size;
  final double opacity;
}

class RingLayout {
  RingLayout(this.size, int count, [this.config = const RingConfig()])
      : count = count < 1 ? 1 : count {
    final short = math.min(size.width, size.height);
    centre = Offset(size.width / 2, size.height / 2);
    globeDiameter = short * config.globeFraction;
    globeRadius = globeDiameter / 2;

    // A crowded ring needs smaller tiles, or they smear into each other at the
    // limbs where the spacing foreshortens.
    final crowding = this.count <= 8 ? 1.0 : math.max(0.62, 8.0 / this.count);
    itemSize = math.min(
        itemMax, math.max(itemMin, short * config.itemFraction * crowding));
  }

  final Size size;
  final int count;
  final RingConfig config;

  late final Offset centre;
  late final double globeDiameter;
  late final double globeRadius;
  late final double itemSize;

  /// Angle between neighbouring windows, never more than a full turn.
  double get step => math.min(config.angularStep, 2 * math.pi / count);

  /// How far round the globe the windows reach, first to last.
  double get span => math.min((count - 1) * step, math.pi);

  /// The longitude a window is pinned to.
  double longitude(int index) => index * step;

  Rect get globeRect => Rect.fromCenter(
      center: centre, width: globeDiameter, height: globeDiameter);

  /// Every window's place on screen, furthest away first, so painting them in
  /// order with the globe in the middle hides the far side behind it.
  List<Bead> beads(double rotation) {
    final cosTilt = math.cos(config.viewTilt);
    final sinTilt = math.sin(config.viewTilt);

    final result = <Bead>[];
    for (var index = 0; index < count; index++) {
      final lon = longitude(index) - rotation;
      final mx = config.orbitRadius * math.sin(lon);
      final mz = config.orbitRadius * math.cos(lon);

      // The same camera as the globe, so the near side of the ring hangs
      // below the centre; the lift raises the whole ellipse.
      final ny = cosTilt * config.orbitLift - sinTilt * mz;
      final nz = sinTilt * config.orbitLift + cosTilt * mz;

      // Blended in by how close the window is to the front, so it swells as
      // it arrives instead of snapping the moment the selection changes.
      final emphasis = (1.0 - shortestTurn(lon).abs() / step).clamp(0.0, 1.0);

      result.add(Bead(
        index,
        Offset(centre.dx + mx * globeRadius, centre.dy - ny * globeRadius),
        nz,
        itemSize *
            (1.0 + depthScale * nz / config.orbitRadius) *
            (1.0 + frontScale * emphasis),
        nz >= 0 ? 1.0 : backOpacity,
      ));
    }

    result.sort((a, b) => a.depth.compareTo(b.depth));
    return result;
  }

  /// The window under a point, nearest first so a tile in front wins over the
  /// one it overlaps. [extent] gives each tile's drawn box from its bead.
  Bead? hitTest(Offset point, double rotation, Rect Function(Bead) extent) {
    for (final bead in beads(rotation).reversed) {
      if (extent(bead).contains(point)) return bead;
    }
    return null;
  }

  /// Where the title plate sits: below the globe and below the ring.
  double get titleTop {
    final rise = (config.orbitRadius * math.sin(config.viewTilt) -
            config.orbitLift * math.cos(config.viewTilt)) *
        globeRadius;
    // The front tile is the nearest and the emphasised one, so it is the
    // largest on the ring; the plate has to clear it.
    final nearest = math.sin(config.viewTilt) * config.orbitLift +
        math.cos(config.viewTilt) * config.orbitRadius;
    final front = itemSize *
        (1.0 + depthScale * nearest / config.orbitRadius) *
        (1.0 + frontScale);
    return centre.dy + math.max(globeRadius, rise + front * 0.5) + 16;
  }
}

/// Fold an angle difference into the shorter way round the circle.
double shortestTurn(double delta) =>
    (delta + math.pi) % (2 * math.pi) - math.pi;
