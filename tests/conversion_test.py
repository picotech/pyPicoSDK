"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

pytest file for checking the mv/adc conversions
"""
from pypicosdk import ps6000a, RANGE, CHANNEL
from pypicosdk._classes._channel_class import ChannelClass
channel = CHANNEL.A


def test_ps6000a_mv_to_adc():
    """Test mv_to_adc function"""
    scope = ps6000a('pytest')
    scope.max_adc_value = 32000
    scope.channel_db[channel] = ChannelClass(RANGE.V1, 1)
    assert scope.mv_to_adc(5.0, channel) == 160


def test_ps6000a_adc_to_mv():
    """Test adc_to_mv function"""
    scope = ps6000a('pytest')
    scope.max_adc_value = 32000
    scope.channel_db[channel] = ChannelClass(RANGE.V1, 1)
    assert scope.adc_to_mv(160, 0) == 5.0
