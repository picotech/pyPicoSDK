/****************************************************************************
 *
 * Filename:    psospaApi.h
 * Copyright:   Pico Technology Limited 2002 - 2024
 * Description:
 *
 * This header defines the interface to driver routines for the
 *  PicoScope psospa range of PC Oscilloscopes.
 *
 ****************************************************************************/
#ifndef __PSOSPAPI_H__
#define __PSOSPAPI_H__

#include <stdint.h>

#include "PicoStatus.h"
#include "PicoDeviceEnums.h"
#include "PicoDeviceStructs.h"
#include "PicoCallback.h"
#include "PicoVersion.h"

#ifdef __cplusplus
#define PREF0 extern "C"
#define TYPE_ENUM
#else
#define PREF0
#define TYPE_ENUM enum
#endif

#ifdef WIN32
#ifdef PREF1
#undef PREF1
#endif
#ifdef PREF2
#undef PREF2
#endif
#ifdef PREF3
#undef PREF3
#endif
//If you are dynamically linking psospa.dll into your project #define DYNLINK here>
#ifdef DYNLINK
#define PREF1 typedef
#define PREF2
#define PREF3(x) (__stdcall * x)
#else
#define PREF1
#ifdef _USRDLL
#define PREF2 __declspec(dllexport) __stdcall
#else
#define PREF2 __declspec(dllimport) __stdcall
#endif
#define PREF3(x) x
#endif
#define PREF4 __stdcall
#else
#ifdef DYNLINK
#define PREF1 typedef
#define PREF2
#define PREF3(x) (*x)
#else
#ifdef _USRDLL
#define PREF1 __attribute__((visibility("default")))
#else
#define PREF1
#endif
#define PREF2
#define PREF3(x) x
#endif
#define PREF4
#endif

typedef void(PREF4* psospaBlockReady)(int16_t handle, PICO_STATUS status, PICO_POINTER pParameter);

typedef void(PREF4* psospaDataReady)(int16_t handle,
                                     PICO_STATUS status,
                                     uint64_t noOfSamples,
                                     int16_t overflow,
                                     PICO_POINTER pParameter);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaOpenUnit)(int16_t* handle,
                                                    int8_t* serial,
                                                    PICO_DEVICE_RESOLUTION resolution,
                                                    PICO_USB_POWER_DETAILS* powerDetails);

// This function retrieves information about the specified oscilloscope or driver software.
// If the device fails to open or no device is opened, it is still possible to read the driver version.
//
// parameters:
// handle: identifies the device from which information is required. If an invalid handle is passed, only the driver versions can be read.
// string: on exit, the unit information string selected specified by the info argument. If string is NULL, only requiredSize is returned.
// stringLength: the maximum number of 8-bit integers (int8_t) that may be written to string.
// requiredSize: on exit, the required length of the string array.
// info: a number specifying what information is required.
//
// return:
// PICO_OK
// PICO_INVALID_HANDLE
// PICO_NULL_PARAMETER
// PICO_INVALID_INFO
// PICO_INFO_UNAVAILABLE
// PICO_DRIVER_FUNCTION
// PICO_STRING_BUFFER_TO_SMALL (stringLength is insufficient for the required data, but non-zero)
PREF0 PREF1 PICO_STATUS PREF2
  PREF3(psospaGetUnitInfo)(int16_t handle, int8_t* string, int16_t stringLength, int16_t* requiredSize, PICO_INFO info);

// This function returns a string (in the requested 'textFormat' format) containing specification details of the psospa variant requested by 'variantName'.
// The data is copied into the location provided by 'outputString' only if a non-null location is provided and outputStringLength is sufficient.
// If making an initial call to find the required buffer size, call with outputStringLength set to zero. outputString may be nullptr in this case and PICO_OK will still be returned.
//
// Parameters:
// variantName: the string variant name for which data is being requested, for example "3418E".
// variantNameLength: the size of the variantName array.
// outputString: the location to copy the 'textFormat' formatted object string to.
// outputStringLength: the size of the outputString array. On return, the size of the buffer that has been copied if successful, or otherwise the size of the buffer that would be required to contain the requested data.
// textFormat: the text format type to request. Supplying PICO_JSON_DATA will return the given device’s capabilities structured in json. Supplying PICO_JSON_SCHEMA will return the given device’s json schema.
//
// Return:
// PICO_OK
// PICO_INVALID_PARAMETER
// PICO_INVALID_VARIANT
// PICO_NULL_PARAMETER (a required parameter is nullptr)
// PICO_STRING_BUFFER_TO_SMALL (outputStringLength is insufficient for the required data, but non-zero)
PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetVariantDetails)(const int8_t* variantName,
                                                             int16_t variantNameLength,
                                                             int8_t* outputString,
                                                             int32_t* outputStringLength,
                                                             PICO_TEXT_FORMAT textFormat);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaCloseUnit)(int16_t handle);

