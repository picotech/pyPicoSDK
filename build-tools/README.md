<!--Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.-->
# Build Tools
This folder contains tools to help with the build of pyPicoSDK

## version_updater.py
Version updater goes through each file that contains a version variable and updates based on `version.py` in the main folder. This script will also generate `pypi.py` which is the non-dark/light themed version of README.md to package with pypi.

To upversion a branch use the workflow below:
1. Before a Pull Request (PR) on a feature branch, do this first
2. Upversion `package_version` and/or `docs_version` in `./version.py`
3. Run `python build-tools/version_updater.py`
4. Verify it has updated the following:
    - `package_version` upversioned
        - `./pypi.md`
        - `./README.md`
        - `./pypicosdk/__init__.py`
        - `./pypicosdk/version.py`
    - `docs_version` upversioned
        - `./pypi.md`
        - `./README.md`
5. PR to main
6. Tag a new release with this format `v#.#.#` i.e. `v1.7.2`
7. Verify GitHub actions for success.
8. Done!

## build_docs.py
This script copies and builds the mkdocs documentation for multiple devices from a single source.
Single source is currently set to `/docs/docs/ref/psospa`.

To build documentation use the workflow below:
1. Edit documentation in /psospa docs
2. Add a device to `paste_dir_list` in `build_docs.py` if not already there. (Adding excluded files to copy)
3. Run `python /build-tools/build_docs.py` (Creating /ref/ps6000a and /ref/ps5000a)
4. Add additional .md docs not copied already (i.e. `ETS.md` for ps5000a)
5. Use `mkdocs serve` to verify additional docs
6. Done!

## requirements.txt
This file contains the relevant libraries GitHub actions will install to build `pypicosdk`. You may also use as a requirements file for your own environment.