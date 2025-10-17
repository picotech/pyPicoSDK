"""Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms."""

from enum import IntEnum
import ctypes
from typing import Literal

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

    BIT_8 = 0
    BIT_10 = 10
    BIT_12 = 1
    BIT_14 = 2
    BIT_15 = 3
    BIT_16 = 4

resolution_literal = Literal['8bit', '10bit', '12bit', '14bit', '15bit', '16bit']
resolution_map = {'8bit':0, '10bit':10, '12bit':1, '14bit':2, '15bit':3, '16bit':4}

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

trigger_dir_l = Literal['above', 'below', 'rising', 'falling', 'rising or falling']
trigger_dir_m = {'above': 0,
                 'below': 1,
                 'rising': 2,
                 'falling': 3,
                 'rising or falling': 4}

class WAVEFORM(IntEnum):
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


ps5000a_waveform_map = {
    WAVEFORM.SINE: 0,
    WAVEFORM.SQUARE: 1,
    WAVEFORM.TRIANGLE: 2,
    WAVEFORM.RAMP_UP: 3,
    WAVEFORM.RAMP_DOWN: 4,
    WAVEFORM.SINC: 5,
    WAVEFORM.GAUSSIAN: 6,
    WAVEFORM.HALF_SINE: 7,
    WAVEFORM.DC_VOLTAGE: 8,
    WAVEFORM.WHITENOISE: 9
}


waveform_literal = Literal[
    'sine',
    'square',
    'triangle',
    'ramp_up',
    'ramp_down',
    'sinc',
    'gaussian',
    'half_sine',
    'dc_voltage',
    'pwm',
    'whitenoise',
    'prbs',
    'arbitrary'
]

waveform_map = {
    'sine':        0x00000011,
    'square':      0x00000012,
    'triangle':    0x00000013,
    'ramp_up':     0x00000014,
    'ramp_down':   0x00000015,
    'sinc':        0x00000016,
    'gaussian':    0x00000017,
    'half_sine':   0x00000018,
    'dc_voltage':  0x00000400,
    'pwm':         0x00001000,
    'whitenoise':  0x00002001,
    'prbs':        0x00002002,
    'arbitrary':   0x10000000
}


class CHANNEL(IntEnum):
    """Constants representing PicoScope trigger and input channels.

    Attributes:
        A: Channel A
        B: Channel B
        C: Channel C
        D: Channel D
        E: Channel E
        F: Channel F
        G: Channel G
        H: Channel H
        TRIGGER_AUX: Dedicated auxiliary trigger input
    """
    A = 0
    B = 1
    C = 2
    D = 3
    E = 4
    F = 5
    G = 6
    H = 7

    #: External trigger input.
    EXTERNAL = 1000

    #: Auxiliary trigger input/output.
    TRIGGER_AUX = 1001

    PULSE_WIDTH_SOURCE = 0x10000000
    PICO_DIGITAL_SOURCE = 0x10000001

CHANNEL_NAMES = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

channel_literal = Literal[
    'channel_a',
    'channel_b',
    'channel_c',
    'channel_d',
    'channel_e',
    'channel_f',
    'channel_g',
    'channel_h',
    'external',
    'trigger_aux'
]

channel_map = {
    'channel_a': 0,
    'channel_b': 1,
    'channel_c': 2,
    'channel_d': 3,
    'channel_e': 4,
    'channel_f': 5,
    'channel_g': 6,
    'channel_h': 7,
    'external': 1000,
    'trigger_aux': 1001
}

led_channel_l = Literal[
    'A',
    'B',
    'C',
    'D',
    'E',
    'F',
    'G',
    'H',
    'AWG',
    'AUX',
]

led_channel_m = {
    'A':0,
    'B':1,
    'C':2,
    'D':3,
    'E':4,
    'F':5,
    'G':6,
    'H':7,
    'AWG':0x10000,
    'AUX':0x20000,
}

class PICO_CHANNEL_OVERVOLTAGE_TRIPPED(ctypes.Structure):
    """Status flag indicating an overvoltage trip on a channel.
    Attributes:
        channel_: Channel identifier as a :class:`CHANNEL` value.
        tripped_: ``1`` if an overvoltage trip occurred, otherwise ``0``.
    """

    _pack_ = 1

    _fields_ = [
        ("channel_", ctypes.c_int32),
        ("tripped_", ctypes.c_uint8),
    ]