// This function allows you to divide the memory into a number of segments so that the scope can store several waveforms sequentially. 
// When the scope is opened, the number of segments defaults to 1, meaning that each capture fills the scope's available memory. 
PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaMemorySegments)(int16_t handle, uint64_t nSegments, uint64_t* nMaxSamples);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaMemorySegmentsBySamples)(int16_t handle,
                                                                   uint64_t nSamples,
                                                                   uint64_t* nMaxSegments);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetMaximumAvailableMemory)(int16_t handle,
                                                                     uint64_t* nMaxSamples,
                                                                     PICO_DEVICE_RESOLUTION resolution);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaQueryMaxSegmentsBySamples)(int16_t handle,
                                                                     uint64_t nSamples,
                                                                     uint32_t nChannelEnabled,
                                                                     uint64_t* nMaxSegments,
                                                                     PICO_DEVICE_RESOLUTION resolution);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetChannelOn)(int16_t handle,
                                                        PICO_CHANNEL channel,
                                                        PICO_COUPLING coupling,
                                                        int64_t rangeMin,
                                                        int64_t rangeMax,
                                                        PICO_PROBE_RANGE_INFO rangeType,
                                                        double analogueOffset,
                                                        PICO_BANDWIDTH_LIMITER bandwidth);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetChannelOff)(int16_t handle, PICO_CHANNEL channel);

// This function switches on a digital port and sets its corresponding logic threshold voltage.
//
// Parameters:
// handle: the device identifier returned by psospaOpenUnit().
// port: identifies the digital port on the oscilloscope:
//   PICO_PORT0: channels D0-D7
//   PICO_PORT1: channels D8-D15
// logicThresholdLevelVolts: the threshold voltage for the port in volts used to distinguish the digital 0 and 1 states.
//
// Return:
// PICO_OK - The PicoScope is functioning correctly.
// PICO_MEMORY_FAIL - Not enough memory could be allocated on the host machine.
// PICO_INVALID_HANDLE - There is no device with the handle value passed.
// PICO_DRIVER_FUNCTION - A driver function has already been called and not yet finished. Only one call to the driver can be made at any one time.
// PICO_INTERNAL_ERROR - The driver has experienced an unknown error and is unable to recover from this error.
// PICO_INVALID_DIGITAL_PORT - The requested digital port number is out of range or not supported for the connected device.
PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetDigitalPortOn)(int16_t handle,
                                                            PICO_CHANNEL port,
                                                            double logicThresholdLevelVolts);

