## Development
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
    