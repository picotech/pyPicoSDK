from setuptools import setup, find_packages
import os

# Helper to include the .dll file in package_data
def package_files(directory):
    paths = []
    for (path, _, filenames) in os.walk(directory):
        for filename in filenames:
            full_path = os.path.join(path, filename)
            paths.append(os.path.relpath(full_path, "picosdk"))
    return paths

extra_files = package_files('picosdk/lib')

setup(
    name="picosdk",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    has_ext_modules=lambda : True,
    package_data={
        "picosdk": extra_files,
    },
    author="Your Name",
    author_email="you@example.com",
    description="Python wrapper for PicoSDK",
    long_description=open("README.md").read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
