import sys
import os
import shutil
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)
from version import docs_version, package_version


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