from pypicosdk import ps6000a, TIME_UNIT


def test_get_time_axis_units():
    scope = ps6000a('pytest')
    # Patch get_timebase to return a fixed interval of 100 ns
    scope.get_timebase = lambda tb, s: {'Interval(ns)': 100, 'Samples': s}

    axis_ns = scope.get_time_axis(2, 3, TIME_UNIT.NS)
    assert axis_ns.tolist() == [0.0, 100.0, 200.0]

    axis_us = scope.get_time_axis(2, 3, TIME_UNIT.US)
    assert axis_us.tolist() == [0.0, 0.1, 0.2]

    axis_auto = scope.get_time_axis(2, 3, None)
    assert axis_auto.tolist() == [0.0, 100.0, 200.0]
