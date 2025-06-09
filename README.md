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
1. Install github repository to folder `git clone https://github.com/StuLawPico/pyPicoSDK_Playground.git`
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

Once tested, try an [example script from github](https://github.com/StuLawPico/pyPicoSDK_Playground) to get started.
For continuous acquisition see `examples/example_6000a_simple_streaming.py`.

## Useful links and references
- [Documentation & Reference](https://stulawpico.github.io/pyPicoSDK_Playground)
- [GitHub Repo (with examples)](https://github.com/StuLawPico/pyPicoSDK_Playground)
- [pypi (src repo)](https://pypi.org/project/pypicosdk/)
- [pypi-nightly (dev repo)](https://pypi.org/project/pypicosdk-nightly/)
- [PicoScope Support (Compatibility)](https://stulawpico.github.io/pyPicoSDK_Playground/dev/current)

## Version Control
pyPicoSDK: 0.2.30

Docs: 0.1.6
