"This file contains general classes for pyPicoSDK"

from dataclasses import dataclass


@dataclass
class BaseDataClass:
    "Class containing data for PicoScopeBase"
    last_pre_trig: float = 50
