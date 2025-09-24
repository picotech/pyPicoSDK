"""
These functions allow you to override the pyPicoSDK package settings and configuration.
"""
import os
from ._exceptions import PicoSDKNotFoundException


class _Configuration:
    "Configuration and overrides of pyPicoSDK"
    def __init__(self):
        self.sdk_directory = None


_conf = _Configuration()


def override_directory(directory: str):
    """
    Use this to specify the dictionary PicoSDK is in.
    pyPicoSDK will attempt to find PicoSDK through a list of
    expected locations. If your install of PicoSDK still isn't
    found, use this function to set it.

    Args:
        directory (str, optional): New directory location of PicoSDK.
            Defaults to None.

    Examples:
        >>> import pypicosdk as psdk
        >>> psdk.override_directory('C:/Program Files/Pico Technology/SDK')
    """
    if not os.path.exists(directory):
        raise PicoSDKNotFoundException(
            f'Directory "{directory}" does not exist. Please use a different directory.')
    lib_path = os.path.join(directory, 'lib')
    if os.path.exists(lib_path):
        directory = lib_path

    _conf.sdk_directory = directory
