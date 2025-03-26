from enum import IntEnum

class UNIT_INFO:
    """
    Unit information identifiers for querying PicoScope device details.

    Attributes:
        PICO_DRIVER_VERSION: PicoSDK driver version.
        PICO_USB_VERSION: USB version (e.g., USB 2.0 or USB 3.0).
        PICO_HARDWARE_VERSION: Hardware version of the PicoScope.
        PICO_VARIANT_INFO: Device model or variant identifier.
        PICO_BATCH_AND_SERIAL: Batch and serial number of the device.
        PICO_CAL_DATE: Device calibration date.
        PICO_KERNEL_VERSION: Kernel driver version.
        PICO_DIGITAL_HARDWARE_VERSION: Digital board hardware version.
        PICO_ANALOGUE_HARDWARE_VERSION: Analogue board hardware version.
        PICO_FIRMWARE_VERSION_1: First part of the firmware version.
        PICO_FIRMWARE_VERSION_2: Second part of the firmware version.

    Examples:
        >>> scope.get_unit_info(picosdk.UNIT_INFO.PICO_BATCH_AND_SERIAL)
        "JM115/0007"

    """
    PICO_DRIVER_VERSION = 0 
    PICO_USB_VERSION = 1
    PICO_HARDWARE_VERSION = 2
    PICO_VARIANT_INFO = 3
    PICO_BATCH_AND_SERIAL = 4
    PICO_CAL_DATE = 5
    PICO_KERNEL_VERSION = 6
    PICO_DIGITAL_HARDWARE_VERSION = 7
    PICO_ANALOGUE_HARDWARE_VERSION = 8
    PICO_FIRMWARE_VERSION_1 = 9
    PICO_FIRMWARE_VERSION_2 = 10

class RESOLUTION:
    """
    Resolution constants for PicoScope devices.

    **WARNING: Not all devices support all resolutions.**

    Attributes:
        _8BIT: 8-bit resolution.
        _10BIT: 10-bit resolution.
        _12BIT: 12-bit resolution.
        _14BIT: 14-bit resolution.
        _15BIT: 15-bit resolution.
        _16BIT: 16-bit resolution.

    Examples:
        >>> scope.open_unit(resolution=RESOLUTION._16BIT)
    """
    _8BIT = 0
    _10BIT = 10
    _12BIT = 1
    _14BIT = 2
    _15BIT = 3
    _16BIT = 4

class TRIGGER_DIR:
    """
    Trigger direction constants for configuring PicoScope triggers.

    Attributes:
        ABOVE: Trigger when the signal goes above the threshold.
        BELOW: Trigger when the signal goes below the threshold.
        RISING: Trigger on rising edge.
        FALLING: Trigger on falling edge.
        RISING_OR_FALLING: Trigger on either rising or falling edge.
    """
    ABOVE = 0
    BELOW = 1
    RISING = 2
    FALLING = 3
    RISING_OR_FALLING = 4

class WAVEFORM:    
    """
    Waveform type constants for PicoScope signal generator configuration.

    Attributes:
        SINE: Sine wave.
        SQUARE: Square wave.
        TRIANGLE: Triangle wave.
        RAMP_UP: Rising ramp waveform.
        RAMP_DOWN: Falling ramp waveform.
        SINC: Sinc function waveform.
        GAUSSIAN: Gaussian waveform.
        HALF_SINE: Half sine waveform.
        DC_VOLTAGE: Constant DC voltage output.
        PWM: Pulse-width modulation waveform.
        WHITENOISE: White noise output.
        PRBS: Pseudo-random binary sequence.
        ARBITRARY: Arbitrary user-defined waveform.
    """
    SINE = 0x00000011
    SQUARE = 0x00000012
    TRIANGLE = 0x00000013
    RAMP_UP = 0x00000014
    RAMP_DOWN = 0x00000015
    SINC = 0x00000016
    GAUSSIAN = 0x00000017
    HALF_SINE = 0x00000018
    DC_VOLTAGE = 0x00000400
    PWM = 0x00001000
    WHITENOISE = 0x00002001
    PRBS = 0x00002002
    ARBITRARY = 0x10000000

class CHANNEL(IntEnum):
    """
    Constants for each channel of the PicoScope.

    Attributes:
        A: Channel A
        B: Channel B
        C: Channel C
        D: Channel D
        E: Channel E
        F: Channel F
        G: Channel G
        H: Channel H
    """
    A = 0
    B = 1
    C = 2 
    D = 3
    E = 4
    F = 5
    G = 6 
    H = 7

class COUPLING(IntEnum):
    AC = 0
    DC = 1
    DC_50OHM = 2

class RANGE(IntEnum):
    mV10 = 0
    mV20 = 1
    mV50 = 2
    mV100 = 3
    mV200 = 4
    mV500 = 5
    V1 = 6
    V2 = 7
    V5 = 8
    V10 = 9
    V20 = 10
    V50 = 11

RANGE_LIST = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000]

class BANDWIDTH_CH:
    FULL = 0
    BW_20MHZ = 1
    BW_200MHZ = 2

class DATA_TYPE:
    INT8_T = 0
    INT16_T = 1
    INT32_T = 2
    UINT32_T = 3
    INT64_T = 4

class ACTION:
    CLEAR_ALL = 0x00000001
    ADD = 0x00000002
    CLEAR_THIS_DATA_BUFFER = 0x00001000
    CLEAR_WAVEFORM_DATA_BUFFERS = 0x00002000
    CLEAR_WAVEFORM_READ_DATA_BUFFERS = 0x00004000

class RATIO_MODE:
    AGGREGATE = 1
    DECIMATE = 2
    AVERAGE = 4
    DISTRIBUTION = 8
    SUM = 16
    TRIGGER_DATA_FOR_TIME_CALCUATION = 0x10000000
    SEGMENT_HEADER = 0x20000000
    TRIGGER = 0x40000000
    RAW = 0x80000000

class POWER_SOURCE:
    SUPPLY_CONNECTED = 0x00000119
    SUPPLY_NOT_CONNECTED = 0x0000011A
    USB3_0_DEVICE_NON_USB3_0_PORT= 0x0000011E