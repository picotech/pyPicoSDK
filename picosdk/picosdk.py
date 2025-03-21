import ctypes
from .picosdk_error_list import ERROR_STRING
import os


class UNIT_INFO:
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
    RES_5000A_8BIT = 0
    RES_5000A_12BIT = 1
    RES_5000A_14BIT = 2
    RES_5000A_15BIT = 3
    RES_5000A_16BIT = 4

    RES_6000A_8BIT = 0
    RES_6000A_10BIT = 10
    RES_6000A_12BIT = 1

FLEXRES_5000A_8BIT = 0
FLEXRES_5000A_12BIT = 1
FLEXRES_5000A_14BIT = 2
FLEXRES_5000A_15BIT = 3
FLEXRES_5000A_16BIT = 4

FLEXRES_6000A_8BIT = 0
FLEXRES_6000A_10BIT = 10
FLEXRES_6000A_12BIT = 1

class TRIGGER_DIR:
    ABOVE = 0
    BELOW = 1
    RISING = 2
    FALLING = 3
    RISING_OR_FALLING = 4

class WAVEFORM:
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


CHANNEL_A = 0
CHANNEL_B = 1
CHANNEL_C = 2 
CHANNEL_D = 3
CHANNEL_E = 4
CHANNEL_F = 5
CHANNEL_G = 6 
CHANNEL_H = 7

AC_COUPLING = 0
DC_COUPLING = 1
DC_50OHM_COUPLING = 2

RANGE_10MV = 0
RANGE_20MV = 1
RANGE_50MV = 2
RANGE_100MV = 3
RANGE_200MV = 4
RANGE_500MV = 5
RANGE_1V = 6
RANGE_2V = 7
RANGE_5V = 8
RANGE_10V = 9
RANGE_20V = 10
RANGE_50V = 11

RANGE_LIST = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000]

class PICO_BW:
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

suppress_warnings = True

# Exceptions
class PicoSDKNotFoundException(Exception):
    pass

class PicoSDKException(Exception):
    pass


# General Functions
def _get_lib_path() -> str:
    """
    Checks for and returns the PicoSDK lib location from Program Files.

    Returns
    -------
    str
        File path to PicoSDK folder.

    Raises
    ------
    PicoSDKNotFoundException
        If the PicoSDK library is not found.
    """

    program_files = os.environ.get("ProgramFiles")
    lib_location = os.path.join(program_files, "Pico Technology/SDK/lib")
    if not os.path.exists(lib_location):
        raise PicoSDKNotFoundException("PicoSDK is not found at 'Program Files/Pico Technology/SDK/lib'")
    return lib_location


