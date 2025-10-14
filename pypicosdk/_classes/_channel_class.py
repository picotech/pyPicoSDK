"""
This file contains a class to hold the channel data
i.e. range information and probe scale information
"""
from dataclasses import dataclass
import numpy as np
if __name__ != '__main__':
    from .. import constants as cst
else:
    from pypicosdk import constants as cst


@dataclass
class ChannelClass:
    "Dataclass containing channel information"
    range: cst.RANGE
    range_mv: int
    probe_scale: float
    ylim_mv: int
    ylim_v: float

    def __init__(self, ch_range: cst.RANGE, probe_scale: float):
        self.range = ch_range
        self.probe_scale = probe_scale
        self.range_mv = cst.RANGE_LIST[ch_range]
        self.range_v = self.range_mv / 1000
        self.ylim_mv = np.array([-self.range_mv, self.range_mv]) * probe_scale
        self.ylim_v = self.ylim_mv / 1000


if __name__ == '__main__':
    test = ChannelClass(ch_range=cst.RANGE.V1, probe_scale=10)
    print(test)
