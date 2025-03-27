@echo off
python version_updater.py
cd docs
mkdocs gh-deploy
cd ..