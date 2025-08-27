"""
pytest file for checking the mv/adc conversions
"""
from pypicosdk import ps6000a, RANGE


def test_mv_to_adc():
    """Test mv_to_adc function"""
    scope = ps6000a('pytest')
    scope.range = {0: 6}  # Channel A set to 1 V
    scope.probe_scale = {0: 1.0}  # Channel A at 1.0 probe scale
    scope.max_adc_value = 32000
    assert scope.mv_to_adc(5.0, RANGE.V1) == 160


def test_adc_to_mv():
    """Test adc_to_mv function"""
    scope = ps6000a('pytest')
    scope.range = {0: 6}  # Channel A set to 1 V
    scope.probe_scale = {0: 1.0}  # Channel A at 1.0 probe scale
    scope.max_adc_value = 32000
    assert scope.adc_to_mv(160, 0) == 5.0
