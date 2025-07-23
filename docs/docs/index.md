<div align="center">
<img src="https://raw.githubusercontent.com/JamesPicoTech/pyPicoSDK/refs/heads/main/docs/docs/img/pypicosdk-image-400x400.png" alt="Centered Image" />
</div>

# Welcome to pyPicoSDK Documentation
## Installation
### Prerequisites 
1. Go to PicoTech downloads [picotech.com/downloads](https://www.picotech.com/downloads)
2. Find your PicoScope in the list and click through
3. Download and install PicoSDK for your operating system
### Via Pip
1. Install the package via pip `pip install pypicosdk`
2. In your `main.py` add `import pypicosdk` or `import pypicosdk as psdk`

### Via GitHub (Inc examples)
1. Install github repository to folder `git clone https://github.com/JamesPicoTech/pyPicoSDK.git`
2. In the root directory (where setup.py is) run `pip install .`
3. In your `main.py` add `import pypicosdk` or `import pypicosdk as psdk`

## Quickstart
To test functionality of this library, copy and run the following python script:
```
import pypicosdk as psdk

scope = psdk.ps6000a()

scope.open_unit()
print(scope.get_unit_serial())
scope.close_unit()
```
The output should be similar to:
`JR001/001`

Once tested, try an [example script from github](https://github.com/JamesPicoTech/pyPicoSDK) to get started.

## Useful links and references
- [Documentation & Reference](https://jamespicotech.github.io/pyPicoSDK/)
- [GitHub Repo (with examples)](https://github.com/JamesPicoTech/pyPicoSDK)
- [pypi (src repo)](https://pypi.org/project/pypicosdk/)
- [pypi-nightly (dev repo)](https://pypi.org/project/pypicosdk-nightly/)
- [PicoScope Support (Compatibility)](https://jamespicotech.github.io/pyPicoSDK/dev/current)

## Version Control
pyPicoSDK: 0.3.2

Docs: 0.2.1
