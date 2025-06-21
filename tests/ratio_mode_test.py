from pypicosdk import RATIO_MODE


def test_ratio_mode_alias():
    assert (
        RATIO_MODE.TRIGGER_DATA_FOR_TIME_CALCUATION
        == RATIO_MODE.TRIGGER_DATA_FOR_TIME_CALCULATION
    )