// This function switches off a digital port.
//
// Parameters:
// handle: the device identifier returned by psospaOpenUnit().
// port: identifies the digital port on the oscilloscope:
//   PICO_PORT0: channels D0-D7
//   PICO_PORT1: channels D8-D15
//
// Return:
// PICO_OK - The PicoScope is functioning correctly.
// PICO_MEMORY_FAIL - Not enough memory could be allocated on the host machine.
// PICO_INVALID_HANDLE - There is no device with the handle value passed.
// PICO_DRIVER_FUNCTION - A driver function has already been called and not yet finished. Only one call to the driver can be made at any one time.
// PICO_INTERNAL_ERROR - The driver has experienced an unknown error and is unable to recover from this error.
// PICO_INVALID_DIGITAL_PORT - The requested digital port number is out of range or not supported for the connected device.
PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetDigitalPortOff)(int16_t handle, PICO_CHANNEL port);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetTimebase)(int16_t handle,
                                                       uint32_t timebase,
                                                       uint64_t noSamples,
                                                       double* timeIntervalNanoseconds,
                                                       uint64_t* maxSamples,
                                                       uint64_t segmentIndex);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenWaveform)(int16_t handle,
                                                          PICO_WAVE_TYPE waveType,
                                                          int16_t* buffer,
                                                          uint64_t bufferLength);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenRange)(int16_t handle, double peakToPeakVolts, double offsetVolts);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenWaveformDutyCycle)(int16_t handle, double dutyCyclePercent);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenTrigger)(int16_t handle,
                                                         PICO_SIGGEN_TRIG_TYPE triggerType,
                                                         PICO_SIGGEN_TRIG_SOURCE triggerSource,
                                                         uint64_t cycles,
                                                         uint64_t autoTriggerPicoSeconds);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenFrequency)(int16_t handle, double frequencyHz);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenFrequencySweep)(int16_t handle,
                                                                double stopFrequencyHz,
                                                                double frequencyIncrement,
                                                                double dwellTimeSeconds,
                                                                PICO_SWEEP_TYPE sweepType);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenPhase)(int16_t handle, uint64_t deltaPhase);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenPhaseSweep)(int16_t handle,
                                                            uint64_t stopDeltaPhase,
                                                            uint64_t deltaPhaseIncrement,
                                                            uint64_t dwellCount,
                                                            PICO_SWEEP_TYPE sweepType);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenSoftwareTriggerControl)(int16_t handle,
                                                                        PICO_SIGGEN_TRIG_TYPE triggerState);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenApply)(int16_t handle,
                                                        int16_t sigGenEnabled,
                                                        int16_t sweepEnabled,
                                                        int16_t triggerEnabled,
                                                        double* frequency,
                                                        double* stopFrequency,
                                                        double* frequencyIncrement,
                                                        double* dwellTime);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenLimits)(int16_t handle,
                                                        PICO_SIGGEN_PARAMETER parameter,
                                                        double* minimumPermissibleValue,
                                                        double* maximumPermissibleValue,
                                                        double* step);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenFrequencyLimits)(int16_t handle,
                                                                  PICO_WAVE_TYPE waveType,
                                                                  uint64_t* numSamples,
                                                                  double* minFrequencyOut,
                                                                  double* maxFrequencyOut,
                                                                  double* minFrequencyStepOut,
                                                                  double* maxFrequencyStepOut,
                                                                  double* minDwellTimeOut,
                                                                  double* maxDwellTimeOut);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenPause)(int16_t handle);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSigGenRestart)(int16_t handle);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetSimpleTrigger)(int16_t handle,
                                                            int16_t enable,
                                                            PICO_CHANNEL source,
                                                            int16_t threshold,
                                                            PICO_THRESHOLD_DIRECTION direction,
                                                            uint64_t delay,
                                                            uint32_t autoTriggerMicroSeconds);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaTriggerWithinPreTriggerSamples)(int16_t handle,
                                                                          PICO_TRIGGER_WITHIN_PRE_TRIGGER state);

PREF0 PREF1 PICO_STATUS PREF2
  PREF3(psospaSetTriggerChannelProperties)(int16_t handle,
                                            PICO_TRIGGER_CHANNEL_PROPERTIES* channelProperties,
                                            int16_t nChannelProperties,
                                            uint32_t autoTriggerMicroSeconds);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetTriggerChannelConditions)(int16_t handle,
                                                                       PICO_CONDITION* conditions,
                                                                       int16_t nConditions,
                                                                       PICO_ACTION action);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetTriggerChannelDirections)(int16_t handle,
                                                                       PICO_DIRECTION* directions,
                                                                       int16_t nDirections);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetTriggerDelay)(int16_t handle, uint64_t delay);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetTriggerHoldoffCounterBySamples)(int16_t handle, uint64_t holdoffSamples);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetPulseWidthQualifierProperties)(int16_t handle,
                                                                            uint32_t lower,
                                                                            uint32_t upper,
                                                                            PICO_PULSE_WIDTH_TYPE type);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetPulseWidthQualifierConditions)(int16_t handle,
                                                                            PICO_CONDITION* conditions,
                                                                            int16_t nConditions,
                                                                            PICO_ACTION action);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetPulseWidthQualifierDirections)(int16_t handle,
                                                                            PICO_DIRECTION* directions,
                                                                            int16_t nDirections);

// This function is used to enable or disable triggering on digital ports and set its parameters.
//
// Parameters:
// handle: the device identifier returned by psospaOpenUnit().
// port: identifies the digital port on the oscilloscope:
//   PICO_PORT0: channels D0-D7
//   PICO_PORT1: channels D8-D15
// directions: a pointer to an array of PICO_DIGITAL_CHANNEL_DIRECTIONS structures specifying the channel directions.
// nDirections: the number of elements in the directions array.
//
// Return:
// PICO_OK
// PICO_INVALID_HANDLE
// PICO_INVALID_DIGITAL_PORT
// PICO_INVALID_DIGITAL_CHANNEL
// PICO_INVALID_DIGITAL_TRIGGER_DIRECTION
// PICO_DRIVER_FUNCTION
// PICO_MEMORY_FAIL
// PICO_INTERNAL_ERROR
PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetTriggerDigitalPortProperties)(int16_t handle,
                                                                           PICO_CHANNEL port,
                                                                           PICO_DIGITAL_CHANNEL_DIRECTIONS* directions,
                                                                           int16_t nDirections);

