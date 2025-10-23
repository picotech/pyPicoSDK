<!-- Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms. -->
<p align="center">
  <img src="https://raw.githubusercontent.com/picotech/pyPicoSDK/refs/heads/main/docs/docs/img/pypicosdk-light-300x300.png" alt="Fancy logo">
</p>

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
1. Install github repository to folder `git clone https://github.com/picotech/pyPicoSDK.git`
2. In the root directory (where setup.py is) run `pip install .`
3. In your `main.py` add `import pypicosdk` or `import pypicosdk as psdk`

### Python requirements
When installing pyPicoSDK, the following dependency is automatically installed:
- numpy

To run the provided examples, the following additional Python packages are required:
- matplotlib
- scipy
- numpy (installed automatically with pyPicoSDK)

To install the example depedancies use one of the following commands:
`pip install matplotlib scipy numpy`
or
`pip install -r requirements.txt`

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

Once tested, try an [example script from github](https://github.com/picotech/pyPicoSDK/tree/main/examples) to get started.

### Full getting started
[For our full getting started guide, click here to go to our full knowledge base article.](https://www.picotech.com/library/knowledge-bases/oscilloscopes/pypicosdk-get-started)

## Issues
For details on raising an issue, find information here: [Issue documentation](https://picotech.github.io/pyPicoSDK/dev/issues/)

## Compatibility
Current PicoScope support:
- PicoScope 6000E (ps6000a drivers)
- PicoScope 3000E (psospa drivers)

## Useful links and references
- [Documentation & Reference](https://picotech.github.io/pyPicoSDK/)
- [GitHub Repo (with examples)](https://github.com/picotech/pyPicoSDK)
- [pypi (src repo)](https://pypi.org/project/pypicosdk/)
- [pypi-nightly (dev repo)](https://pypi.org/project/pypicosdk-nightly/)

## Version Control
pyPicoSDK: 1.7.0

Docs: 0.4.1
