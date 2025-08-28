"""
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


def positive_overshoot_filtered(data):
    """Return the positive overshoot measurment"""
    return (max_value(data) - top(data)) / max_value(data) * 100


def negative_overshoot_filtered(data):
    """Return the negative overshoot measurment"""
    return (min_value(data) - base(data)) / min_value(data) * 100


def fall_time(data, time_axis):
    """Return the fall time of the data"""
    # Calculate lower (10%) and upper (90%) thresholds
    min_val = min_value(data)
    pk_pk = pk2pk(data)
    low = min_val + 0.1 * pk_pk
    high = min_val + 0.9 * pk_pk

    # Get time delta between samples
    t = time_axis[1] - time_axis[0]

    # Get indexes of high and low data
    high_index = np.where(data > high)[0]
    low_index = np.where(data < low)[0]

    # Find where a high sample goes to low and how many counts between
    fall_time_samples = []
    for i in low_index:
        if i+1 not in low_index:
            for x in range(1000):
                if i+x in high_index:
                    fall_time_samples.append(x+1)
                    break

    # Calculate average
    fall_time_samples = np.array(fall_time_samples)
    average = fall_time_samples.mean()

    # Return sample counts multiplied by time delta
    return average * t


def rise_time(data, time_axis):
    """Return the rise time of the data"""
    # Calculate lower (10%) and upper (90%) thresholds
    min_val = min_value(data)
    pk_pk = pk2pk(data)
    low = min_val + 0.1 * pk_pk
    high = min_val + 0.9 * pk_pk

    # Get time delta between samples
    t = time_axis[1] - time_axis[0]

    # Get indexes of high and low data
    high_index = np.where(data > high)[0]
    low_index = np.where(data < low)[0]

    # Find where a high sample goes to low and how many counts between
    rise_time_samples = []
    for i in high_index:
        if i+1 not in high_index:
            for x in range(1000):
                if i+x in low_index:
                    rise_time_samples.append(x+1)
                    break

    # Calculate average
    rise_time_samples = np.array(rise_time_samples)
    average = rise_time_samples.mean()

    # Return sample counts multiplied by time delta
    return average * t


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