# PicoScope Classes
class PicoScopeBase:
    # Class Functions
    def __init__(self):
        self.handle = ctypes.c_short()
        self.range = {}
        self.resolution = None
        self.max_adc_value = None
        self.min_adc_value = None
    
    def __exit__(self):
        self.close_unit()

    def __del__(self):
        self.close_unit()

    # General Functions
    def _get_attr_function(self, function_name: str) -> ctypes.CDLL:
        """
        Returns ctypes function based on sub-class prefix name.

        For example, `_get_attr_function("OpenUnit")` will return `self.dll.ps####aOpenUnit()`.

        Parameters
        ----------
        function_name : str
            PicoSDK function name, e.g., "OpenUnit".

        Returns
        -------
        ctypes.CDLL
            CDLL function for the specified name.
        """
        return getattr(self.dll, self._unit_prefix_n + function_name)
    
    def _error_handler(self, status: int) -> 0:
        """
        Checks status code against error list; raises an exception if not 0.

        Errors such as `SUPPLY_NOT_CONNECTED` are returned as warnings.

        Parameters
        ----------
        status : int
            Returned status value from PicoSDK.

        Returns
        -------
        int
            0 if there are no errors.

        Raises
        ------
        PicoSDKException
            Pythonic exception based on status value.
        """
        error_code = ERROR_STRING[status]
        if status != 0:
            if status in [POWER_SOURCE.SUPPLY_NOT_CONNECTED]:
                print('WARNING: Power supply not connected')
                return 0
            self.close_unit()
            raise PicoSDKException(error_code)
        return 0
    
    def _call_attr_function(self, function_name:str, *args):
        """
        Calls a specific attribute function with the provided arguments.

        Parameters
        ----------
        function_name : str
            PicoSDK function suffix.

        Returns
        -------
        int
            Return 0 if OK.
        """
        attr_function = self._get_attr_function(function_name)
        status = attr_function(*args)
        self._error_handler(status)
        return status

    # General PicoSDK functions    
    def open_unit(self, serial_number:int=None, resolution:RESOLUTION=0) -> int:
        """
        Opens PicoScope unit.

        Parameters
        ----------
        serial_number : int, optional
            Serial number of specific unit, e.g., JR628/0017. Defaults to None.
        resolution : RESOLUTION, optional
            Resolution of device. Defaults to the lowest available resolution, e.g., 8-bit.

        Returns
        -------
        int
            Return 0 if OK.
        """
        if serial_number is not None:
            serial_number = serial_number.encode()
        self._call_attr_function(
            'OpenUnit',
            ctypes.byref(self.handle),
            serial_number, 
            resolution
        )
        self.resolution = resolution
        return 0
    
    def close_unit(self) -> int:

        attr_function = self._get_attr_function('CloseUnit')
        return attr_function(self.handle)

    def is_ready(self) -> int:
        """
        Closes PicoScope unit.

        Returns
        -------
        int
            Return 0 if OK.
        """
        ready = ctypes.c_int16()
        attr_function = getattr(self.dll, self._unit_prefix_n + "IsReady")
        while True:
            status = attr_function(
                self.handle, 
                ctypes.byref(ready)
            )
            self._error_handler(status)
            if ready.value != 0:
                break
        return status
    
    # Get information from PicoScope
    def get_unit_info(self, unit_info: UNIT_INFO) -> str:
        """
        Get specified information from unit. Use UNIT_INFO.XXXX or integer.

        Parameters
        ----------
        unit_info : UNIT_INFO
            For example, UNIT_INFO.PICO_BATCH_AND_SERIAL

        Returns
        -------
        str
            Returns data from device.
        """
        string = ctypes.create_string_buffer(16)
        string_length = ctypes.c_int16(32)
        required_size = ctypes.c_int16(32)
        status = self._call_attr_function(
            'GetUnitInfo',
            self.handle,
            string,
            string_length,
            ctypes.byref(required_size),
            ctypes.c_uint32(unit_info)
        )
        return string.value.decode()
    
    def get_unit_serial(self) -> str:
        """
        Get and return batch and serial of unit.

        Returns
        -------
        str
            Returns serial, e.g., "JR628/0017".
        """
        return self.get_unit_info(UNIT_INFO.PICO_BATCH_AND_SERIAL)
    
    def _get_timebase(self, timebase: int, samples: int, segment:int=0) -> dict:
        """
        This function calculates the sampling rate and maximum number of 
        samples for a given timebase under the specified conditions.

        Parameters
        ----------
        timebase : int
            Selected timebase multiplier (refer to programmer's guide).
        samples : int
            Number of samples.
        segment : int, optional
            The index of the memory segment to use. Defaults to 0.

        Returns
        -------
        dict
            Returns interval (ns) and max samples as a dictionary.
        """
        time_interval_ns = ctypes.c_double()
        max_samples = ctypes.c_uint64()
        attr_function = getattr(self.dll, self._unit_prefix_n + 'GetTimebase')
        status = attr_function(
            self.handle,
            timebase,
            samples,
            ctypes.byref(time_interval_ns),
            ctypes.byref(max_samples),
            segment
        )
        self._error_handler(status)
        return {"Interval(ns)": time_interval_ns.value, 
                "Samples":          max_samples.value}
    
    def _get_timebase_2(self, timebase: int, samples: int, segment:int=0):
        """
        Calculates the sampling rate and maximum number of samples for a given
        timebase under the specified conditions.

        Parameters
        ----------
        timebase : int
            Selected timebase multiplier (refer to programmer's guide).
        samples : int
            Number of samples.
        segment : int, optional
            Index of the memory segment to use. Defaults to 0.

        Returns
        -------
        dict
            Dictionary containing:
            - 'interval' (ns): Time interval between samples.
            - 'max_samples': Maximum number of samples.
        """

        time_interval_ns = ctypes.c_float()
        max_samples = ctypes.c_int32()
        attr_function = getattr(self.dll, self._unit_prefix_n + 'GetTimeBase2')
        status = attr_function(
            self.handle,
            timebase,
            samples,
            ctypes.byref(time_interval_ns),
            ctypes.byref(max_samples),
            segment
        )
        self._error_handler(status)
        return {"Interval(ns)": time_interval_ns.value, 
                "Samples":          max_samples.value}
    
    def _get_adc_limits(self) -> tuple:
        """
        Gets the ADC limits for specified devices.

        Currently tested on: 6000a.

        Returns
        -------
        tuple
            (minimum value, maximum value)

        Raises
        ------
        PicoSDKException
            If device hasn't been initialized.
        """
        if self.resolution is None:
            raise PicoSDKException("Device has not been initialized, use open_unit()")
        min_value = ctypes.c_int32()
        max_value = ctypes.c_int32()
        attr_function = self._get_attr_function('GetAdcLimits')
        status = attr_function(
            self.handle,
            self.resolution,
            ctypes.byref(min_value),
            ctypes.byref(max_value)
        )
        self._error_handler(status)
        return min_value.value, max_value.value
    
    def _get_maximum_adc_value(self) -> int:
        """
        Gets the ADC limits for specified devices.

        Currently tested on: 5000a.

        Returns
        -------
        int
            Maximum ADC value.
        """
        max_value = ctypes.c_int16()
        attr_function = self._get_attr_function('MaximumValue')
        status = attr_function(
            self.handle,
            ctypes.byref(max_value)
        )
        self._error_handler(status)
        return max_value.value
    
    # Data conversion ADC/mV & ctypes/int 
    def mv_to_adc(self, mv, channel_range):
        """
        Converts a millivolt (mV) value to an ADC value based on the device's
        maximum ADC range.

        Parameters
        ----------
        mv : float
            Voltage in millivolts to be converted.
        channel_range : int
            Index or key representing the selected channel voltage range.

        Returns
        -------
        int
            ADC value corresponding to the input millivolt value.
        """

        channel_range_mv = RANGE_LIST[channel_range]
        return int((mv / channel_range_mv) * self.max_adc_value)
    
    def adc_to_mv(self, adc: list, channel_range: int):
        """
        Converts an ADC value to mV - based on maximum ADC value

        Parameters
        ----------
        adc
            _description_
        channel_range
            _description_

        Returns
        -------
            _description_
        """
        "Converts ADC value to mV - based on maximum ADC value"
        channel_range_mv = float(RANGE_LIST[channel_range])
        return (float(adc) / float(self.max_adc_value)) * channel_range_mv
    
    def buffer_adc_to_mv(self, buffer: list, channel: str) -> list:
        """Converts an ADC buffer list to mV list"""
        return [self.adc_to_mv(sample, self.range[channel]) for sample in buffer]
    
    def buffer_adc_to_mv_multiple_channels(self, channels_buffer: dict) -> dict:
        "Converts dict of multiple channels adc values to millivolts (mV)"
        for channel in channels_buffer:
            channels_buffer[channel] = self.buffer_adc_to_mv(channels_buffer[channel], channel)
        return channels_buffer
    
    def buffer_ctypes_to_list(self, ctypes_list):
        "Converts a ctype dataset into a python list of samples"
        return [sample for sample in ctypes_list]
    
    def buffer_ctype_to_list_for_multiple_channels(self, channels_buffer):
        """
        Takes a ctypes channel dictionary buffer and converts into a integer array.
        i.e. {0: <ctypes_array>, 1: <ctypes_array>} -> {0: [1, 0], 1: [5, 7]}
        """
        for channel in channels_buffer:
            channels_buffer[channel] = self.buffer_ctypes_to_list(channels_buffer[channel])
        return channels_buffer

    # Set methods for PicoScope configuration    
    def change_power_source(self, state: POWER_SOURCE) -> 0:
        """Change power source of device 
        i.e. POWER_SOURCE.SUPPLY_NOT_CONNECTED on 5000D device

        :param POWER_SOURCE state: Select power source for device
        :return 0: Return 0 if OK
        """
        attr_func = self._get_attr_function('ChangePowerSource')
        status = attr_func(
            self.handle,
            state
        )
        self._error_handler(status)
        return 0

    def _set_channel_on(self, channel, range, coupling=DC_COUPLING, offset=0.0, bandwidth=PICO_BW.FULL):
        """Sets a channel to ON at a specified range (6000E)"""
        self.range[channel] = range
        attr_function = getattr(self.dll, self._unit_prefix_n + 'SetChannelOn')
        status = attr_function(
            self.handle,
            channel,
            coupling,
            range,
            ctypes.c_double(offset),
            bandwidth
        )
        return self._error_handler(status)
    
    def _set_channel_off(self, channel):
        """Sets a channel to OFF (6000E)"""
        attr_function = getattr(self.dll, self._unit_prefix_n + 'SetChannelOff')
        status = attr_function(
            self.handle, 
            channel
        )
        return self._error_handler(status)
    
    def _set_channel(self, channel, range, enabled=True, coupling=DC_COUPLING, offset=0.0):
        """Set a channel ON with a specified range (5000D)"""
        self.range[channel] = range
        status = self.dll.ps5000aSetChannel(
            self.handle,
            channel,
            enabled,
            coupling,
            range,
            ctypes.c_float(offset)
        )
        return self._error_handler(status)
    
    def set_simple_trigger(self, channel, threshold_mv, enable=True, direction=TRIGGER_DIR.RISING, delay=0, auto_trigger_ms=3000):
        """Sets up a simple trigger from a specified channel and threshold in mV"""
        threshold_adc = self.mv_to_adc(threshold_mv, self.range[channel])
        attr_function = getattr(self.dll, self._unit_prefix_n + 'SetSimpleTrigger')
        status = attr_function(
            self.handle,
            enable,
            channel,
            threshold_adc,
            direction,
            delay,
            auto_trigger_ms
        )
        return self._error_handler(status)
    
    def _set_data_buffer_ps5000a(self, channel, samples, segment=0, ratio_mode=0):
        """Set data buffer (5000D)"""
        buffer = (ctypes.c_int16 * samples)
        buffer = buffer()
        attr_function = self._get_attr_function('SetDataBuffer')
        status = attr_function(
            self.handle,
            channel,
            ctypes.byref(buffer),
            samples,
            segment,
            ratio_mode
        )
        self._error_handler(status)
        return buffer
    
    def _set_data_buffer_ps6000a(self, channel, samples, segment=0, datatype=DATA_TYPE.INT16_T, ratio_mode=RATIO_MODE.RAW, action=ACTION.CLEAR_ALL | ACTION.ADD):
        """Set data buffer (6000E)"""
        if datatype == DATA_TYPE.INT8_T:     buffer = (ctypes.c_int8 * samples)
        elif datatype == DATA_TYPE.INT16_T:  buffer = (ctypes.c_int16 * samples)
        elif datatype == DATA_TYPE.INT32_T:  buffer = (ctypes.c_int32 * samples)
        elif datatype == DATA_TYPE.INT64_T:  buffer = (ctypes.c_int64 * samples)
        elif datatype == DATA_TYPE.UINT32_T: buffer = (ctypes.c_uint32 * samples)
        else: raise PicoSDKException("Invalid datatype selected for buffer")

        buffer = buffer()
        attr_function = self._get_attr_function('SetDataBuffer')
        status = attr_function(
            self.handle,
            channel,
            ctypes.byref(buffer),
            samples,
            datatype,
            segment,
            ratio_mode,
            action
        )
        self._error_handler(status)
        return buffer
 
    def set_data_buffer_for_enabled_channels(self, samples):
        channels_buffer = {}
        for channel in self.range:
            # set_data_buffer() specified in sub-class
            channels_buffer[channel] = self.set_data_buffer(channel, samples)
        return channels_buffer
    
    # Run functions
    def run_block_capture(self, timebase, samples, pre_trig_percent=50, segment=0):
        """Run block with specified timebase and samples"""
        pre_samples = int((samples * pre_trig_percent) / 100)
        post_samples = int(samples - pre_samples)
        time_indisposed_ms = ctypes.c_int32()
        attr_function = self._get_attr_function('RunBlock')
        status = attr_function(
            self.handle,
            pre_samples,
            post_samples,
            timebase,
            ctypes.byref(time_indisposed_ms),
            segment,
            None,
            None
        )
        self._error_handler(status)
        return time_indisposed_ms.value
    
    def get_values(self, samples, start_index=0, segment=0, ratio=0, ratio_mode=RATIO_MODE.RAW):
        """When ready, get values from device"""
        self.is_ready()
        total_samples = ctypes.c_uint32(samples)
        overflow = ctypes.c_int16()
        self._call_attr_function(
            'GetValues',
            self.handle, 
            start_index,
            ctypes.byref(total_samples),
            ratio,
            ratio_mode,
            segment,
            ctypes.byref(overflow)
        )
        return total_samples.value
    
    def run_block(self, timebase, samples) -> dict:
        """Performs a simple block capture once channels and trigger is setup"""
        # run block capture
        self.run_block_capture(timebase, samples)
        
        # buffer = set data buffer (all setup channels)
        channels_buffer = self.set_data_buffer_for_enabled_channels(samples)

        # get values
        self.get_values(samples)

        # Convert buffer from ctypes array to python list
        channels_buffer = self.channels_buffer_ctype_to_list(channels_buffer)

        return channels_buffer
    
    # Siggen Functions
    def _siggen_apply(self, enabled=1, sweep_enabled=0, trigger_enabled=0, 
                     auto_clock_optimise_enabled=0, override_auto_clock_prescale=0) -> dict:
        """Sets the signal generator running using parameters previously configured.

        :param int enabled: SigGen Enabled, defaults to 1
        :param int sweep_enabled: Sweep Enabled, defaults to 0
        :param int trigger_enabled: SigGen trigger enabled, defaults to 0
        :param int auto_clock_optimise_enabled: Auto Clock Optimisation, defaults to 0
        :param int override_auto_clock_prescale: Override Clock Prescale, defaults to 0
        :return dict: Returns dictionary of the actual achieved values
        """
        freq = ctypes.c_double()
        stop_freq = ctypes.c_double()
        freq_incr = ctypes.c_double()
        dwell_time = ctypes.c_double()
        self._call_attr_function(
            'SigGenApply',
            self.handle,
            enabled,
            sweep_enabled,
            trigger_enabled,
            auto_clock_optimise_enabled,
            override_auto_clock_prescale,
            ctypes.byref(freq),
            ctypes.byref(stop_freq),
            ctypes.byref(freq_incr),
            ctypes.byref(dwell_time)
        )
        return {'Freq': freq.value,
                'StopFreq': stop_freq.value,
                'FreqInc': freq_incr.value,
                'dwelltime': dwell_time.value}
    
    def _siggen_set_frequency(self, frequency:int) -> 0:
        """Set the frequency of the SigGen

        :param int frequency: Specified frequency of SigGen
        :return 0: Return 0 if OK
        """
        self._call_attr_function(
            'SigGenFrequency',
            self.handle,
            frequency
        )
        return 0
    
    def _siggen_set_range(self, pk2pk, offset=0):
        self._call_attr_function(
            'SigGenRange',
            self.handle,
            pk2pk,
            offset
        )
        return 0
    
    def _siggen_set_waveform(self, wavetype=WAVEFORM.SINE):
        self._call_attr_function(
            'SigGenRange',
            self.handle,
            wavetype,
            0,
            0
        )
        return 0