class PICO_CHANNEL_FLAGS(IntEnum):
    """Bit flags describing individual channels and digital ports."""

    CHANNEL_A = 1
    CHANNEL_B = 2
    CHANNEL_C = 4
    CHANNEL_D = 8
    CHANNEL_E = 16
    CHANNEL_F = 32
    CHANNEL_G = 64
    CHANNEL_H = 128

    PORT0 = 65536
    PORT1 = 131072
    PORT2 = 262144
    PORT3 = 524288

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

RANGE_LIST = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000,
              100_000, 200_000, 500_000, 1_000_000]

range_literal = Literal[
    '10mV',
    '20mV',
    '50mV',
    '100mV',
    '200mV',
    '500mV',
    '1V',
    '2V',
    '5V',
    '10V',
    '20V',
]

range_map = {
    '10mV': 0,
    '20mV': 1,
    '50mV': 2,
    '100mV': 3,
    '200mV': 4,
    '500mV': 5,
    '1V': 6,
    '2V': 7,
    '5V': 8,
    '10V': 9,
    '20V': 10,
}

ProbeScale_L = Literal['x1', 'x2', 'x5', 'x10', 'x20', 'x50', 'x100', 'x200', 'x500', 'x1000']
ProbeScale_M = {
    'x1': 1,
    'x2': 2,
    'x5': 5,
    'x10': 10,
    'x20': 20,
    'x50': 50,
    'x100': 100,
    'x200': 200,
    'x500': 500,
    'x1000': 1000
}

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
        TRIGGER: Trigger mode for event-based data. If manually setting buffers, TRIGGER will need its own buffer set.
        RAW: Raw data mode, without any processing.
    """
    NONE = 0
    AGGREGATE = 1
    DECIMATE = 2
    AVERAGE = 4
    DISTRIBUTION = 8
    SUM = 16
    TRIGGER_DATA_FOR_TIME_CALCULATION = 0x10000000
    TRIGGER_DATA_FOR_TIME_CALCUATION = (
        TRIGGER_DATA_FOR_TIME_CALCULATION
    )  # Deprecated alias
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
    USB3_0_DEVICE_NON_USB3_0_PORT = 0x0000011E


PwrSrc_L = Literal['AC PSU', 'USB', '2-channel']
PwrSrc_M = {
    'AC PSU': POWER_SOURCE.SUPPLY_CONNECTED,
    'USB': POWER_SOURCE.SUPPLY_NOT_CONNECTED,
    '2-channel': POWER_SOURCE.USB3_0_DEVICE_NON_USB3_0_PORT,
}


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


TimeUnit_L = Literal['fs', 'ps', 'ns', 'us', 'ms', 's']
TimeUnitPwr_M = {'fs': 15, 'ps': 12, 'ns': 9, 'us': 6, 'ms': 3, 's': 0}
TimeUnitStd_M = {
    'fs': 1_000_000_000_000_000,
    'ps': 1_000_000_000_000,
    'ns': 1_000_000_000,
    'us': 1_000_000,
    'ms': 1_000,
    's': 1}


class _PICO_TIME_UNIT(IntEnum):
    FS = 0
    PS = 1
    NS = 2
    US = 3
    MS = 4
    S = 5


_PicoStandardConv = {
    0: TIME_UNIT.FS,
    1: TIME_UNIT.PS,
    2: TIME_UNIT.NS,
    3: TIME_UNIT.US,
    4: TIME_UNIT.MS,
    5: TIME_UNIT.S,
}

_PicoTimeUnitText = {
    0: 'fs',
    1: 'ps',
    2: 'ns',
    3: 'us',
    4: 'ms',
    5: 's',
}

_TimeUnitText = {
    1_000_000_000_000_000: 'fs',
    1_000_000_000_000: 'ps',
    1_000_000_000: 'ns',
    1_000_000: 'us',
    1_000: 'ms',
    1: 's',
}

_StandardPicoConv = {
    1_000_000_000_000_000: _PICO_TIME_UNIT.FS,
    1_000_000_000_000: _PICO_TIME_UNIT.PS,
    1_000_000_000: _PICO_TIME_UNIT.NS,
    1_000_000: _PICO_TIME_UNIT.US,
    1_000: _PICO_TIME_UNIT.MS,
    1: _PICO_TIME_UNIT.S,
}


class PICO_VERSION(ctypes.Structure):
    """Firmware or driver version information.
    Attributes:
        major_: Major version number.
        minor_: Minor version number.
        revision_: Revision number.
        build_: Build number.
    """

    _pack_ = 1

    _fields_ = [
        ("major_", ctypes.c_int16),
        ("minor_", ctypes.c_int16),
        ("revision_", ctypes.c_int16),
        ("build_", ctypes.c_int16),
    ]


class PICO_FIRMWARE_INFO(ctypes.Structure):
    """Information describing firmware versions and updates.
    Attributes:
        firmwareType_: Firmware identifier as a :class:`UNIT_INFO` value.
        currentVersion_: Currently installed :class:`PICO_VERSION`.
        updateVersion_: Available update :class:`PICO_VERSION`.
        updateRequired_: ``1`` if an update is required, otherwise ``0``.
    """

    _pack_ = 1

    _fields_ = [
        ("firmwareType_", ctypes.c_uint32),
        ("currentVersion_", PICO_VERSION),
        ("updateVersion_", PICO_VERSION),
        ("updateRequired_", ctypes.c_uint16),
    ]

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

class PICO_CHANNEL_FLAGS(IntEnum):
    """Bit flags for enabled channels used by ``ps6000aChannelCombinationsStateless``."""

    CHANNEL_A_FLAGS = 1
    CHANNEL_B_FLAGS = 2
    CHANNEL_C_FLAGS = 4
    CHANNEL_D_FLAGS = 8
    CHANNEL_E_FLAGS = 16
    CHANNEL_F_FLAGS = 32
    CHANNEL_G_FLAGS = 64
    CHANNEL_H_FLAGS = 128

    PORT0_FLAGS = 65536
    PORT1_FLAGS = 131072
    PORT2_FLAGS = 262144
    PORT3_FLAGS = 524288


class PICO_CONNECT_PROBE_RANGE(IntEnum):
    """Input range identifiers for ``get_analogue_offset_limits``."""

    CONNECT_PROBE_OFF = 1024

    D9_BNC_10MV = 0
    D9_BNC_20MV = 1
    D9_BNC_50MV = 2
    D9_BNC_100MV = 3
    D9_BNC_200MV = 4
    D9_BNC_500MV = 5
    D9_BNC_1V = 6
    D9_BNC_2V = 7
    D9_BNC_5V = 8
    D9_BNC_10V = 9
    D9_BNC_20V = 10
    D9_BNC_50V = 11
    D9_BNC_100V = 12
    D9_BNC_200V = 13

class PICO_PROBE_RANGE_INFO(IntEnum):
    """Probe attenuation identifiers for ``get_scaling_values``."""

    PROBE_NONE_NV = 0
    X1_PROBE_NV = 1
    X10_PROBE_NV = 10


class PICO_SCALING_FACTORS_VALUES(ctypes.Structure):
    """Scaling factors for a channel and range."""

    _pack_ = 1

    _fields_ = [
        ("channel_", ctypes.c_int32),
        ("range_", ctypes.c_int32),
        ("offset_", ctypes.c_int16),
        ("scalingFactor_", ctypes.c_double),
    ]


class PICO_SCALING_FACTORS_FOR_RANGE_TYPES_VALUES(ctypes.Structure):
    """Scaling factors for a probe range type."""

    _pack_ = 1

    _fields_ = [
        ("channel_", ctypes.c_int32),
        ("rangeMin_", ctypes.c_int64),
        ("rangeMax_", ctypes.c_int64),
        ("rangeType_", ctypes.c_int32),
        ("offset_", ctypes.c_int16),
        ("scalingFactor_", ctypes.c_double),
    ]

class AUXIO_MODE(IntEnum):
    """Operating modes for the AUX IO connector."""

    #: High impedance input for triggering the scope or signal generator.
    INPUT = 0

    #: Constant logic high output.
    HIGH_OUT = 1

    #: Constant logic low output.
    LOW_OUT = 2

    #: Logic high pulse during the post-trigger acquisition time.
    TRIGGER_OUT = 3

class PICO_CHANNEL_OVERVOLTAGE_TRIPPED(ctypes.Structure):
    """Status flag indicating whether a channel's input protection tripped.
    Attributes:
        channel_: Channel identifier as a :class:`CHANNEL` value.
        tripped_: ``1`` if the channel has tripped due to overvoltage.
    """

    _pack_ = 1

    _fields_ = [
        ("channel_", ctypes.c_int32),
        ("tripped_", ctypes.c_uint8),
    ]

class TRIGGER_STATE(IntEnum):
    """Trigger state values used in :class:`PICO_CONDITION`."""

    #: Channel is ignored when evaluating trigger conditions.
    DONT_CARE = 0

    #: Condition must be true for the channel.
    TRUE = 1

    #: Condition must be false for the channel.
    FALSE = 2

class PICO_USB_POWER_DELIVERY(ctypes.Structure):
    """
    Structure representing USB Power Delivery status information for a single USB port.

    This structure provides detailed information about the USB Power Delivery
    contract and status for a USB port, including voltage, current limits,
    connection state, and attached device type.

    Attributes:
        valid_ (ctypes.c_uint8):
            Indicates whether the power delivery data is valid (non-zero if valid).
        busVoltagemV_ (ctypes.c_uint32):
            The bus voltage in millivolts.
        rpCurrentLimitmA_ (ctypes.c_uint32):
            The current limit for the Rp resistor in milliamps.
        partnerConnected_ (ctypes.c_uint8):
            Indicates if a partner device is connected (non-zero if connected).
        ccPolarity_ (ctypes.c_uint8):
            The polarity of the CC (Configuration Channel) line.
        attachedDevice_ (ctypes.c_uint8):
            The type of device attached (corresponds to PICO_USB_POWER_DELIVERY_DEVICE_TYPE).
        contractExists_ (ctypes.c_uint8):
            Indicates whether a power contract exists (non-zero if yes).
        currentPdo_ (ctypes.c_uint32):
            The current Power Data Object (PDO) index.
        currentRdo_ (ctypes.c_uint32):
            The current Request Data Object (RDO) index.
    """
    _pack_ = 1

    _fields_ = [
        ("valid_", ctypes.c_uint8),
        ("busVoltagemV_", ctypes.c_uint32),
        ("rpCurrentLimitmA_", ctypes.c_uint32),
        ("partnerConnected_", ctypes.c_uint8),
        ("ccPolarity_", ctypes.c_uint8),
        ("attachedDevice_", ctypes.c_uint8),
        ("contractExists_", ctypes.c_uint8),
        ("currentPdo_", ctypes.c_uint32),
        ("currentRdo_", ctypes.c_uint32),
    ]

class PICO_USB_POWER_DETAILS(ctypes.Structure):
    """
    Structure describing USB power details for a PicoScope device.

    Attributes:
        dataPort_ (PICO_USB_POWER_DELIVERY):
            USB power delivery details related to the device's data port.
        powerPort_ (PICO_USB_POWER_DELIVERY):
            USB power delivery details related to the device's power port.
    """
    _pack_ = 1

    _fields_ = [
        ("dataPort_", PICO_USB_POWER_DELIVERY),
        ("powerPort_", PICO_USB_POWER_DELIVERY),
    ]


class PICO_STREAMING_DATA_INFO(ctypes.Structure):
    """Structure describing streaming data buffer information."""

    #: Structures in ``PicoDeviceStructs.h`` are packed to 1 byte. Mirror this
    #: packing here so the memory layout matches the C definition.
    _pack_ = 1

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
    """Structure describing trigger information for streaming.

    All field names in this structure are defined with a trailing
    underscore so they match the C structure exactly.
    """

    #: Mirror the 1-byte packing of the C ``PICO_STREAMING_DATA_TRIGGER_INFO``
    #: structure.
    _pack_ = 1

    _fields_ = [
        ("triggerAt_", ctypes.c_uint64),
        ("triggered_", ctypes.c_int16),
        ("autoStop_", ctypes.c_int16),
    ]


class PICO_TRIGGER_INFO(ctypes.Structure):
    """Structure describing trigger timing information.

    All fields of this ``ctypes`` structure include a trailing underscore in
    their names. When you receive a :class:`PICO_TRIGGER_INFO` instance from
    :meth:`~pypicosdk.pypicosdk.PicoScopeBase.get_trigger_info` or other
    functions, access the attributes using these exact names, for example
    ``info.triggerTime_``.

    Attributes:
        status_:   :class:`PICO_STATUS` value describing the trigger state. This
            may be a bitwise OR of multiple status flags such as
            ``PICO_DEVICE_TIME_STAMP_RESET`` or
            ``PICO_TRIGGER_TIME_NOT_REQUESTED``.
        segmentIndex_:  Memory segment index from which the information was
            captured.
        triggerIndex_:  Sample index at which the trigger occurred.
        triggerTime_:   Time of the trigger event calculated with sub-sample
            resolution.
        timeUnits_:     Units for ``triggerTime_`` as a
            :class:`PICO_TIME_UNIT` value.
        missedTriggers_: Number of trigger events that occurred between this
            capture and the previous one.
        timeStampCounter_:  Timestamp in samples from the first capture.
    """

    #: Match the packed layout of the corresponding C structure.
    _pack_ = 1

    _fields_ = [
        ("status_", ctypes.c_int32),
        ("segmentIndex_", ctypes.c_uint64),
        ("triggerIndex_", ctypes.c_uint64),
        ("triggerTime_", ctypes.c_double),
        ("timeUnits_", ctypes.c_int32),
        ("missedTriggers_", ctypes.c_uint64),
        ("timeStampCounter_", ctypes.c_uint64),
    ]

TIMESTAMP_COUNTER_MASK: int = (1 << 56) - 1
"""Mask for the 56-bit ``timeStampCounter`` field."""


class PICO_TRIGGER_CHANNEL_PROPERTIES(ctypes.Structure):
    """Trigger threshold configuration for a single channel.

    The fields of this structure mirror the ``PICO_TRIGGER_CHANNEL_PROPERTIES``
    definition in the PicoSDK headers.  Each attribute name ends with an
    underscore so that the names match the underlying C struct when accessed
    from Python.

    Attributes:
        thresholdUpper_: ADC counts for the upper trigger threshold.
        thresholdUpperHysteresis_: Hysteresis applied to ``thresholdUpper_`` in
            ADC counts.
        thresholdLower_: ADC counts for the lower trigger threshold.
        thresholdLowerHysteresis_: Hysteresis applied to ``thresholdLower_`` in
            ADC counts.
        channel_: Input channel that these properties apply to as a
            :class:`CHANNEL` value.
    """

    _pack_ = 1

    _fields_ = [
        ("thresholdUpper_", ctypes.c_int16),
        ("thresholdUpperHysteresis_", ctypes.c_uint16),
        ("thresholdLower_", ctypes.c_int16),
        ("thresholdLowerHysteresis_", ctypes.c_uint16),
        ("channel_", ctypes.c_int32),
    ]


class PICO_CONDITION(ctypes.Structure):
    """Trigger condition used by ``SetTriggerChannelConditions``.

    Each instance defines the state that a particular input source must meet
    for the overall trigger to occur.

    Attributes:
        source_: Channel being monitored as a :class:`CHANNEL` value.
        condition_: Desired state from :class:`PICO_TRIGGER_STATE`.
    """

    #: Ensure this structure matches the 1-byte packed layout used in the
    #: PicoSDK headers.
    _pack_ = 1

    _fields_ = [
        ("source_", ctypes.c_int32),
        ("condition_", ctypes.c_int32),
    ]


class THRESHOLD_DIRECTION(IntEnum):
    """Enumerates trigger threshold directions used with :class:`PICO_DIRECTION`."""

    ABOVE = 0
    BELOW = 1
    RISING = 2
    FALLING = 3
    RISING_OR_FALLING = 4
    ABOVE_LOWER = 5
    BELOW_LOWER = 6
    RISING_LOWER = 7
    FALLING_LOWER = 8
    INSIDE = ABOVE
    OUTSIDE = BELOW
    ENTER = RISING
    EXIT = FALLING
    ENTER_OR_EXIT = RISING_OR_FALLING
    POSITIVE_RUNT = 9
    NEGATIVE_RUNT = 10
    NONE = RISING


class THRESHOLD_MODE(IntEnum):
    """Threshold operation mode values used in :class:`PICO_DIRECTION`."""

    LEVEL = 0
    WINDOW = 1


class PICO_DIRECTION(ctypes.Structure):
    """Direction descriptor for ``SetTriggerChannelDirections``.

    Attributes:
        channel_: Channel index as a :class:`CHANNEL` value.
        direction_: Direction from :class:`PICO_THRESHOLD_DIRECTION`.
        thresholdMode_: Threshold mode from :class:`PICO_THRESHOLD_MODE`.
    """

    _pack_ = 1

    _fields_ = [
        ("channel_", ctypes.c_int32),
        ("direction_", ctypes.c_int32),
        ("thresholdMode_", ctypes.c_int32),
    ]

class PICO_PORT_DIGITAL_CHANNEL(IntEnum):
    """Digital channel identifiers within a port."""

    CHANNEL0 = 0
    CHANNEL1 = 1
    CHANNEL2 = 2
    CHANNEL3 = 3
    CHANNEL4 = 4
    CHANNEL5 = 5
    CHANNEL6 = 6
    CHANNEL7 = 7


class PICO_DIGITAL_DIRECTION(IntEnum):
    """Digital trigger direction settings."""

    DONT_CARE = 0
    DIRECTION_LOW = 1
    DIRECTION_HIGH = 2
    DIRECTION_RISING = 3
    DIRECTION_FALLING = 4
    DIRECTION_RISING_OR_FALLING = 5


class PICO_DIGITAL_CHANNEL_DIRECTIONS(ctypes.Structure):
    """Structure describing a digital channel direction."""

    _pack_ = 1

    _fields_ = [
        ("channel_", ctypes.c_int32),
        ("direction_", ctypes.c_int32),
    ]


class PULSE_WIDTH_TYPE(IntEnum):
    """Pulse width qualifier comparison types."""

    NONE = 0
    LESS_THAN = 1
    GREATER_THAN = 2
    IN_RANGE = 3
    OUT_OF_RANGE = 4


class SWEEP_TYPE(IntEnum):
    """Sweep direction for signal generator."""

    UP = 0
    DOWN = 1
    UPDOWN = 2
    DOWNUP = 3


class PICO_SIGGEN_TRIG_TYPE(IntEnum):
    """Trigger type for the signal generator."""

    PICO_SIGGEN_RISING = 0
    PICO_SIGGEN_FALLING = 1
    PICO_SIGGEN_GATE_HIGH = 2
    PICO_SIGGEN_GATE_LOW = 3


class PICO_SIGGEN_TRIG_SOURCE(IntEnum):
    """Signal generator trigger source options."""

    PICO_SIGGEN_NONE = 0
    PICO_SIGGEN_SCOPE_TRIG = 1
    PICO_SIGGEN_AUX_IN = 2
    PICO_SIGGEN_EXT_IN = 3
    PICO_SIGGEN_SOFT_TRIG = 4
    PICO_SIGGEN_TRIGGER_RAW = 5


class SIGGEN_FILTER_STATE(IntEnum):
    """Output filter state for the signal generator."""

    AUTO = 0
    OFF = 1
    ON = 2


class SIGGEN_PARAMETER(IntEnum):
    """Parameters that can be queried with :func:`siggen_limits`.

    Attributes:
        OUTPUT_VOLTS: 0
        SAMPLE: 1
        BUFFER_LENGTH: 2
    """

    OUTPUT_VOLTS = 0
    SAMPLE = 1
    BUFFER_LENGTH = 2


class TRIGGER_WITHIN_PRE_TRIGGER(IntEnum):
    """Control for :func:`trigger_within_pre_trigger_samples`."""

    PICO_DISABLE = 0
    PICO_ARM = 1


# LED Structures
class PICO_LED_COLOUR_PROPERTIES(ctypes.Structure):
    """This structure is used with psospaSetLedColours() to define
    the color for one LED using hue and saturation (HSV) values
    for the color."""

    _pack_ = 1

    _fields_ = [
        ("led_", ctypes.c_uint32),
        ("hue_", ctypes.c_uint16),
        ("saturation_", ctypes.c_uint8),
    ]

class PICO_LED_STATE_PROPERTIES(ctypes.Structure):
    """This structure is used with set_led_states() to define the
    state for one LED."""
    # _pack_ = 8
    _fields_ = [
        ("led_", ctypes.c_uint32),
        ("state_", ctypes.c_int8),
    ]

led_state_l = Literal['auto', 'off', 'on']
led_state_m = {'auto': -1, 'off': 0, 'on': 1}

led_colours_l = Literal['red', 'green', 'blue', 'yellow', 'pink']
led_colours_m = {'red': 0, 'green': 100, 'blue': 244, 'yellow': 61, 'pink':306}

output_unit_l = Literal['adc', 'mv', 'v']

OutputUnitV_L = Literal['mv', 'v']
OutputUnitV_M = {'mv': 1, 'v': 1000}

# Public names exported by :mod:`pypicosdk.constants` for ``import *`` support.
# This explicit list helps static analyzers like Pylance discover available
# attributes when the parent package re-exports ``pypicosdk.constants`` using
# ``from .constants import *``.
__all__ = [
    'UNIT_INFO',
    'RESOLUTION',
    'TRIGGER_DIR',
    'WAVEFORM',
    'CHANNEL',
    'CHANNEL_NAMES',
    'PICO_CHANNEL_OVERVOLTAGE_TRIPPED',
    'PICO_CHANNEL_FLAGS',
    'COUPLING',
    'RANGE',
    'RANGE_LIST',
    'BANDWIDTH_CH',
    'DATA_TYPE',
    'ACTION',
    'RATIO_MODE',
    'POWER_SOURCE',
    'SAMPLE_RATE',
    'TIME_UNIT',
    '_PICO_TIME_UNIT',
    'PICO_VERSION',
    'PICO_FIRMWARE_INFO',
    'DIGITAL_PORT',
    'DIGITAL_PORT_HYSTERESIS',
    'PICO_CHANNEL_FLAGS',
    'PICO_CONNECT_PROBE_RANGE',
    'PICO_PROBE_RANGE_INFO',
    'PICO_SCALING_FACTORS_VALUES',
    'PICO_SCALING_FACTORS_FOR_RANGE_TYPES_VALUES',
    'AUXIO_MODE',
    'PICO_CHANNEL_OVERVOLTAGE_TRIPPED',
    'TRIGGER_STATE',
    'PICO_USB_POWER_DELIVERY',
    'PICO_USB_POWER_DETAILS',
    'PICO_STREAMING_DATA_INFO',
    'PICO_STREAMING_DATA_TRIGGER_INFO',
    'PICO_TRIGGER_INFO',
    'TIMESTAMP_COUNTER_MASK',
    'PICO_TRIGGER_CHANNEL_PROPERTIES',
    'PICO_CONDITION',
    'THRESHOLD_DIRECTION',
    'THRESHOLD_MODE',
    'PICO_DIRECTION',
    'PICO_PORT_DIGITAL_CHANNEL',
    'PICO_DIGITAL_DIRECTION',
    'PICO_DIGITAL_CHANNEL_DIRECTIONS',
    'PULSE_WIDTH_TYPE',
    'SWEEP_TYPE',
    'PICO_SIGGEN_TRIG_TYPE',
    'PICO_SIGGEN_TRIG_SOURCE',
    'SIGGEN_FILTER_STATE',
    'SIGGEN_PARAMETER',
    'TRIGGER_WITHIN_PRE_TRIGGER',
    'PICO_LED_COLOUR_PROPERTIES',
    'PICO_LED_STATE_PROPERTIES',

    'channel_literal',
    'channel_map',
    'trigger_dir_l',
    'trigger_dir_m',
    'TimeUnit_L',
    'TimeUnitPwr_M',
    'led_channel_l',
    'led_channel_m',
    'led_state_l',
    'led_state_m',
    'led_colours_l',
    'led_colours_m',
    'range_literal',
    'range_map',
    'resolution_literal',
    'resolution_map',
    'waveform_literal',
    'waveform_map',
    'output_unit_l',
]
