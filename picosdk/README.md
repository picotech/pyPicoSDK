## Development
### Adding a new general function
This section of the guide shows how to add a new function into a class directly from the PicoSDK DLLs.
1. Create a function within the PicoScopeBase class or the psX000a class:
```
def open_unit():
    return "Done!"
```
2. Find the DLL in the programmers guide to wrap in python i.e. `ps6000aOpenUnit`
3. Get the DLL function from `self._get_attr_function()` . This concatenates the `_unit_prefix_n` of the PicoScope specific sub-class, with the sepcific function. i.e. a `_unit_prefix_n = "ps5000a"` + `self._get_attr_function("OpenUnit")` will return `self.dll.ps5000aOpenUnit()` for use as a function.
4. Assign this to a variable such as `attr_function`:
```
def open_unit():
   attr_function = self._get_attr_function('OpenUnit')
   return None
```
5. Build the function (referencing the programmers guide):
```
def open_unit():
   attr_function = self._get_attr_function('OpenUnit')
   attr_function(
    handle,
    serial,
    resolution
   )
   return None
```
6. Using ctypes, convert or setup variables for each function input (where needed).
 - `ctypes.byref(variable)` will send the ctypes pointer - for addressable data
 - String data needs `encode()` before sending
 - Integers _may_ be automatically converted

```
def open_unit():
   handle = ctypes.c_short()
   attr_function = self._get_attr_function('OpenUnit')
   attr_function(
    ctypes.byref(handle),
    serial.encode(),
    resolution
   )
   return handle
```
7. Add docstring for your new function along with function inputs, declarations and default values.
```
def open_unit(serial:str=None, resolution:int=0) -> ctypes.c_short:
   """Open PicoScope Unit
   :param str serial: Serial number of device
   :param int resolution: Resolution of device
   :return ctypes.c_short: Returned handle of device
   """
   handle = ctypes.c_short()
   attr_function = self._get_attr_function('OpenUnit')
   attr_function(
    ctypes.byref(handle),
    serial,
    resolution
   )
   return handle
```
