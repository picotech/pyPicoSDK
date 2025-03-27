@echo off
echo updating versions from version_main.py
python version_updater.py
echo copying contents of index.md to README.md
python -c "import shutil; shutil.copyfile('./docs/docs/index.md', './README.md')"
python setup.py clean --all bdist_wheel
echo twine upload --repository testpypi dist/*