# Build tools
This is a suite of build tools to build the .whl files and documentation.
## build_whl.bat
Requires:
 - cibuildwheel `pip install cibuildwheel`
 - python

When build_whl.bat is ran it will first update any version variables throughout the document and code based on _version.py_ (make sure to up-issue the version number if needed).

It will then build the .whl files for all windows python versions specified by `python_requires` in setup.py. This may take a few minutes to complete.

Once complete it will display the `twine` command to upload the package to pypi for `pip` download.

## deploy_docs.bat
When deploy_docs.bat is ran, it will first update any version variables throughout the document and code based on _version.py_ (make sure to up-issue the version number if needed).

It will then run gh-deploy which will populate the github pages site with the latest documentation. This will ask for authentication before deploying. 

## version_updater.py
Version updater goes through the documents, setup.py and picosdk/version.py and updates each version variable based on _version.py_ in the main folder. 

To run use `python version.py`