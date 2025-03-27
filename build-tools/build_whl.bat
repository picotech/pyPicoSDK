@echo off
cd build-tools
echo updating versions from version_main.py
python version_updater.py
cd ..
echo copying contents of index.md to README.md
python -c "import shutil; shutil.copyfile('./docs/docs/index.md', './README.md')"
cibuildwheel --output-dir dist
echo twine upload --repository testpypi dist/*
cd build-tools