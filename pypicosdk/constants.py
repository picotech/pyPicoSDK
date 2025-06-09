from enum import IntEnum
import ctypes

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


CHANNEL_NAMES = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

class COUPLING(IntEnum):
    """
    Enum class representing different types of coupling used in signal processing.

    Attributes:
        AC: Represents AC coupling.
        DC: Represents DC coupling.
        DC_50OHM: Represents 50 Ohm DC coupling.
    """
    AC = 0
    DC = 1
    DC_50OHM = 50

class RANGE(IntEnum):
    """
    Enum class representing different voltage ranges used in signal processing.

    Attributes:
        mV10: Voltage range of ±10 mV.
        mV20: Voltage range of ±20 mV.
        mV50: Voltage range of ±50 mV.
        mV100: Voltage range of ±100 mV.
        mV200: Voltage range of ±200 mV.
        mV500: Voltage range of ±500 mV.
        V1: Voltage range of ±1 V.
        V2: Voltage range of ±2 V.
        V5: Voltage range of ±5 V.
        V10: Voltage range of ±10 V.
        V20: Voltage range of ±20 V.
        V50: Voltage range of ±50 V.
    """
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
    """
    Class for different bandwidth configurations.

    Attributes:
        FULL: Full bandwidth configuration.
        BW_20MHZ: Bandwidth of 20 MHz.
        BW_200MHZ: Bandwidth of 200 MHz.
    """
    FULL = 0
    BW_20MHZ = 1
    BW_200MHZ = 2

class DATA_TYPE:
    """
    Class for different data types.

    Attributes:
        INT8_T: 8-bit signed integer.
        INT16_T: 16-bit signed integer.
        INT32_T: 32-bit signed integer.
        UINT32_T: 32-bit unsigned integer.
        INT64_T: 64-bit signed integer.
    """
    INT8_T = 0
    INT16_T = 1
    INT32_T = 2
    UINT32_T = 3
    INT64_T = 4

class ACTION:
    """
    Action codes used to manage and clear data buffers.

    These action codes are used with functions like `setDataBuffer` to specify
    the type of operation to perform on data buffers.

    Attributes:
        CLEAR_ALL: Clears all data buffers.
        ADD: Adds data to the buffer.
        CLEAR_THIS_DATA_BUFFER: Clears the current data buffer.
        CLEAR_WAVEFORM_DATA_BUFFERS: Clears all waveform data buffers.
        CLEAR_WAVEFORM_READ_DATA_BUFFERS: Clears the waveform read data buffers.
    """
    CLEAR_ALL = 0x00000001
    ADD = 0x00000002
    CLEAR_THIS_DATA_BUFFER = 0x00001000
    CLEAR_WAVEFORM_DATA_BUFFERS = 0x00002000
    CLEAR_WAVEFORM_READ_DATA_BUFFERS = 0x00004000

class RATIO_MODE:
    """
    Defines various ratio modes for signal processing.

    Attributes:
        AGGREGATE: Aggregate mode for data processing.
        DECIMATE: Decimation mode for reducing data resolution.
        AVERAGE: Averaging mode for smoothing data.
        DISTRIBUTION: Mode for calculating distribution statistics.
        SUM: Mode for summing data.
        TRIGGER_DATA_FOR_TIME_CALCULATION: Mode for calculating trigger data for time-based calculations.
        SEGMENT_HEADER: Mode for segment header data processing.
        TRIGGER: Trigger mode for event-based data.
        RAW: Raw data mode, without any processing.
    """
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
    """
    Defines different power source connection statuses.

    These values represent the connection status of a power supply or USB device.

    Attributes:
        SUPPLY_CONNECTED: Power supply is connected.
        SUPPLY_NOT_CONNECTED: Power supply is not connected.
        USB3_0_DEVICE_NON_USB3_0_PORT: USB 3.0 device is connected to a non-USB 3.0 port.
    """
    SUPPLY_CONNECTED = 0x00000119
    SUPPLY_NOT_CONNECTED = 0x0000011A
    USB3_0_DEVICE_NON_USB3_0_PORT= 0x0000011E

class SAMPLE_RATE(IntEnum):
    SPS = 1
    KSPS = 1_000
    MSPS = 1_000_000
    GSPS = 1_000_000_000

class TIME_UNIT(IntEnum):
    FS = 1_000_000_000_000_000
    PS = 1_000_000_000_000
    NS = 1_000_000_000
    US = 1_000_000
    MS = 1_000
    S = 1

class PICO_TIME_UNIT(IntEnum):
    FS = 0
    PS = 1
    NS = 2
    US = 3
    MS = 4
    S = 5

class DIGITAL_PORT(IntEnum):
    """Digital port identifiers for the 6000A series."""
    PORT0 = 128
    PORT1 = 129

class DIGITAL_PORT_HYSTERESIS(IntEnum):
    """Hysteresis options for digital ports."""
    VERY_HIGH_400MV = 0
    HIGH_200MV = 1
    NORMAL_100MV = 2
    LOW_50MV = 3


class PICO_STREAMING_DATA_INFO(ctypes.Structure):
    """Structure describing streaming data buffer information."""

    _fields_ = [
        ("channel_", ctypes.c_int32),
        ("mode_", ctypes.c_int32),
        ("type_", ctypes.c_int32),
        ("noOfSamples_", ctypes.c_int32),
        ("bufferIndex_", ctypes.c_uint64),
        ("startIndex_", ctypes.c_int32),
        ("overflow_", ctypes.c_int16),
    ]


class PICO_STREAMING_DATA_TRIGGER_INFO(ctypes.Structure):
    """Structure describing trigger information for streaming."""

    _fields_ = [
        ("triggerAt_", ctypes.c_uint64),
        ("triggered_", ctypes.c_int16),
        ("autoStop_", ctypes.c_int16),
    ]
