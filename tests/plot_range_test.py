import pypicosdk as psdk
from pypicosdk import RANGE, CHANNEL


def test_plot_range_single_channel():
    scope = psdk.ps6000a('pytest')
    scope.range = {CHANNEL.A: RANGE.V1}
    assert scope.get_plot_range() == (-1000, 1000)


def test_plot_range_multiple_channels():
    scope = psdk.ps6000a('pytest')
    scope.range = {CHANNEL.A: RANGE.V1, CHANNEL.B: RANGE.V10}
    assert scope.get_plot_range() == (-10000, 10000)