// This function sets the individual digital channels' starting event(s) for the pulse width trigger.
//
// Parameters:
// handle: the device identifier returned by psospaOpenUnit().
// port: identifies the digital port on the oscilloscope:
//   PICO_PORT0: channels D0-D7
//   PICO_PORT1: channels D8-D15
// directions: a pointer to an array of PICO_DIGITAL_CHANNEL_DIRECTIONS structures specifying the channel directions.
// nDirections: the number of elements in the directions array.
//
// Return:
// PICO_OK
// PICO_INVALID_HANDLE
// PICO_INVALID_DIGITAL_PORT
// PICO_INVALID_DIGITAL_CHANNEL
// PICO_INVALID_DIGITAL_TRIGGER_DIRECTION
// PICO_DRIVER_FUNCTION
// PICO_MEMORY_FAIL
// PICO_INTERNAL_ERROR
PREF0 PREF1 PICO_STATUS PREF2
  PREF3(psospaSetPulseWidthDigitalPortProperties)(int16_t handle,
                                                  PICO_CHANNEL port,
                                                  PICO_DIGITAL_CHANNEL_DIRECTIONS* directions,
                                                  int16_t nDirections);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetTriggerTimeOffset)(int16_t handle,
                                                                int64_t* time,
                                                                PICO_TIME_UNITS* timeUnits,
                                                                uint64_t segmentIndex);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetValuesTriggerTimeOffsetBulk)(int16_t handle,
                                                                          int64_t* times,
                                                                          PICO_TIME_UNITS* timeUnits,
                                                                          uint64_t fromSegmentIndex,
                                                                          uint64_t toSegmentIndex);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetDataBuffer)(int16_t handle,
                                                         PICO_CHANNEL channel,
                                                         PICO_POINTER buffer,
                                                         uint64_t nSamples,
                                                         PICO_DATA_TYPE dataType,
                                                         uint64_t waveform,
                                                         PICO_RATIO_MODE downSampleRatioMode,
                                                         PICO_ACTION action);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetDataBuffers)(int16_t handle,
                                                          PICO_CHANNEL channel,
                                                          PICO_POINTER bufferMax,
                                                          PICO_POINTER bufferMin,
                                                          uint64_t nSamples,
                                                          PICO_DATA_TYPE dataType,
                                                          uint64_t waveform,
                                                          PICO_RATIO_MODE downSampleRatioMode,
                                                          PICO_ACTION action);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaRunBlock)(int16_t handle,
                                                    uint64_t noOfPreTriggerSamples,
                                                    uint64_t noOfPostTriggerSamples,
                                                    uint32_t timebase,
                                                    double* timeIndisposedMs,
                                                    uint64_t segmentIndex,
                                                    psospaBlockReady lpReady,
                                                    PICO_POINTER pParameter);

