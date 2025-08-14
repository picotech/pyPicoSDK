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
    