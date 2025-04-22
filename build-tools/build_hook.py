import os
import sys
from pathlib import Path
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

platform = sys.platform
if platform.startswith('linux'):
    extension = '.so'
    platform_tag = 'manylinux_x86_64'
elif sys.platform.startswith('win32'):
    extension = '.dll'
    platform_tag = 'win_amd64'
else:
    raise OSError("This platform isn't supported") 

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):     
        print("Preparing platform-specific native libraries...")
        path = 'pypicosdk/lib'
        for file in os.listdir('pypicosdk/lib'):
            if file.endswith(extension):
                filepath = os.path.join(path, file)
                build_data['force_include'][filepath] = filepath

    def finalize(self, version, build_data, artifact_path):
        if "pip-modern-metadata" not in artifact_path:
            path, filename = os.path.split(artifact_path)
            new_filename = filename.replace('any', platform_tag)
            print(f'Renaming {filename} to {new_filename}')
            os.rename(artifact_path, os.path.join(path, new_filename))