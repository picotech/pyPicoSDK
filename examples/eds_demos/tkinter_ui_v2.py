from collections import deque
from dataclasses import dataclass
# import random
import time
import tkinter as tk
import threading
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pypicosdk as psdk

# import faulthandler
# faulthandler.enable()


@dataclass
class ScopeConfig:
    # Channel Config
    channel = psdk.CHANNEL.A
    range = psdk.RANGE.V1
    threshold = 0

    # Sample Config
    samples = 50000
    sample_rate = 10
    unit = psdk.SAMPLE_RATE.MSPS

    # SigGen
    freq = 1000
    pk2pk = 1.8
    waveform = psdk.WAVEFORM.SINE


class RunTime:
    def __init__(
            self,
            picoscope: psdk.psospa | psdk.ps6000a,
            buffer_queue: deque,
            scope_config: ScopeConfig
            ):
        self.buffer_queue = buffer_queue
        self.scope = picoscope
        self.config = scope_config
        self.samples: int = self.config.samples
        self.buffer = np.empty(self.samples, dtype=np.int16)
        self.timebase: int

        self.led_list = ['A', 'B', 'C', 'D', 'AUX', 'AWG']

        self.setup_scope()
        self.setup_siggen()
        self.thread: threading.Thread
        self.stop = threading.Event()

    def setup_scope(self):
        self.scope.open_unit()
        self.scope.set_channel(self.config.channel, self.config.range)
        self.scope.set_simple_trigger(
            self.config.channel, self.config.threshold, auto_trigger=1_000)
        self.scope.set_data_buffer(self.config.channel, self.samples, buffer=self.buffer)
        self.timebase = self.scope.sample_rate_to_timebase(
            self.config.sample_rate, self.config.unit)
        self.time_axis = self.scope.get_time_axis(self.timebase, self.samples, pre_trig_percent=50,
                                                  unit='ms')

    def setup_siggen(self):
        self.scope.set_siggen(self.config.freq, self.config.pk2pk, self.config.waveform)

    def run_block(self):
        self.scope.run_block_capture(self.timebase, self.samples)
        self.scope.get_values(self.samples)
        self.buffer_queue.append(self.scope.adc_to_mv(self.buffer, self.config.channel))

    def main_thread(self):
        while not self.stop.is_set():
            self.run_block()

    def start(self):
        self.thread = threading.Thread(target=self.main_thread)
        self.thread.start()

    def join(self):
        self.stop.set()
        self.thread.join()
        self.scope.close_unit()


class Animation:
    def __init__(self, scope_runtime: RunTime, interval):
        self.root = tk.Tk()
        self.root.title('PicoScope EDS 2025')

        self.queue = scope_runtime.buffer_queue

        self.fig, self.ax = plt.subplots()
        self.line, = self.ax.plot(scope_runtime.time_axis, np.zeros(scope_runtime.samples))
        self.ax.set_xlim(scope_runtime.time_axis[0], scope_runtime.time_axis[-1])
        self.ax.set_ylim(scope_runtime.scope.get_ylim())
        self.interval = interval

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack()

        self.button_1 = tk.Button(self.button_frame, text='inc', command=self.inc_siggen,
                                  width=10, height=1)
        self.button_1.grid(row=0, column=0)

        self.update_thread = threading.Thread(target=self.update)
        self.stop = threading.Event()

        self.root.protocol("WM_DELETE_WINDOW", self.join)

    def inc_siggen(self):
        print('inc_siggen')

    def update(self):
        while not self.stop.is_set():
            try:
                self.line.set_ydata(self.queue.popleft())
            except IndexError:
                pass
            self.canvas.draw()
            time.sleep(self.interval/1000)

    def start(self):
        self.update_thread.start()
        self.root.mainloop()

    def join(self):
        print('Quitting...')
        self.stop.set()
        self.root.quit()
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        self.update_thread.join()


if __name__ == '__main__':
    queue = deque(maxlen=10)
    scope = psdk.psospa()
    config = ScopeConfig()

    runtime = RunTime(scope, queue, config)
    runtime.start()

    animation = Animation(runtime, interval=100)
    animation.start()

    runtime.join()
