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
const double globeFraction = 0.50;
const double itemFraction = 0.32;
const double itemMin = 185;
const double itemMax = 420;

/// The ring the windows ride on, in globe radii.
const double orbitRadius = 2.40;

/// How far the ring floats above the equatorial plane. A ring lying exactly on
/// the equator projects far below the globe's centre, because the camera tilt
/// multiplies the offset by the ring's radius rather than the globe's, and the
/// windows end up sweeping past the south pole.
const double orbitLift = 0.765;

/// Camera lift above the equator, shared with the globe shader so the beads
/// and the coastlines agree about which way is up.
const double viewTilt = 0.42;

/// Fixed spacing, so a handful of windows sit together as a band in front of
/// you instead of being flung out to the cardinal points. Only around twenty
/// windows does the ring close and wrap right around the world.
const double angularStep = 22.0 * math.pi / 180.0;

const double depthScale = 0.18;
const double backOpacity = 0.55;

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
  RingLayout(this.size, int count) : count = count < 1 ? 1 : count {
    final short = math.min(size.width, size.height);
    centre = Offset(size.width / 2, size.height / 2);
    globeDiameter = short * globeFraction;
    globeRadius = globeDiameter / 2;

    // A crowded ring needs smaller tiles, or they smear into each other at the
    // limbs where the spacing foreshortens.
    final crowding = this.count <= 8 ? 1.0 : math.max(0.62, 8.0 / this.count);
    itemSize =
        math.min(itemMax, math.max(itemMin, short * itemFraction * crowding));
  }

  final Size size;
  final int count;

  late final Offset centre;
  late final double globeDiameter;
  late final double globeRadius;
  late final double itemSize;

  /// Angle between neighbouring windows, never more than a full turn.
  double get step => math.min(angularStep, 2 * math.pi / count);

  /// How far round the globe the windows reach, first to last.
  double get span => math.min((count - 1) * step, math.pi);

  /// The longitude a window is pinned to.
  double longitude(int index) => index * step;

  Rect get globeRect => Rect.fromCenter(
      center: centre, width: globeDiameter, height: globeDiameter);

  /// Every window's place on screen, furthest away first, so painting them in
  /// order with the globe in the middle hides the far side behind it.
  List<Bead> beads(double rotation) {
    final cosTilt = math.cos(viewTilt);
    final sinTilt = math.sin(viewTilt);

    final result = <Bead>[];
    for (var index = 0; index < count; index++) {
      final lon = longitude(index) - rotation;
      final mx = orbitRadius * math.sin(lon);
      final mz = orbitRadius * math.cos(lon);

      // The same camera as the globe, so the near side of the ring hangs
      // below the centre; the lift raises the whole ellipse.
      final ny = cosTilt * orbitLift - sinTilt * mz;
      final nz = sinTilt * orbitLift + cosTilt * mz;

      result.add(Bead(
        index,
        Offset(centre.dx + mx * globeRadius, centre.dy - ny * globeRadius),
        nz,
        itemSize * (1.0 + depthScale * nz / orbitRadius),
        nz >= 0 ? 1.0 : backOpacity,
      ));
    }

    result.sort((a, b) => a.depth.compareTo(b.depth));
    return result;
  }

  /// Where the title plate sits: below the globe and below the ring.
  double get titleTop {
    final rise =
        (orbitRadius * math.sin(viewTilt) - orbitLift * math.cos(viewTilt)) *
            globeRadius;
    return centre.dy + math.max(globeRadius, rise + itemSize * 0.60) + 16;
  }
}

/// Fold an angle difference into the shorter way round the circle.
double shortestTurn(double delta) =>
    (delta + math.pi) % (2 * math.pi) - math.pi;
