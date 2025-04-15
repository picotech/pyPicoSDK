@echo off
echo updating versions from version_main.py
python build-tools\version_updater.py
rmdir /s /q dist
python -m build --wheel
twine upload dist/*