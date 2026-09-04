// Copyright 2026 Max Brito
// SPDX-License-Identifier: Apache-2.0
//
// The Earth, lit by where the sun actually is.
//
// The sphere is an orthographic projection: for each pixel of the disc, work
// out the surface normal, turn that into a latitude and longitude, and look it
// up in an equirectangular map. Day and night are two maps, mixed by the solar
// elevation computed for that same point, so the terminator is exact at every
// frame rather than baked into an image that has to be regenerated.

#version 460 core

#include <flutter/runtime_effect.glsl>

precision highp float;

uniform vec2 uOrigin;        // top-left of the globe within the painted area
uniform vec2 uSize;          // the globe's box, in pixels; square
uniform float uRotation;     // globe spin, radians
uniform float uTilt;         // camera lift above the equator, radians
uniform float uSunLat;       // subsolar latitude, radians
uniform float uSunLon;       // subsolar longitude, radians
uniform float uTwilightLo;   // solar elevation that is fully night, radians
uniform float uTwilightHi;   // solar elevation that is fully day, radians
uniform float uNightAmbient; // daylight left in the night side
uniform float uOpacity;

uniform sampler2D uDay;
uniform sampler2D uNight;

out vec4 fragColor;

const float kPi = 3.14159265358979;
const float kTwoPi = 6.28318530717959;

void main() {
    vec2 p = ((FlutterFragCoord().xy - uOrigin) / uSize) * 2.0 - 1.0;
    float r2 = dot(p, p);
    if (r2 > 1.0) {
        fragColor = vec4(0.0);
        return;
    }

    // Surface normal of the visible hemisphere, then rotated out of the
    // camera's tilt into world space.
    vec3 n = vec3(p.x, -p.y, sqrt(max(0.0, 1.0 - r2)));
    float ct = cos(uTilt);
    float st = sin(uTilt);
    vec3 m = vec3(n.x, ct * n.y + st * n.z, -st * n.y + ct * n.z);

    float lat = asin(clamp(m.y, -1.0, 1.0));
    float lon = atan(m.x, m.z) + uRotation;

    vec2 uv = vec2(fract(lon / kTwoPi + 0.5), 0.5 - lat / kPi);
    vec3 day = texture(uDay, uv).rgb;
    vec3 night = texture(uNight, uv).rgb + day * uNightAmbient;

    // Solar elevation here, straight from spherical trigonometry.
    float sinElevation = sin(lat) * sin(uSunLat)
        + cos(lat) * cos(uSunLat) * cos(lon - uSunLon);
    float elevation = asin(clamp(sinElevation, -1.0, 1.0));
    float daylight = smoothstep(uTwilightLo, uTwilightHi, elevation);

    vec3 colour = mix(night, day, daylight);

    // Atmosphere towards the limb, and a soft edge so the globe is not a
    // cut-out circle.
    float r = sqrt(r2);
    float rim = smoothstep(0.72, 1.0, r);
    colour = mix(colour, vec3(0.32, 0.55, 0.95), rim * rim * 0.45);

    float edge = 1.0 - smoothstep(1.0 - 1.5 / uSize.x, 1.0, r);
    float alpha = edge * uOpacity;
    fragColor = vec4(colour * alpha, alpha);
}
