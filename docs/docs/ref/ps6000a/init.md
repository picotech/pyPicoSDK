# Initializing ps6000a
```
import pypicosdk as psdk

scope = psdk.ps6000a()

scope.open_unit()
# Do something
scope.close_unit()
```
