"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

This scipt copies the version numbers to specific files.
    The master file is located in ./version.py.
    Update there then run version_updater.py to updated files
    below.
"""
# flake8: noqa

from version import docs_version, package_version
import sys
import os
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

IMG_STR = '''<!-- Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms. -->
<p align="center">
  <img src="https://raw.githubusercontent.com/picotech/pyPicoSDK/refs/heads/main/docs/docs/img/pypicosdk-light-300x300.png" alt="Fancy logo">
</p>

'''


def build_pypi_doc():
    "Create a pypi readme"
    string = '<!-- start here -->'
    string_len = len(string)
    with open('README.md', encoding='utf-8') as f:
        readme = f.read()

    index = readme.find(string) + string_len + 1

    new_readme = IMG_STR + readme[index:]

    with open('pypi.md', 'w', encoding='utf-8') as f:
        f.write(new_readme)


def update_lines(file_path, start_with, replacement_string):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    with open(file_path, "w", encoding='utf-8') as f:
        for line in lines:
            if line.strip().startswith(start_with):
                f.write(f'{replacement_string}\n')
            else:
                f.write(line)


def update_readme():
    update_lines('./README.md', 'pyPicoSDK:', f'pyPicoSDK: {package_version}')
    update_lines('./README.md', 'Docs:', f'Docs: {docs_version}')


def update_src():
    update_lines('./pypicosdk/version.py', '__version__', f'__version__ = "{package_version}"')


def update_init():
    """Update __version__ in __init__.py"""
    init_file = './pypicosdk/__init__.py'

    # Read the current file
    with open(init_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if __version__ already exists
    if '__version__' in content:
        # Update existing __version__
        update_lines(init_file, '__version__', f'__version__ = "{package_version}"')
    else:
        # Add __version__ after the docstring and before imports
        lines = content.split('\n')
        new_lines = []

        for _, line in enumerate(lines):
            new_lines.append(line)
            # Add __version__ after the docstring (after the last """ or ''' line)
            if line.strip().endswith('"""') or line.strip().endswith("'''"):
                new_lines.append('')  # Add blank line
                new_lines.append(f'__version__ = "{package_version}"')
                new_lines.append('')  # Add blank line

        # Write the updated content
        with open(init_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))


def update_versions():
    update_readme()
    update_src()
    update_init()


if __name__ == "__main__":
    update_versions()
    build_pypi_doc()
