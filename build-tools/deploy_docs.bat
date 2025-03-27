@echo off
cd build-tools
python version_updater.py
cd ..\docs
mkdocs gh-deploy
cd ..