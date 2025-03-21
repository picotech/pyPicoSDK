from picosdk.picosdk import *

ps = ps6000a()

ps.open_unit()

ps.get_unit_serial()
ps._siggen_set_range(1, 0)
ps._siggen_set_frequency(50000)
ps._siggen_set_waveform()
print(ps._siggen_apply())
ps.close_unit()