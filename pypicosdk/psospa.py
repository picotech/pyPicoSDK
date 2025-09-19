"""Copyright (C) 2018-2022 Pico Technology Ltd. See LICENSE file for terms."""

import ctypes
from typing import override, Literal
import json

from .constants import *
from .constants import (
    TIME_UNIT
)
from .common import PicoSDKException
from .base import PicoScopeBase
from .shared.ps6000a_psospa import shared_ps6000a_psospa

class psospa(PicoScopeBase, shared_ps6000a_psospa):
    """PicoScope OSP (A) API specific functions"""

    @override
    def __init__(self, *args, **kwargs):
        super().__init__("psospa", *args, **kwargs)

    @override
    def open_unit(self, serial_number:str=None, resolution:RESOLUTION | resolution_literal=0) -> PICO_USB_POWER_DETAILS:
        """
        Opens a connection to a PicoScope unit and retrieves USB power details.

        Args:
            serial_number (str, optional):
                Serial number of the specific PicoScope unit to open (e.g., "JR628/0017").
                If None, the first available unit is opened.
            resolution (RESOLUTION | resolution_literal, optional):
                The desired device resolution. Can be a RESOLUTION enum or literal integer.
                Defaults to 0.

        Returns:
            A structure containing USB power information of the opened device.
        """
        # If using Literals, convert to int
        if resolution in resolution_map:
            resolution = resolution_map[resolution]

        if serial_number is not None:
            serial_number = serial_number.encode()

        usb_power_struct = PICO_USB_POWER_DETAILS()

        self._call_attr_function(
            'OpenUnit',
            ctypes.byref(self.handle),
            serial_number, 
            resolution,
            ctypes.byref(usb_power_struct)
        )
        self.resolution = resolution
        self.set_all_channels_off()
        self.min_adc_value, self.max_adc_value =super().get_adc_limits()
        self.n_channels = self.get_variant_details()['NumberOfAnalogueChannels']

        return usb_power_struct

    @override
    def set_channel_on(
        self, 
        channel:CHANNEL, 
        range:RANGE, 
        coupling:COUPLING=COUPLING.DC, 
        offset:float=0, 
        bandwidth:BANDWIDTH_CH=BANDWIDTH_CH.FULL,
        range_type:PICO_PROBE_RANGE_INFO=PICO_PROBE_RANGE_INFO.X1_PROBE_NV
        ) -> int:
        """
        Enable and configure a specific channel on the device with given parameters.

        Args:
            channel (CHANNEL):
                The channel to enable (e.g., CHANNEL.A, CHANNEL.B).
            range (RANGE):
                The input voltage range to set for the channel.
            coupling (COUPLING, optional):
                The coupling mode to use (e.g., DC, AC). Defaults to DC.
            offset (float, optional):
                DC offset to apply to the channel input, in volts. Defaults to 0.
            bandwidth (BANDWIDTH_CH, optional):
                Bandwidth limit setting for the channel. Defaults to full bandwidth.
            range_type (PICO_PROBE_RANGE_INFO, optional):
                Specifies the probe range type. Defaults to X1 probe (no attenuation).
        """
        self.range[channel] = range

        range_max = ctypes.c_int64(RANGE_LIST[range] * 1_000_000)
        range_min = ctypes.c_int64(-range_max.value)

        status = self._call_attr_function(
            'SetChannelOn',
            self.handle,
            channel,
            coupling,
            range_min,
            range_max,
            range_type,
            ctypes.c_double(offset),
            bandwidth
        )
        return status
    
    @override
    def get_nearest_sampling_interval(self, interval_s:float, round_faster:int=True) -> dict:
        """
        Calculate the nearest valid sampling interval supported by the device.

        Args:
            interval_s (float): Desired sampling interval in seconds.
            round_faster (int, optional): If non-zero (True), rounds the sampling 
                interval to the nearest interval that is equal to or faster (shorter) 
                than requested.
                If zero (False), rounds to the nearest interval equal to or slower.
                Defaults to True.

        Returns:
            dict:
                Dictionary containing:
                - "timebase" (int): The device timebase value corresponding to
                the nearest supported sampling interval.
        """
        timebase = ctypes.c_uint32()
        time_interval = ctypes.c_double()
        self._call_attr_function(
            'NearestSampleIntervalStateless',
            self.handle,
            self._get_enabled_channel_flags(),
            ctypes.c_double(interval_s),
            ctypes.c_uint8(round_faster),
            self.resolution,
            ctypes.byref(timebase),
            ctypes.byref(time_interval),
        )
        return {"timebase": timebase.value,
                "actual_sample_interval": (timebase.value / TIME_UNIT.PS)}

    def get_scaling_values(self, n_channels: int = 8) -> list[PICO_SCALING_FACTORS_VALUES]:
        """Return probe scaling factors for each channel.
        Args:
            n_channels: Number of channel entries to retrieve.
        Returns:
            list[PICO_SCALING_FACTORS_VALUES]: Scaling factors for ``n_channels`` channels.
        """

        array_type = PICO_SCALING_FACTORS_VALUES * n_channels
        values = array_type()
        self._call_attr_function(
            "GetScalingValues",
            self.handle,
            values,
            ctypes.c_int16(n_channels),
        )
        return list(values)

    def get_variant_details(
            self, 
            variant_name:str|None|Literal["all-series"] = None, 
            buffer_size:int=32768,
            style:Literal["json", "schema"]="json",
        ) -> dict:
        """
        Retrieve detailed variant information from the device and return it in a specified style.

        Args:
            variant_name (str | None | Literal["all-series"], optional):
                The variant to query.
                - If None, uses the connected device's variant name from
                `get_unit_info(UNIT_INFO.PICO_VARIANT_INFO)`.
                - If "all-series", retrieves information for all supported device variants.
            buffer_size (int, optional):
                Initial size in bytes of the buffer allocated to receive the JSON output.
                Defaults to 32,768 bytes. Increase if the output is unexpectedly truncated.
            style (Literal["json", "schema"], optional):
                Specifies the format of the returned data.
                - "json" returns variant details as JSON data.
                - "schema" returns the JSON schema describing the data structure.
                Defaults to "json".

        Returns:
            dict | list:
                Parsed JSON data representing the variant details or schema,
                depending on the chosen style.
        """
        buffer = ctypes.create_string_buffer(buffer_size)
        buffer_size = ctypes.c_int32(buffer_size)
        if variant_name is None:
            variant_name = self.get_unit_info(UNIT_INFO.PICO_VARIANT_INFO).encode()
        else:
            variant_name = variant_name.encode()

        status = self._call_attr_function(
            "GetVariantDetails",
            variant_name,
            len(variant_name),
            ctypes.byref(buffer),
            ctypes.byref(buffer_size),
            {"json": 0, "schema": 1}[style],
        )
        return json.loads(buffer.value.decode())

    def set_led_brightness(self, brightness:int) -> None:
        """
        Set the brightness of all configurable LEDs. 

        It will not take affect until one of the following 
        functions are ran:
         - run_block_capture()
         - run_streaming()
         - set_aux_io_mode()
         - siggen_apply()

        Args:
            brightness (int): Brightness percentage [0 - 100]
        """
        self._call_attr_function(
            'SetLedBrightness',
            self.handle,
            brightness,
        )

    def set_all_led_colours(self, hue:int|led_colours_l, saturation:int=100) -> None:
        """
        Sets all LED's on the PicoScope to a single colour

        Args:
            hue (int | str): Colour as a hue in [0-359] or a 
                basic colour from the following:
                ['red', 'green', 'blue', 'yellow', 'pink']

            saturation (int, optional): Saturation of the colour [0-100]. Defaults to 100.
        """
        led_list = list(led_channel_m.keys())
        led_list = led_list[:self.n_channels] + led_list[-2:]
        self.set_led_colours(led_list, [hue] * len(led_list), [saturation] * len(led_list))

    def set_led_colours(
            self, 
            led:led_channel_l | list[led_channel_l], 
            hue:int | led_colours_l | list[int] | list[led_colours_l], 
            saturation:int | list[int]
        ) -> None:
        """Sets the colour of the selected LED using HUE and Saturation

        It will not take affect until one of the following 
        functions are ran:
         - run_block_capture()
         - run_streaming()
         - set_aux_io_mode()
         - siggen_apply()

        Args:
            led (str|list[str]): The selected LED. Must be one or a list of these values:
                `'A'`, `'B'`, `'C'`, `'D'`, `'E'`, `'F'`, `'G'`, `'H'`, `'AWG'`, `'AUX'`.
            hue (int|list[int]): Colour as a hue in [0-359] or a 
                basic colour from the following:
                ['red', 'green', 'blue', 'yellow', 'pink']
            saturation (int|list[int]): Saturation of the LED, [0-100].
        """
        # if isinstance(hue, str):
        #     hue = led_colours_m[hue]

        if not isinstance(led, list):
            led = [led]
            hue = [hue]
            saturation = [saturation]
        
        if isinstance(hue[0], str):
            hue = [led_colours_m[i] for i in hue]

        array_len = len(led)
        array_struct = (PICO_LED_COLOUR_PROPERTIES * array_len)()

        for i in range(array_len):
            array_struct[i] = PICO_LED_COLOUR_PROPERTIES(
                led_channel_m[led[i]],
                hue[i],
                saturation[i]
            )

        self._call_attr_function(
            "SetLedColours",
            self.handle,
            ctypes.byref(array_struct),
            array_len,
        )
    
    def set_all_led_states(self,state:str|led_state_l):
        """
        Sets the state of all LED's on the PicoScope.

        Args:
            state (str): ['auto', 'on', 'off']
        """
        led_list = list(led_channel_m.keys())
        led_list = led_list[:self.n_channels] + led_list[-2:]
        self.set_led_states(led_list, [state] * len(led_list))

    def set_led_states(self, led:str|led_channel_l|list[led_channel_l], state:str|led_state_l|list[led_state_l]):
        """
        Sets the state for a selected LED. Between default behaviour (auto),
        on or off.
        
        Args:
            led (str): The selected LED. Must be one of these values:
                `'A'`, `'B'`, `'C'`, `'D'`, `'E'`, `'F'`, `'G'`, `'H'`, `'AWG'`, `'AUX'`.
            state (str): State of selected LED: `'auto'`, `'off'`, `'on'`.
        """
        if not isinstance(led, list):
            led = [led]
            state = [state]

        array_len = len(led)
        array_struct = (PICO_LED_STATE_PROPERTIES * array_len)()

        for i in range(array_len):
            array_struct[i] = PICO_LED_STATE_PROPERTIES(
                led_channel_m[led[i]],
                led_state_m[state[i]]
            )

        self._call_attr_function(
            'SetLedStates',
            self.handle,
            ctypes.byref(array_struct), 
            ctypes.c_uint32(array_len)
        )
