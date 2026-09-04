// Copyright 2026 Max Brito
// SPDX-License-Identifier: Apache-2.0

/// Where the sun is, from the system clock alone.
library;

import 'dart:math' as math;

/// The point on the Earth the sun is directly overhead, in radians.
class SubsolarPoint {
  const SubsolarPoint(this.latitude, this.longitude);

  final double latitude;
  final double longitude;
}

/// Low-precision solar position from the *Astronomical Almanac*.
///
/// Good to well under a tenth of a degree, which is far finer than a globe a
/// few hundred pixels across can show, and it needs nothing but the clock.
SubsolarPoint subsolarPoint(DateTime when) {
  final utc = when.toUtc();

  // Days since J2000.0.
  final julian = utc.millisecondsSinceEpoch / 86400000.0 + 2440587.5;
  final n = julian - 2451545.0;

  final meanAnomaly = _radians((357.528 + 0.9856003 * n) % 360.0);
  final meanLongitude = (280.459 + 0.98564736 * n) % 360.0;
  final eclipticLongitude = _radians((meanLongitude +
          1.915 * math.sin(meanAnomaly) +
          0.020 * math.sin(2 * meanAnomaly)) %
      360.0);
  final obliquity = _radians(23.439 - 0.00000036 * n);

  final declination =
      math.asin(math.sin(obliquity) * math.sin(eclipticLongitude));

  // Equation of time: the gap between apparent and mean solar time.
  final rightAscension = (_degrees(math.atan2(
              math.cos(obliquity) * math.sin(eclipticLongitude),
              math.cos(eclipticLongitude))) %
          360.0);
  final equationOfTime =
      (((meanLongitude - rightAscension + 180.0) % 360.0) - 180.0) * 4.0;

  final hours = utc.hour +
      utc.minute / 60.0 +
      utc.second / 3600.0 +
      utc.millisecond / 3600000.0;
  var longitude = -15.0 * (hours + equationOfTime / 60.0 - 12.0);
  longitude = ((longitude + 180.0) % 360.0) - 180.0;

  return SubsolarPoint(declination, _radians(longitude));
}

/// The rotation that turns the viewer's own part of the world to the front.
///
/// The globe is lit by the real sun, so a globe pinned to the prime meridian
/// shows a dark face all evening while the daylight sits round the back.
/// Fifteen degrees of longitude an hour, from the clock's offset from UTC.
double localMeridian([DateTime? now]) {
  final when = now ?? DateTime.now();
  final hours = when.timeZoneOffset.inMinutes / 60.0;
  return hours * (math.pi / 12.0);
}

double _radians(double degrees) => degrees * math.pi / 180.0;
double _degrees(double radians) => radians * 180.0 / math.pi;
