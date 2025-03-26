# Welcome to pyPicoSDK Documentation
## Installation
1. Install github repository to folder `git clone https://github.com/JamesPicoTech/pyPicoSDK.git`
2. In your `main.py` add `from picosdk import picosdk`

## Quickstart
To test functionality of this library, copy and run the following python script:
```
from picosdk import picosdk

scope = picosdk.ps6000a()

scope.open_unit()
print(scope.get_unit_serial())
scope.close_unit()
```
The output should be similar to:
`JR001/001`

Once tested, try an example script to get started.