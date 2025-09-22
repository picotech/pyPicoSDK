# Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

# pylint: skip-file
# flake8: noqa
import re

string = '<!-- start here -->'
string_len = len(string)
with open('README.md') as f:
    readme = f.read()

index = readme.find(string) + string_len + 1
img_str = '''<p align="center">
  <img src="https://raw.githubusercontent.com/picotech/pyPicoSDK/refs/heads/main/docs/docs/img/pypicosdk-light-300x300.png" alt="Fancy logo">
</p>

'''

new_readme = img_str + readme[index:]

with open('README_pypi.md', 'w') as f:
    f.write(new_readme)