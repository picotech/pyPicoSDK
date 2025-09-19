<!-- Copyright (C) 2018-2022 Pico Technology Ltd. See LICENSE file for terms. -->
## Development

### Live install pyPicoSDK for development
Run the following command in root dir (where setup.py is):

`pip install -e .`

This will install pyPicoSDK as an editable package, any changes made to pypicosdk will be reflected in the example code or any code ran in the current environnment. 

### Adding a new general function
This section of the guide shows how to add a new function into a class directly from the PicoSDK DLLs.
1. Create a function within the PicoScopeBase class or the psX000a class:
```
def open_unit():
    return "Done!"
```
2. Find the DLL in the programmers guide to wrap in python i.e. `ps6000aOpenUnit` and seperate the function suffix `OpenUnit`
3. Use the function `self._call_attr_function()`. This function will find the DLL and deal with PicoSDK errors. 
```
def open_unit(serial, resolution):
    handle = ctypes.c_short()
    status = self._call_attr_function("OpenUnit", ctypes.byref(handle), serial, resolution)
    return "Done!"
```

### Package Layout
#### pypicosdk Folder Structure
##### General files:
- \_\_init__.py
    - Script called when importing pypicosdk for the first time.
    - Imports everything inside pypicosdk.py.
- pypicosdk.py
    - The main source of all information.
    - Pulls and exposes the following:
        - Main scope classes i.e. psospa() and ps6000a().
        - Warnings and Exceptions from common.
        - Version.
        - Everything else is pulled in for the benifit of mkdocs.
- common.py
    - Contains the common functions and exceptions.
- constants.py
    - Contains all enum CONSTANTS used throughout the package.
    - Contains typing Literals and mappings for string typing hints.
- error_list.py
    - Contains a dictionary of all status errors in the PicoSDK to check against in the
        `base.py:_error_handler()`.
- version.py
    - Contains the version information.

##### PicoScope class files:
- ps####.py
    - Contains the main PicoScope class which include:
        - Scope specific functions i.e. LED's for psospa devices.
        - Overrides for certain functions i.e. different methods for `open_unit()` but still
            want to use the same function name.
- base.py
    - Contains mutable data between all scopes i.e.:
        - Scope handle
        - Scope DLL location and ctypes function
        - Channel information
        - ADC min and max
    - Contains shared functions across all scopes i.e. 'open_unit()'
- shared/ps#####_ps######.py
    - The shared folder contains functions shared between 2-3 scopes, but not all.
        - i.e. The 4000a 6000a share functions, but psospa does not so there is a class specifically
            for 6000a and 4000a devices called ps6000a_ps4000a.py which is inherited into the main
            scope class.
- shared/\_\_init__.py
    - Not currently used, but allows mkdocs and python to initialise the folder.
- shared/\_protocol.py
    - This file contains an inheritable class to help pylint/flake8 see variables that exist in
        different inherited classes i.e. get_max_adc_values() won't be in the class base, but it
        still may use it raising a flake8/pylint error. Having that function in the protocol class
        allows the linters to be happy the variable 'exists'.

#### Inheritance

pyPicoSDK has a shared inheritence class layout. Each driver class will follow this format:

```
class ps6000a(PicoScopeBase, shared_ps6000a_ps4000a, shared_ps6000a_psospa):
    def __init__(*args, **kwargs):
        super().__init__(*args, **kwargs)
    ...
```
The ps6000a drivers share the core functions: `PicoScopeBase`.
It also shares some driver functions **exclusively** with ps4000a `shared_ps6000a_ps4000a` and psospa: `shared_ps6000a_psospa`.
Any functions that ps6000a owns exclusively can be in the main ps6000a class.

`__init__` resolves `super().__init__` to initialise the PicoScopeBase variables i.e. ADC limits, channel dict etc.


### Updating Versions

Version control is currently maintained by incrementing the version numbers in `./version.py`. Once updated, run `./build-tools/version_updater.py` to update README's and other files that reference the version.

Version numbering is done on the premise of BreakingChange.MajorChange.MinorChange i.e. 1.4.2

Docs has its own versioning with the same numbering system.

### Updating documentation

`docs/docs/ref/ps*/` includes duplication of certain functions to allow mkdocstrings to populate the docs with functions. 
Currently `build-tools/build_docs.py` copies a list of files between devices from `.../ref/psospa/` to the other picoscope references. 

Therefore order of operation is the following:
1. Update non-copy controlled files i.e. `init.md` and `led.md` (if applicable)
2. Update copy files in `.../ref/psospa/...` i.e. `.../run.md` 
3. Run `build_docs.py` via `python build-tools/build_docs.py`
4. Check source control to check changes. 
    