"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

This script is an example of the kind of measurements you can do in python.

These measurements demonstrate one of many methods of measuring the ADC data from your PicoScope.
When making measurements yourself, always verify that your method is suitable for your
hardware, signal characteristics, and accuracy requirements.
"""

import numpy as np


def top(data, bins=32):
    """Return the "Top" mode of the data"""

    # Sort and get upper 40% of samples
    data = np.sort(data)
    data = data[int(len(data) * 0.6):]

    # Build histogram and get max counts
    counts, bin_edges = np.histogram(data, bins=bins)
    mode_bin_index = np.argmax(counts)

    # Get upper and lower edges of bins
    lbe = bin_edges[mode_bin_index]
    upe = bin_edges[mode_bin_index + 1]

    # Get data between the bin edges
    filtered = data[(data >= lbe) & (data <= upe)]

    # Return the average of samples between bin edges
    return float(filtered.mean())


def base(data, bins=32):
    """Return the "Base" mode of the data"""

    # Sort and get lower 40% of samples
    data = np.sort(data)
    data = data[: int(len(data) * 0.4)]

    # Build histogram and get max counts
    counts, bin_edges = np.histogram(data, bins=bins)
    mode_bin_index = np.argmax(counts)

    # Get upper and lower edges of bins
    lbe = bin_edges[mode_bin_index]
    upe = bin_edges[mode_bin_index + 1]

    # Get data between the bin edges
    filtered = data[(data >= lbe) & (data <= upe)]

    # Return the average of samples between bin edges
    return float(filtered.mean())


def max_value(data):
    """Return the max value"""
    return np.max(data)


def min_value(data):
    """Return the minimum value"""
    return np.min(data)


def pk2pk(data):
    """Return the peak to peak"""
    return float(max(data) - min(data))


def amplitude(data):
    """Return the amplitude"""
    return float(top(data) - base(data)) / 2


def rms(data):
    """Return the RMS (root mean squared)"""
    return float(np.sqrt(np.mean(np.square(data - data.mean()))))

def average(data):
    """Return the average"""
    return np.mean(data)


def positive_overshoot_filtered(data):
    """Positive overshoot as % of step height."""
    v_top = top(data)
    v_base = base(data)
    step = v_top - v_base
    if not np.isfinite(step) or step <= 0:
        return float('nan')
    v_max = max_value(data)
    pos = (v_max - v_top) / step * 100.0
    return float(max(0.0, pos))


def negative_overshoot_filtered(data):
    """Negative overshoot as % of step height."""
    v_top = top(data)
    v_base = base(data)
    step = v_top - v_base
    if not np.isfinite(step) or step <= 0:
        return float('nan')
    v_min = min_value(data)
    neg = (v_base - v_min) / step * 100.0
    return float(max(0.0, neg))


def zero_crossings(data: np.ndarray, hysteresis: float = 0.0) -> np.ndarray:
    """Return indices of zero crossings in ``data`` with optional hysteresis."""

    centered = data - data.mean()
    if hysteresis <= 0:
        return np.where(np.diff(np.sign(centered)))[0]

    sign = 1 if centered[0] >= 0 else -1
    crossings = []
    for i, value in enumerate(centered[1:], 1):
        if sign >= 0 and value <= -hysteresis:
            sign = -1
            crossings.append(i - 1)
        elif sign <= 0 and value >= hysteresis:
            sign = 1
            crossings.append(i - 1)
    return np.asarray(crossings, dtype=int)


def measure_frequency(
    data: np.ndarray, sample_rate: float, hysteresis: float = 0.0
) -> float:
    """Return the average frequency of ``data`` in Hz.

    Args:
        data: Waveform samples.
        sample_rate: Sampling rate in samples per second.
        hysteresis: Threshold for zero crossing detection in mV.
    """

    crossings = zero_crossings(data, hysteresis)
    if len(crossings) < 3:
        return float("nan")
    # Use every other crossing to avoid measuring half periods
    periods = (crossings[2:] - crossings[:-2]) / sample_rate
    return float(1 / periods.mean())
