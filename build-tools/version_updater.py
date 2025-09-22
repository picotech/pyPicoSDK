"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

This scipt copies the version numbers to specific files.
    The master file is located in ./version.py.
    Update there then run version_updater.py to updated files
    below.
"""

import sys
import os
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)
from version import docs_version, package_version

IMG_STR = '''<!-- Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms. -->
<p align="center">
  <img src="https://raw.githubusercontent.com/picotech/pyPicoSDK/refs/heads/main/docs/docs/img/pypicosdk-light-300x300.png" alt="Fancy logo">
</p>

'''

def build_pypi_doc():
    "Create a pypi readme"
    string = '<!-- start here -->'
    string_len = len(string)
    with open('README.md') as f:
        readme = f.read()

    index = readme.find(string) + string_len + 1

    new_readme = IMG_STR + readme[index:]

    with open('pypi.md', 'w') as f:
        f.write(new_readme)


def update_lines(file_path, start_with, replacement_string):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    with open(file_path, "w") as f:
        for line in lines:
            if line.strip().startswith(start_with):
                f.write(f'{replacement_string}\n')
            else:
                f.write(line)

def update_readme():
    update_lines('./README.md', 'pyPicoSDK:', f'pyPicoSDK: {package_version}')
    update_lines('./README.md', 'Docs:', f'Docs: {docs_version}')

def update_src():
    update_lines('./pypicosdk/version.py', 'VERSION', f'VERSION = "{package_version}"')

def update_versions():
    update_readme()
    update_src()

if __name__ == "__main__":
    update_versions()
    build_pypi_doc()