class ps6000a(PicoScopeBase):
    dll = ctypes.CDLL(os.path.join(_get_lib_path(), "ps6000a.dll"))
    _unit_prefix_n = "ps6000a"

    def open_unit(self, serial_number:str=None, resolution=RESOLUTION.RES_6000A_8BIT):
        """Opens the PicoScope unit

        Parameters
        ----------
        serial_number : str, optional
            _description_, by default None
        resolution : _type_, optional
            _description_, by default RESOLUTION.RES_6000A_8BIT

        Returns
        -------
        _type_
            _description_
        """
        status = super().open_unit(serial_number, resolution)
        self.min_adc_value, self.max_adc_value =super()._get_adc_limits()
        return status

    def set_channel_on(self, channel, range, coupling=DC_COUPLING, offset=0, bandwidth=PICO_BW.FULL):
        return super()._set_channel_on(channel, range, coupling, offset, bandwidth)

    def set_channel_off(self, channel):
        return super()._set_channel_off(channel)
    
    def get_timebase(self, timebase, samples, segment=0):
        return super()._get_timebase(timebase, samples, segment)
    
    def set_data_buffer(self, channel, samples, segment=0, datatype=DATA_TYPE.INT16_T, ratio_mode=RATIO_MODE.RAW, action=ACTION.CLEAR_ALL | ACTION.ADD):
        return super()._set_data_buffer_ps6000a(channel, samples, segment, datatype, ratio_mode, action)
    
