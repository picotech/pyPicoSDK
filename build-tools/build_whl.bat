@echo off
cd build-tools
echo updating versions from version_main.py
python version_updater.py
cd ..
rmdir /s /q dist
rmdir /s /q build
rmdir /s /q pypicosdk.egg-info
echo copying contents of index.md to README.md
python -c "import shutil; shutil.copyfile('./docs/docs/index.md', './README.md')"
cibuildwheel --output-dir dist
echo twine upload --repository testpypi dist/*
cd ..