"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.
This file contains general classes for pyPicoSDK
"""

from dataclasses import dataclass
from .. import constants as cst


@dataclass
class BaseDataClass:
    "Class containing data for PicoScopeBase"
    last_pre_trig: float = 50
    last_datatype: cst.DATA_TYPE = cst.DATA_TYPE.INT16_T
    last_buffer_size: int = None
