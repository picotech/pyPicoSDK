import numpy as np
import pandas as pd

def channels_buffer_to_np_array(channels_buffer:dict, ps_class):
    data = np.array(list(channels_buffer.values()))
    print(ps_class)
    return data