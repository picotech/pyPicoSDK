import pypicosdk as psdk
from pypicosdk import RANGE, CHANNEL


def test_plot_range_single_channel():
    scope = psdk.ps6000a('pytest')
    scope.range = {CHANNEL.A: RANGE.V1}
    pr = scope.get_plot_range()
    assert tuple(pr) == (-1000, 1000)
    assert pr.ylim == (-1000, 1000)
    assert pr.unit == "mV"


def test_plot_range_multiple_channels():
    scope = psdk.ps6000a('pytest')
    scope.range = {CHANNEL.A: RANGE.V1, CHANNEL.B: RANGE.V10}
    pr = scope.get_plot_range()
    assert tuple(pr) == (-10000, 10000)
    assert pr.unit == "mV"
