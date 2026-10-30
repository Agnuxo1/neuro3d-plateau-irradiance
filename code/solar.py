"""Solar geometry and a clear-sky irradiance model, shared by both engines.

Deliberately simple and identical on both sides of the comparison, so that the
measured difference between the own engine and the Cycles control is a
difference in *light transport*, not in the radiation model.

Solar position: NOAA Solar Calculator equations (Meeus, low-precision set).
Clear sky: Hottel (1976) beam transmittance for a 23 km visibility standard
atmosphere, with the Liu-Jordan diffuse correlation. This is a clear-sky model,
not measured weather data, and every figure derived from it says so.
"""

from __future__ import annotations

import datetime as dt

import numpy as np


def solar_position(times_utc: np.ndarray, lat_deg: float, lon_deg: float):
    """Return (altitude, azimuth) in radians. Azimuth is clockwise from north.

    `times_utc` is an array of POSIX seconds (UTC).
    """
    jd = times_utc / 86400.0 + 2440587.5
    jc = (jd - 2451545.0) / 36525.0
    gml = np.radians((280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360.0)
    gma = np.radians(357.52911 + jc * (35999.05029 - 0.0001537 * jc))
    ecc = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    ctr = (np.sin(gma) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
           + np.sin(2 * gma) * (0.019993 - 0.000101 * jc)
           + np.sin(3 * gma) * 0.000289)
    true_long = gml + np.radians(ctr)
    omega = np.radians(125.04 - 1934.136 * jc)
    app_long = true_long - np.radians(0.00569) - np.radians(0.00478) * np.sin(omega)
    seps = 23.0 + (26.0 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60.0) / 60.0
    oblq = np.radians(seps + 0.00256 * np.cos(omega))
    decl = np.arcsin(np.sin(oblq) * np.sin(app_long))

    y = np.tan(oblq / 2.0) ** 2
    eqt = 4.0 * np.degrees(
        y * np.sin(2 * gml)
        - 2 * ecc * np.sin(gma)
        + 4 * ecc * y * np.sin(gma) * np.cos(2 * gml)
        - 0.5 * y * y * np.sin(4 * gml)
        - 1.25 * ecc * ecc * np.sin(2 * gma)
    )

    # True solar time in minutes of the day.
    frac_day = (times_utc % 86400.0) / 60.0
    tst = (frac_day + eqt + 4.0 * lon_deg) % 1440.0
    ha = np.radians(tst / 4.0 - 180.0)

    lat = np.radians(lat_deg)
    cz = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(ha)
    cz = np.clip(cz, -1.0, 1.0)
    alt = np.pi / 2 - np.arccos(cz)
    # Azimuth clockwise from north.
    az = np.arctan2(np.sin(ha), np.cos(ha) * np.sin(lat) - np.tan(decl) * np.cos(lat))
    az = (az + np.pi) % (2 * np.pi)
    return alt, az


def sun_vector(alt: np.ndarray, az: np.ndarray) -> np.ndarray:
    """Unit vectors pointing from the ground towards the sun, in local ENU."""
    return np.stack(
        [np.cos(alt) * np.sin(az), np.cos(alt) * np.cos(az), np.sin(alt)], axis=-1
    )


def clear_sky(alt: np.ndarray, altitude_km: float = 0.01):
    """Hottel beam and Liu-Jordan diffuse, in W/m**2. Zero below the horizon."""
    sz = np.sin(np.maximum(alt, 1e-6))
    a0 = 0.4237 - 0.00821 * (6.0 - altitude_km) ** 2
    a1 = 0.5055 + 0.00595 * (6.5 - altitude_km) ** 2
    k = 0.2711 + 0.01858 * (2.5 - altitude_km) ** 2
    tau_b = a0 + a1 * np.exp(-k / sz)
    tau_d = 0.2710 - 0.2939 * tau_b
    gsc = 1367.0
    dni = np.where(alt > 0, gsc * np.maximum(tau_b, 0.0), 0.0)
    dhi = np.where(alt > 0, gsc * sz * np.maximum(tau_d, 0.0), 0.0)
    return dni, dhi


def timesteps(year: int, tz_hours: float, hour_step: float = 1.0):
    """Monthly-representative time steps with the hours each one stands for.

    The 15th of each month is used as the representative day; every daylight
    hour of that day is weighted by the number of days in the month, so the sum
    approximates a year of clear skies.
    """
    import calendar

    times, weights = [], []
    for month in range(1, 13):
        ndays = calendar.monthrange(year, month)[1]
        h = 0.0
        while h < 24.0:
            local = dt.datetime(year, month, 15) + dt.timedelta(hours=h)
            utc = local - dt.timedelta(hours=tz_hours)
            times.append(utc.replace(tzinfo=dt.timezone.utc).timestamp())
            weights.append(ndays * hour_step)
            h += hour_step
    return np.asarray(times), np.asarray(weights)


def tregenza_patches():
    """145-patch Tregenza sky dome: directions, solid angles, cos-weight check."""
    counts = [30, 30, 24, 24, 18, 12, 6]
    alts = [6, 18, 30, 42, 54, 66, 78]
    dirs, omegas = [], []
    band = np.radians(12.0)
    for n, a in zip(counts, alts):
        a = np.radians(a)
        omega = band * (2 * np.pi / n) * np.cos(a)
        for i in range(n):
            az = 2 * np.pi * (i + 0.5) / n
            dirs.append([np.cos(a) * np.sin(az), np.cos(a) * np.cos(az), np.sin(a)])
            omegas.append(omega)
    # Cap.
    a_cap = np.radians(84.0)
    dirs.append([0.0, 0.0, 1.0])
    omegas.append(2 * np.pi * (1 - np.sin(a_cap)))
    d = np.asarray(dirs, np.float64)
    o = np.asarray(omegas, np.float64)
    # Normalise so that an unobstructed horizontal plane receives exactly DHI.
    o *= np.pi / float((o * d[:, 2]).sum())
    return d, o
