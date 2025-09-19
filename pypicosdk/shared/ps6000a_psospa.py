# flake8: noqa
# pylint: skip-file
import ctypes
from warnings import warn
import numpy as np

from .. import constants as cst
from ..constants import *
from ..constants import (
    CHANNEL,
    RANGE,
    COUPLING,
    BANDWIDTH_CH,
    channel_literal,
    channel_map,
    range_literal,
    range_map,
    ProbeScale_L,
    ProbeScale_M,
    RANGE_LIST,
)
from .. import common as cmn
from ..common import (
    PicoSDKException,
    _struct_to_dict,
    _get_literal,
)

from ._protocol import _ProtocolBase

class shared_ps6000a_psospa(_ProtocolBase):
    """Shared functions between ps6000a and psospa"""
    probe_scale: dict[float]

    def get_adc_limits(self) -> tuple:
        """
        Gets the ADC limits for specified devices.

        Currently tested on: 6000a.

        Returns:
                tuple: (minimum value, maximum value)

        Raises:
                PicoSDKException: If device hasn't been initialized.
        """
        if self.resolution is None:
            raise PicoSDKException("Device has not been initialized, use open_unit()")
        min_value = ctypes.c_int32()
        max_value = ctypes.c_int32()
        self._call_attr_function(
            'GetAdcLimits',
            self.handle,
            self.resolution,
            ctypes.byref(min_value),
            ctypes.byref(max_value)
        )
        return min_value.value, max_value.value

    def get_trigger_info(
        self,
        first_segment_index: int = 0,
        segment_count: int = 1,
    ) -> list[dict]:
        """Retrieve trigger timing information for one or more segments.

        Args:
            first_segment_index: Index of the first memory segment to query.
            segment_count: Number of consecutive segments starting at
                ``first_segment_index``.

        Returns:
            List of dictionaries for each trigger event

        Raises:
            PicoSDKException: If the function call fails or preconditions are
                not met.
        """

        info_array = (PICO_TRIGGER_INFO * segment_count)()

        self._call_attr_function(
            "GetTriggerInfo",
            self.handle,
            ctypes.byref(info_array[0]),
            ctypes.c_uint64(first_segment_index),
            ctypes.c_uint64(segment_count),
        )

        # Convert struct to dictionary
        return [_struct_to_dict(info, format=True) for info in info_array]

    def get_values_bulk_async(
        self,
        start_index: int,
        no_of_samples: int,
        from_segment_index: int,
        to_segment_index: int,
        down_sample_ratio: int,
        down_sample_ratio_mode: int,
        lp_data_ready:ctypes.POINTER,
        p_parameter:ctypes.POINTER,
    ) -> None:
        """Begin asynchronous retrieval of values from multiple segments.

        Args:
            start_index: Index within each segment to begin copying from.
            no_of_samples: Number of samples to read from each segment.
            from_segment_index: Index of the first segment to read.
            to_segment_index: Index of the last segment in the range.
            down_sample_ratio: Downsampling ratio to apply before copying.
            down_sample_ratio_mode: Downsampling mode from
                :class:`RATIO_MODE`.
            lp_data_ready: Callback invoked when data is available. The callback
                signature should be ``callback(handle, status, n_samples,
                overflow)``.
            p_parameter: User parameter passed through to ``lp_data_ready``.
        """

        self._call_attr_function(
            "GetValuesBulkAsync",
            self.handle,
            ctypes.c_uint64(start_index),
            ctypes.c_uint64(no_of_samples),
            ctypes.c_uint64(from_segment_index),
            ctypes.c_uint64(to_segment_index),
            ctypes.c_uint64(down_sample_ratio),
            down_sample_ratio_mode,
            lp_data_ready,
            p_parameter,
        )

    def stop_using_get_values_overlapped(self) -> None:
        """Terminate overlapped capture mode.

        Call this when overlapped captures are complete to release any
        resources allocated by :meth:`get_values_overlapped`.
        """

        self._call_attr_function(
            "StopUsingGetValuesOverlapped",
            self.handle,
        )

    def set_trigger_holdoff_counter_by_samples(self, samples: int) -> None:
        """Set the trigger holdoff period in sample intervals.
        Args:
            samples: Number of samples for the holdoff period.
        """

        self._call_attr_function(
            "SetTriggerHoldoffCounterBySamples",
            self.handle,
            ctypes.c_uint64(samples),
        )

    def set_trigger_digital_port_properties(
        self,
        port: int,
        directions: list[PICO_DIGITAL_CHANNEL_DIRECTIONS] | None,
    ) -> None:
        """Configure digital port trigger directions.
        Args:
            port: Digital port identifier.
            directions: Optional list of channel directions to set. ``None`` to
                clear existing configuration.
        """

        if directions:
            array_type = PICO_DIGITAL_CHANNEL_DIRECTIONS * len(directions)
            dir_array = array_type(*directions)
            ptr = dir_array
            count = len(directions)
        else:
            ptr = None
            count = 0

        self._call_attr_function(
            "SetTriggerDigitalPortProperties",
            self.handle,
            port,
            ptr,
            ctypes.c_int16(count),
        )

    def set_pulse_width_qualifier_directions(
        self,
        channel: int,
        direction: int,
        threshold_mode: int,
    ) -> None:
        """Set pulse width qualifier direction for ``channel``.
        If multiple directions are needed, channel, direction and threshold_mode
        can be given a list of values.

        Args:
            channel (CHANNEL | list): Single or list of channels to configure.
            direction (THRESHOLD_DIRECTION | list): Single or list of directions to configure.
            threshold_mode (THRESHOLD_MODE | list): Single or list of threshold modes to configure.
        """
        if type(channel) == list:
            dir_len = len(channel)
            dir_struct = (PICO_DIRECTION * dir_len)()
            for i in range(dir_len):
                print(channel[i], direction[i], threshold_mode[i])
                dir_struct[i] = PICO_DIRECTION(channel[i], direction[i], threshold_mode[i])
        else:
            dir_len = 1
            dir_struct = PICO_DIRECTION(channel, direction, threshold_mode)

        self._call_attr_function(
            "SetPulseWidthQualifierDirections",
            self.handle,
            ctypes.byref(dir_struct),
            ctypes.c_int16(dir_len),
        )

    def set_pulse_width_digital_port_properties(
        self,
        port: int,
        directions: list[PICO_DIGITAL_CHANNEL_DIRECTIONS] | None,
    ) -> None:
        """Configure digital port properties for pulse-width triggering.
        Args:
            port: Digital port identifier.
            directions: Optional list of channel directions to set. ``None`` to
                clear existing configuration.
        """

        if directions:
            array_type = PICO_DIGITAL_CHANNEL_DIRECTIONS * len(directions)
            dir_array = array_type(*directions)
            ptr = dir_array
            count = len(directions)
        else:
            ptr = None
            count = 0

        self._call_attr_function(
            "SetPulseWidthDigitalPortProperties",
            self.handle,
            port,
            ptr,
            ctypes.c_int16(count),
        )

    def trigger_within_pre_trigger_samples(self, state: int) -> None:
        """Control trigger positioning relative to pre-trigger samples.
        Args:
            state: 0 to enable, 1 to disable
        """

        self._call_attr_function(
            "TriggerWithinPreTriggerSamples",
            self.handle,
            state,
        )

    def set_siggen(
            self,
            frequency:float,
            pk2pk:float,
            wave_type:WAVEFORM | waveform_literal,
            offset:float=0.0,
            duty:float=50,
            sweep:bool = False,
            stop_freq:float = None,
            inc_freq:float = 1,
            dwell_time:float = 0.001,
            sweep_type:SWEEP_TYPE = SWEEP_TYPE.UP,
        ) -> dict:
        """Configures and applies the signal generator settings.

        Sets up the signal generator with the specified waveform type, frequency,
        amplitude (peak-to-peak), offset, and duty cycle.

        If sweep is enabled and the sweep-related args are given, the SigGen will sweep.

        Args:
            frequency (float): Signal frequency in hertz (Hz).
            pk2pk (float): Peak-to-peak voltage in volts (V).
            wave_type (WAVEFORM): Waveform type (e.g., WAVEFORM.SINE, WAVEFORM.SQUARE).
            offset (float, optional): Voltage offset in volts (V).
            duty (int or float, optional): Duty cycle as a percentage (0–100).
            sweep: If True, sweep is enabled, fill in the following:
            stop_freq: Frequency to stop sweep at in Hertz (Hz). Defaults to None.
            inc_freq: Frequency to increment (or step) in hertz (Hz). Defaults to 1 Hz.
            dwell_time: Time to wait between frequency steps in seconds (s). Defaults to 1 ms.
            sweep_type: Direction of sweep ``[UP, DOWN, UPDOWN, DOWNUP]``. Defaults to UP.


        Returns:
            dict: Returns dictionary of the actual achieved values.
        """
        # Check if typing Literal
        if wave_type in waveform_map:
            wave_type = waveform_map[wave_type]

        self.siggen_set_waveform(wave_type)
        self.siggen_set_range(pk2pk, offset)
        self.siggen_set_frequency(frequency)
        self.siggen_set_duty_cycle(duty)
        if sweep == True:
            if stop_freq is None:
                raise PicoSDKException("Sweep SigGen set, but no stop_freq declared.")
            self.siggen_frequency_sweep(stop_freq, inc_freq, dwell_time, sweep_type)
            return self.siggen_apply(sweep_enabled=True)
        return self.siggen_apply()

    def siggen_apply(self, enabled=1, sweep_enabled=0, trigger_enabled=0,
                     auto_clock_optimise_enabled=0, override_auto_clock_prescale=0) -> dict:
        """
        Sets the signal generator running using parameters previously configured.

        Args:
                enabled (int, optional): SigGen Enabled,
                sweep_enabled (int, optional): Sweep Enabled,
                trigger_enabled (int, optional): SigGen trigger enabled,
                auto_clock_optimise_enabled (int, optional): Auto Clock Optimisation,
                override_auto_clock_prescale (int, optional): Override Clock Prescale,

        Returns:
                dict: Returns dictionary of the actual achieved values.
        """
        c_frequency = ctypes.c_double()
        c_stop_freq = ctypes.c_double()
        c_freq_incr = ctypes.c_double()
        c_dwell_time = ctypes.c_double()
        self._call_attr_function(
            'SigGenApply',
            self.handle,
            enabled,
            sweep_enabled,
            trigger_enabled,
            auto_clock_optimise_enabled,
            override_auto_clock_prescale,
            ctypes.byref(c_frequency),
            ctypes.byref(c_stop_freq),
            ctypes.byref(c_freq_incr),
            ctypes.byref(c_dwell_time)
        )
        return {'Freq': c_frequency.value,
                'StopFreq': c_stop_freq.value,
                'FreqInc': c_freq_incr.value,
                'dwelltime': c_dwell_time.value}

    def siggen_set_frequency(self, frequency:float) -> None:
        """
        Set frequency of SigGen in Hz.

        Args:
                frequency (int): Frequency in Hz.
        """
        self._call_attr_function(
            'SigGenFrequency',
            self.handle,
            ctypes.c_double(frequency)
        )

    def siggen_set_duty_cycle(self, duty:float) -> None:
        """
        Set duty cycle of SigGen in percentage

        Args:
                duty cycle (int): Duty cycle in %.
        """
        self._call_attr_function(
            'SigGenWaveformDutyCycle',
            self.handle,
            ctypes.c_double(duty)
        )

    def siggen_set_range(self, pk2pk:float, offset:float=0.0):
        """
        Set mV range of SigGen (6000A).

        Args:
                pk2pk (int): Peak to peak of signal in volts (V).
                offset (int, optional): Offset of signal in volts (V).
        """
        self._call_attr_function(
            'SigGenRange',
            self.handle,
            ctypes.c_double(pk2pk),
            ctypes.c_double(offset)
        )

    def _siggen_get_buffer_args(self, buffer:np.ndarray) -> tuple[ctypes.POINTER, int]:
        """
        Takes a np buffer and returns a ctypes compatible pointer and buffer length.

        Args:
            buffer (np.ndarray): numpy buffer of data (between -32767 and +32767)

        Returns:
            tuple[ctypes.POINTER, int]: Buffer pointer and buffer length
        """
        buffer_len = buffer.size
        buffer = np.asanyarray(buffer, dtype=np.int16)
        buffer_ptr = buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
        return buffer_ptr, buffer_len

    def siggen_set_waveform(
            self,
            wave_type: WAVEFORM,
            buffer:np.ndarray|None = None
        ) -> None:
        """
        Set waveform type for SigGen (6000A). If arbitrary mode is selected,
        a buffer of ADC samples is needed.

        Args:
                wave_type (WAVEFORM): Waveform type i.e. WAVEFORM.SINE.
                buffer: np.array buffer to be used in WAVEFORM.ARBITRARY mode.
        """
        # Arbitrary buffer creation
        buffer_len = None
        buffer_ptr = None
        if wave_type is WAVEFORM.ARBITRARY:
            buffer_ptr, buffer_len = self._siggen_get_buffer_args(buffer)


        self._call_attr_function(
            'SigGenWaveform',
            self.handle,
            wave_type,
            buffer_ptr,
            buffer_len
        )

    def siggen_frequency_limits(
        self,
        wave_type: WAVEFORM,
        num_samples: int,
        start_frequency: float,
        sweep_enabled: int,
        manual_dac_clock_frequency: float | None = None,
        manual_prescale_ratio: int | None = None,
    ) -> dict:
        """Query frequency sweep limits for the signal generator.
        Args:
            wave_type: Waveform type.
            num_samples: Number of samples in the arbitrary waveform buffer.
            start_frequency: Starting frequency in Hz.
            sweep_enabled: Whether a sweep is enabled.
            manual_dac_clock_frequency: Optional manual DAC clock frequency.
            manual_prescale_ratio: Optional manual DAC prescale ratio.
        Returns:
            dict: Frequency limit information with keys ``max_stop_frequency``,
            ``min_frequency_step``, ``max_frequency_step``, ``min_dwell_time`` and
            ``max_dwell_time``.
        """

        c_num_samples = ctypes.c_uint64(num_samples)
        c_start_freq = ctypes.c_double(start_frequency)

        if manual_dac_clock_frequency is not None:
            c_manual_clock = ctypes.c_double(manual_dac_clock_frequency)
            c_manual_clock_ptr = ctypes.byref(c_manual_clock)
        else:
            c_manual_clock_ptr = None

        if manual_prescale_ratio is not None:
            c_prescale = ctypes.c_uint64(manual_prescale_ratio)
            c_prescale_ptr = ctypes.byref(c_prescale)
        else:
            c_prescale_ptr = None

        max_stop = ctypes.c_double()
        min_step = ctypes.c_double()
        max_step = ctypes.c_double()
        min_dwell = ctypes.c_double()
        max_dwell = ctypes.c_double()

        self._call_attr_function(
            "SigGenFrequencyLimits",
            self.handle,
            wave_type,
            ctypes.byref(c_num_samples),
            ctypes.byref(c_start_freq),
            ctypes.c_int16(sweep_enabled),
            c_manual_clock_ptr,
            c_prescale_ptr,
            ctypes.byref(max_stop),
            ctypes.byref(min_step),
            ctypes.byref(max_step),
            ctypes.byref(min_dwell),
            ctypes.byref(max_dwell),
        )

        return {
            "max_stop_frequency": max_stop.value,
            "min_frequency_step": min_step.value,
            "max_frequency_step": max_step.value,
            "min_dwell_time": min_dwell.value,
            "max_dwell_time": max_dwell.value,
        }

    def siggen_limits(self, parameter: SIGGEN_PARAMETER) -> dict:
        """Query signal generator parameter limits.
        Args:
            parameter: Signal generator parameter to query.
        Returns:
            dict: Dictionary with keys ``min``, ``max`` and ``step``.
        """

        min_val = ctypes.c_double()
        max_val = ctypes.c_double()
        step = ctypes.c_double()
        self._call_attr_function(
            "SigGenLimits",
            self.handle,
            parameter,
            ctypes.byref(min_val),
            ctypes.byref(max_val),
            ctypes.byref(step),
        )

        return {"min": min_val.value, "max": max_val.value, "step": step.value}

    def siggen_frequency_sweep(
        self,
        stop_frequency_hz: float,
        frequency_increment: float,
        dwell_time_s: float,
        sweep_type: SWEEP_TYPE,
    ) -> None:
        """Configure frequency sweep parameters.
        Args:
            stop_frequency_hz: End frequency of the sweep in Hz.
            frequency_increment: Increment value in Hz.
            dwell_time_s: Time to dwell at each frequency in seconds.
            sweep_type: Sweep direction.
        """

        self._call_attr_function(
            "SigGenFrequencySweep",
            self.handle,
            ctypes.c_double(stop_frequency_hz),
            ctypes.c_double(frequency_increment),
            ctypes.c_double(dwell_time_s),
            sweep_type,
        )

    def siggen_phase(self, delta_phase: int) -> None:
        """Set the signal generator phase using ``delta_phase``.

        The signal generator uses direct digital synthesis (DDS) with a 32-bit phase accumulator that indicates the
        present location in the waveform. The top bits of the phase accumulator are used as an index into a buffer
        containing the arbitrary waveform. The remaining bits act as the fractional part of the index, enabling highresolution control of output frequency and allowing the generation of lower frequencies.
        The signal generator steps through the waveform by adding a deltaPhase value between 1 and
        phaseAccumulatorSize-1 to the phase accumulator every dacPeriod (= 1/dacFrequency).

        Args:
            delta_phase: Phase offset to apply.
        """

        self._call_attr_function(
            "SigGenPhase",
            self.handle,
            ctypes.c_uint64(delta_phase),
        )

    def siggen_phase_sweep(
        self,
        stop_delta_phase: int,
        delta_phase_increment: int,
        dwell_count: int,
        sweep_type: SWEEP_TYPE,
    ) -> None:
        """Configure a phase sweep for the signal generator.
        Args:
            stop_delta_phase: End phase in DAC counts.
            delta_phase_increment: Increment value in DAC counts.
            dwell_count: Number of DAC cycles to dwell at each phase step.
            sweep_type: Sweep direction.
        """

        self._call_attr_function(
            "SigGenPhaseSweep",
            self.handle,
            ctypes.c_uint64(stop_delta_phase),
            ctypes.c_uint64(delta_phase_increment),
            ctypes.c_uint64(dwell_count),
            sweep_type,
        )

    def siggen_pause(self) -> None:
        """Pause the signal generator."""

        self._call_attr_function("SigGenPause", self.handle)

    def siggen_restart(self) -> None:
        """Restart the signal generator after a pause."""

        self._call_attr_function("SigGenRestart", self.handle)

    def siggen_software_trigger_control(self, trigger_state: int) -> None:
        """Control software triggering for the signal generator.
        Args:
            trigger_state: ``1`` to enable the software trigger, ``0`` to disable.
        """

        self._call_attr_function(
            "SigGenSoftwareTriggerControl",
            self.handle,
            trigger_state,
        )

    def siggen_trigger(
        self,
        trigger_type: int,
        trigger_source: int,
        cycles: int,
        auto_trigger_ps: int = 0,
    ) -> None:
        """Configure signal generator triggering.
        Args:
            trigger_type: Trigger type to use.
            trigger_source: Source for the trigger.
            cycles: Number of cycles before the trigger occurs.
            auto_trigger_ps: Time in picoseconds before auto-triggering.
        """

        self._call_attr_function(
            "SigGenTrigger",
            self.handle,
            trigger_type,
            trigger_source,
            ctypes.c_uint64(cycles),
            ctypes.c_uint64(auto_trigger_ps),
        )

    def set_siggen_awg(
            self,
            frequency:float,
            pk2pk:float,
            buffer:np.ndarray|list,
            offset:float=0.0,
            duty:float=50,
            sweep:bool = False,
            stop_freq:float = None,
            inc_freq:float = 1,
            dwell_time:float = 0.001,
            sweep_type:SWEEP_TYPE = SWEEP_TYPE.UP,
        ) -> dict:
        """
        Arbitrary Waveform Generation - Generates a signal from a given buffer.

        Sets up the signal generator with a specified frequency, amplitude (peak-to-peak),
        offset, and duty cycle.

        If sweep is enabled and the sweep-related args are given, the SigGen will sweep.

        Args:
            frequency (float): Signal frequency in hertz (Hz).
            pk2pk (float): Peak-to-peak voltage in volts (V).
            buffer (np.ndarray | list): _description_
            offset (float, optional): Voltage offset in volts (V). Defaults to 0.0.
            duty (float, optional): Duty cycle as a percentage (0–100). Defaults to 50.
            sweep (bool, optional): If True, sweep is enabled, fill in the following:
            stop_freq (float, optional): Frequency to stop sweep at in Hertz (Hz). Defaults to None.
            inc_freq (float, optional): Frequency to increment (or step) in hertz (Hz). Defaults to 1.
            dwell_time (float, optional): Time to wait between frequency steps in seconds (s). Defaults to 0.001.
            sweep_type (SWEEP_TYPE, optional): Direction of sweep ``[UP, DOWN, UPDOWN, DOWNUP]``. Defaults to UP.

        Raises:
            PicoSDKException: _description_

        Returns:
            dict: _description_
        """

        self.siggen_set_waveform(WAVEFORM.ARBITRARY, buffer=buffer)
        self.siggen_set_range(pk2pk, offset)
        self.siggen_set_frequency(frequency)
        self.siggen_set_duty_cycle(duty)
        if sweep == True:
            if stop_freq is None:
                raise PicoSDKException("Sweep SigGen set, but no stop_freq declared.")
            self.siggen_frequency_sweep(stop_freq, inc_freq, dwell_time, sweep_type)
            return self.siggen_apply(sweep_enabled=True)
        return self.siggen_apply()

    def get_analogue_offset_limits(
        self, range: PICO_CONNECT_PROBE_RANGE, coupling: COUPLING
    ) -> tuple[float, float]:
        """Get the allowed analogue offset range for ``range`` and ``coupling``."""

        max_v = ctypes.c_double()
        min_v = ctypes.c_double()
        self._call_attr_function(
            "GetAnalogueOffsetLimits",
            self.handle,
            range,
            coupling,
            ctypes.byref(max_v),
            ctypes.byref(min_v),
        )
        return max_v.value, min_v.value

    def set_channel(
        self,
        channel: CHANNEL | channel_literal,
        range: RANGE | range_literal = RANGE.V1,  # pylint: disable=W0622
        enabled: bool = True,
        coupling: COUPLING = COUPLING.DC,
        offset: float = 0.0,
        bandwidth: BANDWIDTH_CH = BANDWIDTH_CH.FULL,
        probe_scale: float = 1.0,
    ) -> None:
        """
        Enable/disable a channel and specify certain variables i.e. range, coupling, offset, etc.

        For the ps6000a drivers, this combines set_channel_on/off to a single function.
        Set channel on/off by adding enabled=True/False

        Args:
                channel (CHANNEL): Channel to setup.
                range (RANGE): Voltage range of channel.
                enabled (bool, optional): Enable or disable channel.
                coupling (COUPLING, optional): AC/DC/DC 50 Ohm coupling of selected channel.
                offset (int, optional): Analog offset in volts (V) of selected channel.
                bandwidth (BANDWIDTH_CH, optional): Bandwidth of channel (selected models).
                probe_scale (float, optional): Probe attenuation factor e.g. 10 for x10 probe.
                    Default value of 1.0 (x1).
        """
        # Check if typing Literals
        channel = _get_literal(channel, channel_map)
        range = _get_literal(range, range_map)

        # Add probe scaling
        self.probe_scale[channel] = probe_scale
        if probe_scale != 1.0:
            warn(
                f'Ensure selected channel range of {cst.range_literal.__args__[range]} ' +
                f'accounts for attenuation of x{probe_scale} at scope input',
                cmn.ProbeScaleWarning)

        # Update ylims
        self._set_ylim(range)

        if enabled:
            self.set_channel_on(channel, range, coupling, offset, bandwidth)
        else:
            self.set_channel_off(channel)

    def set_channel_on(self, channel, range, coupling=COUPLING.DC, offset=0.0, bandwidth=BANDWIDTH_CH.FULL):
        """Sets a channel to ON at a specified range (6000E)"""
        self.range[channel] = range
        status = self._call_attr_function(
            'SetChannelOn',
            self.handle,
            channel,
            coupling,
            range,
            ctypes.c_double(offset),
            bandwidth
        )
        return status

    def set_channel_off(self, channel):
        """Sets a channel to OFF (6000E)"""
        status = self._call_attr_function(
            'SetChannelOff',
            self.handle,
            channel
        )
        return status

    def set_aux_io_mode(self, mode: AUXIO_MODE) -> None:

        """Configure the AUX IO connector using ``ps6000aSetAuxIoMode``.

        Args:
            mode: Requested AUXIO mode from :class:`~pypicosdk.constants.AUXIO_MODE`.
        """

        self._call_attr_function(
            "SetAuxIoMode",
            self.handle,
            mode,
        )

    def memory_segments_by_samples(self, n_samples: int) -> int:
        """Set the samples per memory segment.

        This wraps ``ps6000aMemorySegmentsBySamples`` which divides the
        capture memory so that each segment holds ``n_samples`` samples.

        Args:
            n_samples: Number of samples per segment.

        Returns:
            int: Number of segments the memory was divided into.
        """

        max_segments = ctypes.c_uint64()
        self._call_attr_function(
            "MemorySegmentsBySamples",
            self.handle,
            ctypes.c_uint64(n_samples),
            ctypes.byref(max_segments),
        )
        return max_segments.value

    def query_max_segments_by_samples(
        self,
        n_samples: int,
        n_channel_enabled: int,
    ) -> int:
        """Return the maximum number of segments for a given sample count.

        Wraps ``ps6000aQueryMaxSegmentsBySamples`` to query how many memory
        segments can be configured when each segment stores ``n_samples``
        samples.

        Args:
            n_samples: Number of samples per segment.
            n_channel_enabled: Number of enabled channels.

        Returns:
            int: Maximum number of segments available.

        Raises:
            PicoSDKException: If the device has not been opened.
        """

        if self.resolution is None:
            raise PicoSDKException("Device has not been initialized, use open_unit()")

        max_segments = ctypes.c_uint64()
        self._call_attr_function(
            "QueryMaxSegmentsBySamples",
            self.handle,
            ctypes.c_uint64(n_samples),
            ctypes.c_uint32(n_channel_enabled),
            ctypes.byref(max_segments),
            self.resolution,
        )
        return max_segments.value

    def reset_channels_and_report_all_channels_overvoltage_trip_status(self) -> list[PICO_CHANNEL_OVERVOLTAGE_TRIPPED]:
        """Reset channels and return overvoltage trip status for each.
        Wraps ``ps6000aResetChannelsAndReportAllChannelsOvervoltageTripStatus``.
        Returns:
            list[PICO_CHANNEL_OVERVOLTAGE_TRIPPED]: Trip status for all channels.
        """

        n_channels = len(CHANNEL_NAMES)
        status_array = (PICO_CHANNEL_OVERVOLTAGE_TRIPPED * n_channels)()
        self._call_attr_function(
            "ResetChannelsAndReportAllChannelsOvervoltageTripStatus",
            self.handle,
            status_array,
            ctypes.c_uint8(n_channels),
        )

        return list(status_array)

    def set_digital_port_on(
        self,
        port: DIGITAL_PORT,
        logic_threshold_level: list[int],
        hysteresis: DIGITAL_PORT_HYSTERESIS,
    ) -> None:
        """Enable a digital port using ``ps6000aSetDigitalPortOn``.

        Args:
            port: Digital port to enable.
            logic_threshold_level: Threshold level for each pin in millivolts.
            hysteresis: Hysteresis level applied to all pins.
        """

        level_array = (ctypes.c_int16 * len(logic_threshold_level))(
            *logic_threshold_level
        )

        self._call_attr_function(
            "SetDigitalPortOn",
            self.handle,
            port,
            level_array,
            len(logic_threshold_level),
            hysteresis,
        )

    def set_digital_port_off(self, port: DIGITAL_PORT) -> None:
        """Disable a digital port using ``ps6000aSetDigitalPortOff``."""

        self._call_attr_function(
            "SetDigitalPortOff",
            self.handle,
            port,
        )

    def get_maximum_available_memory(self) -> int:
        """Return the maximum sample depth for the current resolution.
        Wraps ``ps6000aGetMaximumAvailableMemory`` to query how many samples
        can be captured at ``self.resolution``.
        Returns:
            int: Maximum number of samples supported.
        Raises:
            PicoSDKException: If the device has not been opened.
        """

        if self.resolution is None:
            raise PicoSDKException("Device has not been initialized, use open_unit()")

        max_samples = ctypes.c_uint64()
        self._call_attr_function(
            "GetMaximumAvailableMemory",
            self.handle,
            ctypes.byref(max_samples),
            self.resolution,
        )
        return max_samples.value

    def report_all_channels_overvoltage_trip_status(
        self,
    ) -> list[PICO_CHANNEL_OVERVOLTAGE_TRIPPED]:
        """Return the overvoltage trip status for each channel.
        This wraps ``ps6000aReportAllChannelsOvervoltageTripStatus`` to
        query whether any channel's 50 Ω input protection has tripped.
        Returns:
            list[PICO_CHANNEL_OVERVOLTAGE_TRIPPED]: Trip status for all
            channels.
        """

        n_channels = len(CHANNEL_NAMES)
        array_type = PICO_CHANNEL_OVERVOLTAGE_TRIPPED * n_channels
        status_array = array_type()

        self._call_attr_function(
            "ReportAllChannelsOvervoltageTripStatus",
            self.handle,
            status_array,
            n_channels,
        )

        return list(status_array)


__all__ = ['shared_ps6000a_psospa']