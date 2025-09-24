# flake8: noqa
# pylint: skip-file
"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

Public package interface for :mod:`pypicosdk`.
"""

# Import the implementation module under an internal name so we can
# reference its ``__all__`` attribute for static type checkers like Pylance.
from . import pypicosdk as _impl

# Re-export everything defined in ``pypicosdk`` for backwards compatibility.
from .pypicosdk import *
from ._config import override_directory

# Expose the full list of public names for static analysers.
__all__ = _impl.__all__