class ps5000a(PicoScopeBase):
    dll = ctypes.CDLL(os.path.join(_get_lib_path(), "ps5000a.dll"))
    _unit_prefix_n = "ps5000a"

    def open_unit(self, serial_number=None, resolution=RESOLUTION):
        status = super().open_unit(serial_number, resolution)
        self.max_adc_value = super()._get_maximum_adc_value()
        return status

    def set_channel(self, channel, range, enabled=True, coupling=DC_COUPLING, offset=0):
        return super()._set_channel(channel, range, enabled, coupling, offset)
    
    def get_timebase(self, timebase, samples, segment=0):
        return super()._get_timebase_2(timebase, samples, segment)
    
    def set_data_buffer(self, channel, samples, segment=0, ratio_mode=0):
        return super()._set_data_buffer_ps5000a(channel, samples, segment, ratio_mode)



"""Timebase calculation for external use WIP"""
def timebase_calc_6000a(timebase: int):
    """Hello World

    :param int timebase: _description_
    :return _type_: _description_
    """
    if timebase <= 4:
        return print((pow(2, timebase))/5_000_000_000)
    else:
        return print((timebase - 4) / 156_250_000)

# def timebase_calc_6428E_D(timebase: int):
#     if timebase <= 5:
#         return to_engineering_notation((pow(2, timebase)) / 10_000_000_000)
#     else:
#         return to_engineering_notation((timebase - 5) / 156_250_000)
    
# def to_engineering_notation(value):
#     prefixes = {
#         -12: 'p',  # pico
#         -9: 'n',   # nano
#         -6: 'u',   # micro
#         -3: 'm',   # milli
#          0: '',    # unit
#          3: 'k',   # kilo
#          6: 'M',   # mega
#          9: 'G',   # giga
#         12: 'T',   # tera
#     }
    
#     if value == 0:
#         return "0"
    
#     exponent = 0
#     scaled_value = 0
#     exponent = value/10
#     print(exponent)
    
#     return 0
#     # return f"{scaled_value:.3f}{prefixes[exponent]}"
