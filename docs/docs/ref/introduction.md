<!-- Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms. -->
# Introduction

Each picoSDK class is built from a common class (PicoScopeBase) and a specific sub-class (ps####a).
This allows each PicoScope to have shared, common functions such as opening the unit, while certain models have additional, hardware-specific functions.

## C PicoSDK (ctypes)
This wrapper is built over the C DLL drivers from Pico Technology.
Therefore most basic python functions (such as `run_block()`) have a counterpart in the C library (e.g. `ps6000aRunBlockMode()`).
These python functions parse the variables through the DLL's using the `ctypes` package to talk directly to the unit.
For reference on these DLL's and their C implementation, go to [https://www.picotech.com/downloads/documentation](https://www.picotech.com/downloads/documentation) and look for your PicoScope Programmer's Guide.

## FAQ's
### Does my PicoScope use ps6000a() or ps6000()?
The PicoScope (A) drivers are the latest generation of drivers from Pico Technology. If you have a PicoScope with a letter designation higher than the following, you will need to use the (A) class and drivers:

 - PicoScope 6000**E**
