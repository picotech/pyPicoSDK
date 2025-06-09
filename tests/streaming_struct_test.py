import ctypes
from pypicosdk import (
    PICO_STREAMING_DATA_INFO,
    PICO_STREAMING_DATA_TRIGGER_INFO,
    CHANNEL,
    DATA_TYPE,
    RATIO_MODE,
)

def test_streaming_info_fields():
    info = PICO_STREAMING_DATA_INFO()
    info.channel_ = CHANNEL.A
    info.mode_ = RATIO_MODE.RAW
    info.type_ = DATA_TYPE.INT16_T
    info.noOfSamples_ = 0
    info.bufferIndex_ = 0
    info.startIndex_ = 0
    info.overflow_ = 0

    assert info.channel_ == CHANNEL.A
    assert info.mode_ == ctypes.c_int32(RATIO_MODE.RAW).value


def test_streaming_trigger_info_fields():
    trig = PICO_STREAMING_DATA_TRIGGER_INFO()
    trig.triggerAt_ = 0
    trig.triggered_ = 0
    trig.autoStop_ = 0

    assert trig.triggered_ == 0
