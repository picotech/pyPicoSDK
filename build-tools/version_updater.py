import sys
import os
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

def update_docs():
    update_lines('../docs/docs/index.md', 'pyPicoSDK:', f'pyPicoSDK: {package_version}')
    update_lines('../docs/docs/index.md', 'Docs:', f'Docs: {docs_version}')

def update_setup():
    update_lines('../setup.py', 'version=', (' '*4) + f'version="{package_version}",')

def update_src():
    update_lines('../pypicosdk/version.py', 'VERSION', f'VERSION = "{package_version}"')

def update_project_toml():
    update_lines('../pyproject.toml', 'version = ', f'version = "{package_version}"')


def update_versions():
    update_docs()
    update_setup()
    update_src()
    update_project_toml()

if __name__ == "__main__":
    update_versions()