// This function may be used instead of a callback function to receive data from psospaRunBlock(). To use this method, pass a NULL pointer as the lpReady argument to psospaRunBlock(). 
// You must then poll the driver to see if it has finished collecting the requested samples.
//
// Parameters:
// handle: the device identifier returned by psospaOpenUnit().
// ready: on output indicates the state of the collection. If zero, the device is still collecting. If non - zero, the device has finished collecting and psospaGetValues() can be 
// used to retrieve the data.
//
// Return:
// PICO_OK
// PICO_INVALID_HANDLE
// PICO_NULL_PARAMETER
PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaIsReady)(int16_t handle, int16_t* ready);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaRunStreaming)(int16_t handle,
                                                        double* sampleInterval,
                                                        PICO_TIME_UNITS sampleIntervalTimeUnits,
                                                        uint64_t maxPreTriggerSamples,
                                                        uint64_t maxPostTriggerSamples,
                                                        int16_t autoStop,
                                                        uint64_t downSampleRatio,
                                                        PICO_RATIO_MODE downSampleRatioMode);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetStreamingLatestValues)(int16_t handle,
                                                                    PICO_STREAMING_DATA_INFO* streamingDataInfo,
                                                                    uint64_t nStreamingDataInfos,
                                                                    PICO_STREAMING_DATA_TRIGGER_INFO* triggerInfo);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaNoOfStreamingValues)(int16_t handle, uint64_t* noOfValues);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetValues)(int16_t handle,
                                                     uint64_t startIndex,
                                                     uint64_t* noOfSamples,
                                                     uint64_t downSampleRatio,
                                                     PICO_RATIO_MODE downSampleRatioMode,
                                                     uint64_t segmentIndex,
                                                     int16_t* overflow);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetValuesBulk)(int16_t handle,
                                                         uint64_t startIndex,
                                                         uint64_t* noOfSamples,
                                                         uint64_t fromSegmentIndex,
                                                         uint64_t toSegmentIndex,
                                                         uint64_t downSampleRatio,
                                                         PICO_RATIO_MODE downSampleRatioMode,
                                                         int16_t* overflow);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetValuesAsync)(int16_t handle,
                                                          uint64_t startIndex,
                                                          uint64_t noOfSamples,
                                                          uint64_t downSampleRatio,
                                                          PICO_RATIO_MODE downSampleRatioMode,
                                                          uint64_t segmentIndex,
                                                          PICO_POINTER lpDataReady,
                                                          PICO_POINTER pParameter);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetValuesBulkAsync)(int16_t handle,
                                                              uint64_t startIndex,
                                                              uint64_t noOfSamples,
                                                              uint64_t fromSegmentIndex,
                                                              uint64_t toSegmentIndex,
                                                              uint64_t downSampleRatio,
                                                              PICO_RATIO_MODE downSampleRatioMode,
                                                              PICO_POINTER lpDataReady,
                                                              PICO_POINTER pParameter);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetValuesOverlapped)(int16_t handle,
                                                               uint64_t startIndex,
                                                               uint64_t* noOfSamples,
                                                               uint64_t downSampleRatio,
                                                               PICO_RATIO_MODE downSampleRatioMode,
                                                               uint64_t fromSegmentIndex,
                                                               uint64_t toSegmentIndex,
                                                               int16_t* overflow);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaStopUsingGetValuesOverlapped)(int16_t handle);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetNoOfCaptures)(int16_t handle, uint64_t* nCaptures);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetNoOfProcessedCaptures)(int16_t handle, uint64_t* nProcessedCaptures);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaStop)(int16_t handle);

// This function sets the number of captures to be collected in one run of rapid block mode. If you do not call this function before a run, the driver will capture only one waveform.
PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetNoOfCaptures)(int16_t handle, uint64_t nCaptures);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetTriggerInfo)(int16_t handle,
                                                          PICO_TRIGGER_INFO* triggerInfo,
                                                          uint64_t firstSegmentIndex,
                                                          uint64_t segmentCount);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaEnumerateUnits)(int16_t* count, int8_t* serials, int16_t* serialLth);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaPingUnit)(int16_t handle);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetAnalogueOffsetLimits)(int16_t handle,
                                                                   int64_t rangeMin,
                                                                   int64_t rangeMax,
                                                                   PICO_PROBE_RANGE_INFO rangeType,
                                                                   PICO_COUPLING coupling,
                                                                   double* maximumVoltage,
                                                                   double* minimumVoltage);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetMinimumTimebaseStateless)(int16_t handle,
                                                                       PICO_CHANNEL_FLAGS enabledChannelFlags,
                                                                       uint32_t* timebase,
                                                                       double* timeInterval,
                                                                       PICO_DEVICE_RESOLUTION resolution);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaNearestSampleIntervalStateless)(int16_t handle,
                                                                          PICO_CHANNEL_FLAGS enabledChannelFlags,
                                                                          double timeIntervalRequested,
                                                                          uint8_t roundFaster,
                                                                          PICO_DEVICE_RESOLUTION resolution,
                                                                          uint32_t* timebase,
                                                                          double* timeIntervalAvailable);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetDeviceResolution)(int16_t handle, PICO_DEVICE_RESOLUTION resolution);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetDeviceResolution)(int16_t handle, PICO_DEVICE_RESOLUTION* resolution);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaQueryOutputEdgeDetect)(int16_t handle, int16_t* state);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetOutputEdgeDetect)(int16_t handle, int16_t state);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetScalingValues)(int16_t handle,
                                                            PICO_SCALING_FACTORS_FOR_RANGE_TYPES_VALUES* scalingValues,
                                                            int16_t nChannels);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaGetAdcLimits)(int16_t handle,
                                                        PICO_DEVICE_RESOLUTION resolution,
                                                        int16_t* minValue,
                                                        int16_t* maxValue);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaCheckForUpdate)(int16_t handle,
                                                          PICO_FIRMWARE_INFO* firmwareInfos,
                                                          int16_t* nFirmwareInfos,
                                                          uint16_t* updatesRequired);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaStartFirmwareUpdate)(int16_t handle, PicoUpdateFirmwareProgress progress);

PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaResetChannelsAndReportAllChannelsOvervoltageTripStatus)(
  int16_t handle,
  PICO_CHANNEL_OVERVOLTAGE_TRIPPED* allChannelsTrippedStatus,
  uint8_t nChannelTrippedStatus);

PREF0 PREF1 PICO_STATUS PREF2
  PREF3(psospaReportAllChannelsOvervoltageTripStatus)(int16_t handle,
                                                      PICO_CHANNEL_OVERVOLTAGE_TRIPPED* allChannelsTrippedStatus,
                                                      uint8_t nChannelTrippedStatus);

// Sets the colour of the specified LEDs
// The LED's colour will only take effect the next time that LED is applied
// i.e. psospaRunBlock, psospaRunStreaming, psospaSigGenApply, etc.
//
// Parameters:
// handle: identifies the device on which to set the LED colour
// colourProperties: array of the LEDs to set and the colour to set them to, duplicate LEDs will take the colour of the last in the list
// nColourProperties: number of elements in the colourProperties array
//
// Return:
// PICO_OK
// PICO_INVALID_HANDLE (handle isn't that of an open PicoScope device.)
// PICO_NULL_PARAMETER (the colourProperties pointer is null)
// PICO_INVALID_PARAMETER (array length is invalid)
// PICO_INVALID_PARAMETER (one or more of the specified LEDs is not present on the device)
// PICO_INVALID_PARAMETER (one or more of the hue or saturation are out of range)
PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetLedColours)(int16_t handle,
                                                         const PICO_LED_COLOUR_PROPERTIES* colourProperties,
                                                         uint32_t nColourProperties);

// Sets the brightness of all configurable LEDs
// The LED's brightness will only take effect the next time that LED is applied
// i.e. psospaRunBlock, psospaRunStreaming, psospaSigGenApply, etc.
//
// Parameters:
// handle: identifies the device on which to set the LED colour
// brightness: brightness of the LEDs. 0-100 inclusive (default 79)
//
// Return:
// PICO_OK
// PICO_INVALID_HANDLE (handle isn't that of an open PicoScope device.)
// PICO_INVALID_PARAMETER (brightness is out of range)
PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetLedBrightness)(int16_t handle, uint8_t brightness);

// Sets the state of the specified LEDs
//
// Parameters:
// handle: identifies the device on which to set the LED state
// stateProperties: array of the LEDs to set and the state to set them to, duplicate LEDs will take the state of the last in the list
// nStateProperties: number of elements in the stateProperties array
//
// Return:
// PICO_OK
// PICO_INVALID_HANDLE (handle isn't that of an open PicoScope device.)
// PICO_NULL_PARAMETER (the stateProperties pointer is null)
// PICO_INVALID_PARAMETER (array length is invalid)
// PICO_INVALID_PARAMETER (one or more of the specified LEDs is not present on the device)
PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetLedStates)(int16_t handle,
                                                        const PICO_LED_STATE_PROPERTIES* stateProperties,
                                                        uint32_t nStateProperties);

// Configures the AuxIO mode/function
//
// Parameters:
// handle: identifies the device on which to configure the AuxIO mode
// auxIoMode: required AuxIO mode value from PICO_AUXIO_MODE enum
//
// Return:
// PICO_OK
// PICO_INVALID_HANDLE (handle isn't that of an open PicoScope device.)
// PICO_OPERATION_FAILED (failed to change AuxIO mode)
// PICO_WARNING_AUX_OUTPUT_CONFLICT (a warning given to user when AuxIO direction is output due to AuxIO mode, and AWG or/and scope use Aux trigger source) 
PREF0 PREF1 PICO_STATUS PREF2 PREF3(psospaSetAuxIoMode)(int16_t handle, PICO_AUXIO_MODE auxIoMode);

#endif
