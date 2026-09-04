// SPDX-License-Identifier: Apache-2.0

import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter_test/flutter_test.dart';
import 'package:globeswitcher/model/solar.dart';
import 'package:globeswitcher/ui/ring.dart';

void main() {
  group('solar position', () {
    test('declination follows the seasons', () {
      double declinationOn(String iso) =>
          subsolarPoint(DateTime.parse(iso)).latitude * 180 / math.pi;

      expect(declinationOn('2026-06-21T12:00:00Z'), closeTo(23.44, 0.1));
      expect(declinationOn('2026-12-21T12:00:00Z'), closeTo(-23.44, 0.1));
      expect(declinationOn('2026-03-20T12:00:00Z'), closeTo(0.0, 0.6));
    });

    test('the sun is over the prime meridian at noon UTC', () {
      final longitude =
          subsolarPoint(DateTime.parse('2026-09-04T12:00:00Z')).longitude *
              180 /
              math.pi;
      expect(longitude, closeTo(0.0, 1.0));
    });

    test('and over the date line at midnight', () {
      final longitude =
          subsolarPoint(DateTime.parse('2026-09-04T00:00:00Z')).longitude.abs() *
              180 /
              math.pi;
      expect(longitude, closeTo(180.0, 1.0));
    });
  });

  group('ring layout', () {
    const size = Size(1920, 1080);

    test('a few windows sit together, many wrap the world', () {
      expect(RingLayout(size, 4).span * 180 / math.pi, closeTo(66, 0.1));
      expect(RingLayout(size, 20).span, closeTo(math.pi, 0.001));
    });

    test('the selected window ends up at the front', () {
      final layout = RingLayout(size, 6);
      final beads = layout.beads(layout.longitude(3));
      final front = beads.reduce((a, b) => a.depth > b.depth ? a : b);
      expect(front.index, 3);
      expect(front.centre.dx, closeTo(layout.centre.dx, 1));
    });

    test('the ring crosses below the centre, not at the pole', () {
      final layout = RingLayout(size, 6);
      final front = layout
          .beads(0)
          .reduce((a, b) => a.depth > b.depth ? a : b);
      final belowCentre = front.centre.dy - layout.centre.dy;
      expect(belowCentre, greaterThan(0));
      expect(belowCentre, lessThan(layout.globeRadius));
    });

    test('a turn is taken the short way round', () {
      expect(shortestTurn(math.pi + 0.1), closeTo(-math.pi + 0.1, 1e-9));
      expect(shortestTurn(-math.pi - 0.1), closeTo(math.pi - 0.1, 1e-9));
    });
  });
}
