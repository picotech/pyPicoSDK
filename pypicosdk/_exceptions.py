"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.
Python file containing all pyPicoSDK exceptions
"""


class PicoSDKException(Exception):
    "General pyPicoSDK exception"


class PicoSDKNotFoundException(Exception):
    "Exception for PicoSDK not found."


class NoArgumentsNeededWarning(UserWarning):
    "Warning no arguments needed for the function."
