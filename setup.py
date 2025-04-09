from setuptools import setup, find_packages
import os

# Helper to include the .dll file in package_data
def package_files(directory):
    paths = []
    for (path, _, filenames) in os.walk(directory):
        for filename in filenames:
            full_path = os.path.join(path, filename)
            paths.append(os.path.relpath(full_path, "pypicosdk"))
    return paths

extra_files = package_files('pypicosdk/lib')

setup(
    name="pypicosdk",
    version="0.2.21",
    packages=find_packages(),
    include_package_data=True,
    has_ext_modules=lambda : True,
    package_data={
        "pypicosdk": extra_files,
    },
    author="Pico Technology",
    author_email="support@picotech.com",
    description="Modern Python wrapper for PicoSDK",
    long_description=open("README.md").read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    license_file="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Operating System :: Microsoft :: Windows :: Windows 11",
        "Development Status :: 1 - Planning",
    ],
    python_requires='>=3.9',
)
