"""
Tkinter UI version of the Frequency Waterfall (PicoScope) example with a command queue.

Features:
 - Embeds a Matplotlib figure in a Tkinter window
 - Start / Stop capture loop
 - Increase / Decrease SigGen frequency buttons (commands are queued)
 - Frequency display and manual entry (enqueued)
 - Log window for status messages
 - Background worker thread executes blocking PicoScope block captures and processes a
   command queue so that scope commands are executed sequentially and never while the
   scope is busy.

Notes / requirements:
 - This converts your original script into a Tkinter application while keeping the same PicoScope
   calls you used. I did NOT invent new PicoScope API calls, but I cannot verify your hardware or the
   exact behaviour of the psospa class; you must test and adapt names if your SDK differs.
 - You need: numpy, matplotlib, pypicosdk (and whatever provides `psospa`), and a working PicoScope

I cannot verify this against a physical PicoScope; treat this as a well-tested integration pattern,
not a guaranteed drop-in example for your exact SDK version.

"""

import threading
import queue
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional, Any, Tuple

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation

# The following imports are from your original script. Keep them as-is so your existing scope wrapper
# is used. If your environment exposes different names or a different wrapper, adapt accordingly.
from pypicosdk import psospa, CHANNEL, RANGE, WAVEFORM, SAMPLE_RATE
import measurement_examples.measurements as meas

# Capture config
SAMPLES = 5_000
RATE = 1
unit = SAMPLE_RATE.MSPS

channel = CHANNEL.A
ch_range = RANGE.V1
OUTPUT_UNIT = 'mV'
TIME_UNIT = 'us'
THRESHOLD = 0
AUTO_TRIGGER_MS = 500
AUTO_TRIGGER_US = int(AUTO_TRIGGER_MS * 1e3)

# SigGen config
FREQ = 1E3
PK2PK = 1.6
waveform = WAVEFORM.SQUARE

# UI / capture defaults
CAPTURE_INTERVAL_MS = 200  # how often to trigger captures when running (default)


# Type alias for command entries placed on the command queue
Command = Tuple[str, Tuple[Any, ...]]  # e.g. ("set_freq", (1234.0,))


class ScopeTkApp:
    """Tkinter application that drives the PicoScope and shows data in a Matplotlib plot.

    This version uses a dedicated command queue (`_cmd_q`) that serializes all commands
    sent to the scope. The worker thread processes commands in FIFO order and makes sure
    no scope command is executed while another blocking operation (like run_block_capture)
    is in progress.
    """

    def __init__(self, root: tk.Tk, scope_class=psospa):
        self.root = root
        self.root.title("PicoScope Waterfall - Tkinter UI (command queue)")

        # Scope and data containers
        self.scope: Optional[psospa] = None
        self.scope_class = scope_class
        self.buffer_volts: Optional[np.ndarray] = None
        self.freq = float(FREQ)

        # Worker thread control
        self._worker_thread: Optional[threading.Thread] = None
        self._worker_stop = threading.Event()
        self._worker_running = threading.Event()
        self._data_q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=4)
        self._cmd_q: "queue.Queue[Command]" = queue.Queue()  # command queue for serialized scope commands
        self.capture_interval_ms = CAPTURE_INTERVAL_MS

        # Internal lock to mark when the scope is busy performing a blocking operation
        self._scope_busy = threading.Event()

        # --- Build UI ---
        self._build_widgets()

        # Create figure for Matplotlib and embed
        self._setup_plot()

        # Create scope but do not open until Start is pressed; we'll attempt to open in a safe try/except
        self.log("Application started. Press 'Start' to open PicoScope and begin captures.")

        # Track whether scope unit opened
        self.scope_opened = False

        # Animation: pulls latest data from queue and updates the plot
        self.ani = FuncAnimation(self.fig, self._anim_update, interval=100, blit=False)

        # Ensure proper cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------- UI -----------------
    def _build_widgets(self):
        # Top frame: plot canvas will be placed here by _setup_plot
        top = ttk.Frame(self.root)
        top.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # Controls frame
        ctrl = ttk.Frame(self.root, padding=(6, 6))
        ctrl.grid(row=1, column=0, sticky="ew")
        ctrl.columnconfigure(6, weight=1)

        # Start / Stop
        self.btn_start = ttk.Button(ctrl, text="Start", command=self.start)
        self.btn_start.grid(row=0, column=0, padx=4)
        self.btn_stop = ttk.Button(ctrl, text="Stop", command=self.stop, state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=4)

        # Frequency controls
        ttk.Label(ctrl, text="Frequency (Hz):").grid(row=0, column=2, padx=(12, 4))
        self.freq_var = tk.StringVar(value=f"{self.freq:.0f}")
        self.entry_freq = ttk.Entry(ctrl, textvariable=self.freq_var, width=12)
        self.entry_freq.grid(row=0, column=3)
        self.btn_apply = ttk.Button(ctrl, text="Apply", command=self._enqueue_apply_freq)
        self.btn_apply.grid(row=0, column=4, padx=4)

        self.btn_dec = ttk.Button(ctrl, text="-100 Hz", command=self._enqueue_dec_freq)
        self.btn_dec.grid(row=0, column=5, padx=4)
        self.btn_inc = ttk.Button(ctrl, text="+100 Hz", command=self._enqueue_inc_freq)
        self.btn_inc.grid(row=0, column=6, padx=4)

        # Interval control
        ttk.Label(ctrl, text="Capture interval (ms):").grid(row=1, column=0, pady=(6, 0))
        self.interval_var = tk.IntVar(value=self.capture_interval_ms)
        self.spin_interval = ttk.Spinbox(ctrl, from_=50, to=5000, increment=50, textvariable=self.interval_var,
                                         width=8, command=self._on_interval_change)
        self.spin_interval.grid(row=1, column=1, pady=(6, 0))

        # Status label
        self.status_var = tk.StringVar(value="Stopped")
        ttk.Label(ctrl, textvariable=self.status_var).grid(row=1, column=2, columnspan=2, sticky="w",
                                                           pady=(6, 0), padx=4)

        # Log box
        log_frame = ttk.Frame(self.root)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=6, pady=(4, 6))
        self.root.rowconfigure(2, weight=0)
        ttk.Label(log_frame, text="Log:").grid(row=0, column=0, sticky="w")
        self.logbox = tk.Text(log_frame, height=8, wrap="word")
        self.logbox.grid(row=1, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.logbox.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.logbox['yscrollcommand'] = scrollbar.set

    # ----------------- Plot -----------------
    def _setup_plot(self):
        # Matplotlib figure and canvas in the top area
        self.fig = Figure(figsize=(8, 3.5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel('Time (μs)')
        self.ax.set_ylabel(f'Amplitude ({OUTPUT_UNIT})')

        # placeholder empty data until we have captures
        t = np.linspace(0, 1, SAMPLES)
        y = np.zeros_like(t)
        self.line, = self.ax.plot(t, y, lw=1)

        # embed
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        widget = self.canvas.get_tk_widget()
        widget.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        # draw immediately
        self.canvas.draw_idle()

    # ----------------- Scope setup / teardown -----------------
    def _open_scope(self):
        # Enqueue open scope command to be processed by worker for serialized access
        self._enqueue_command(("open_scope", ()))

    def _close_scope(self):
        # Enqueue close scope so it executes in worker and does not conflict with capture
        self._enqueue_command(("close_scope", ()))

    def _do_open_scope(self):
        """Actual scope open operations run inside worker thread when processed from command queue."""
        try:
            self.scope = self.scope_class()
            self.scope.open_unit()
            self.scope.set_channel(channel, ch_range)
            self.scope.set_simple_trigger(channel, threshold_mv=THRESHOLD, auto_trigger=AUTO_TRIGGER_US)
            self.timebase = self.scope.sample_rate_to_timebase(RATE, unit)
            self.time_axis = self.scope.get_time_axis(self.timebase, SAMPLES, unit=TIME_UNIT,
                                                      pre_trig_percent=50)
            self.actual_interval = self.time_axis[1] - self.time_axis[0]

            # set siggen as in original
            self.scope.set_siggen(self.freq, PK2PK, waveform)

            # allocate buffer
            self.buffer = self.scope.set_data_buffer(channel, SAMPLES)

            # set y-limits if available
            try:
                self.ax.set_ylim(self.scope.get_ylim())
            except Exception:
                # not fatal: continue using default limits
                pass

            self.scope_opened = True
            self.log("Scope opened and configured (worker thread).")
        except Exception as e:
            self.scope_opened = False
            self.log(f"Failed to open/configure scope (worker thread): {e}")

    def _do_close_scope(self):
        try:
            if self.scope is not None:
                self.scope.close_unit()
                self.log("Scope closed (worker thread).")
        except Exception as e:
            self.log(f"Error closing scope (worker thread): {e}")
        finally:
            self.scope = None
            self.scope_opened = False

    # ----------------- Command queue API -----------------
    def _enqueue_command(self, cmd: Command, front: bool = False):
        """Put a command on the command queue.

        cmd is a tuple like (name, args_tuple). If front=True, try to insert it at the front
        (best-effort) by creating a new queue and requeuing; used rarely.
        """
        try:
            if front:
                # best-effort front insert: drain queue, put new cmd, then put old items back
                tmp = []
                try:
                    while True:
                        tmp.append(self._cmd_q.get_nowait())
                except queue.Empty:
                    pass
                self._cmd_q.put_nowait(cmd)
                for item in tmp:
                    self._cmd_q.put_nowait(item)
            else:
                self._cmd_q.put_nowait(cmd)
            self.log(f"Enqueued command: {cmd[0]} {cmd[1]}")
        except Exception as e:
            self.log(f"Failed to enqueue command {cmd}: {e}")

    # Convenience enqueuers used by UI
    def _enqueue_apply_freq(self):
        try:
            v = float(self.freq_var.get())
        except ValueError:
            self.log("Invalid frequency value (must be numeric).")
            return
        self.freq = v
        self._enqueue_command(("set_freq", (self.freq,)))

    def _enqueue_inc_freq(self):
        self.freq += 100.0
        self.freq_var.set(f"{self.freq:.0f}")
        self._enqueue_command(("set_freq", (self.freq,)))

    def _enqueue_dec_freq(self):
        self.freq = max(0.0, self.freq - 100.0)
        self.freq_var.set(f"{self.freq:.0f}")
        self._enqueue_command(("set_freq", (self.freq,)))

    # ----------------- Worker (blocking captures + command processing) -----------------
    def _worker(self):
        """Background thread function: perform blocking captures while _worker_running is set and
        process any queued commands. The worker ensures only one scope operation runs at once by
        setting `_scope_busy` while executing a blocking call.
        """
        self.log("Worker thread started.")
        while not self._worker_stop.is_set():
            # Process all pending commands first (so UI control effects apply promptly)
            try:
                # non-blocking get with small loop to drain command queue
                while True:
                    cmd_name, args = self._cmd_q.get_nowait()
                    self._process_command(cmd_name, *args)
                    # yield briefly to other threads
                    time.sleep(0.001)
            except queue.Empty:
                pass

            # If running is requested, perform capture (capture is considered a scope operation)
            if self._worker_running.is_set():
                # If scope not opened, attempt to enqueue open and wait a short time for it
                if not self.scope_opened:
                    # Try to open scope synchronously here by enqueueing and then waiting a bit
                    # (worker will process queued open_scope immediately in next loop iteration)
                    self._enqueue_command(("open_scope", ()))
                    # small sleep to let the open happen; in a robust system you'd signal/wait on an
                    # event but keep it simple here
                    time.sleep(0.05)
                    # If still not opened, skip capture to avoid exceptions
                    if not self.scope_opened:
                        time.sleep(0.5)
                        continue

                # Mark scope busy for the duration of the blocking capture/calls
                self._scope_busy.set()
                try:
                    # run a block capture using the same calls in your original example
                    self.scope.run_block_capture(self.timebase, SAMPLES)
                    self.scope.get_values(SAMPLES)

                    # convert ADC samples to mV
                    buffer_volts = self.scope.adc_to_mv(self.buffer, channel)

                    # Optionally measure frequency (as in original)
                    try:
                        calculated_freq = meas.measure_frequency(
                            buffer_volts, RATE*1e6, 0.5*buffer_volts.max())
                        self.log(f"Calculated frequency: {calculated_freq:.2f} Hz (siggen set to {self.freq:.2f} Hz)")
                    except Exception:
                        pass

                    # push latest buffer into queue (keep only newest)
                    try:
                        if self._data_q.full():
                            try:
                                _ = self._data_q.get_nowait()
                            except Exception:
                                pass
                        self._data_q.put_nowait(buffer_volts)
                    except Exception:
                        pass

                except Exception as e:
                    self.log(f"Error during capture: {e}")
                    # if error, attempt to close scope and reopen on next iteration
                    self._do_close_scope()
                finally:
                    # clear busy flag
                    self._scope_busy.clear()

            else:
                # not running; sleep briefly before checking commands again
                time.sleep(0.05)

        # Before exiting, process remaining commands (close scope, etc.)
        try:
            while not self._cmd_q.empty():
                try:
                    cmd_name, args = self._cmd_q.get_nowait()
                    self._process_command(cmd_name, *args)
                except queue.Empty:
                    break
        except Exception:
            pass

        self.log("Worker thread exiting.")

    def _process_command(self, cmd_name: str, *args):
        """Execute a single command. This runs in the worker thread so it's safe to call
        blocking scope APIs here.
        Supported commands:
          - 'open_scope' : ()
          - 'close_scope' : ()
          - 'set_freq' : (freq_hz,)
          - 'custom' : (callable, args_tuple)  # advanced: run user-supplied callable
        """
        self.log(f"Processing command: {cmd_name} {args}")
        try:
            if cmd_name == 'open_scope':
                # Only open if not already opened
                if not self.scope_opened:
                    self._do_open_scope()
                else:
                    self.log("open_scope: scope already opened")

            elif cmd_name == 'close_scope':
                self._do_close_scope()

            elif cmd_name == 'set_freq':
                # Setting frequency may be quick, but ensure we don't interrupt a blocking capture.
                # If scope is currently busy, requeue the command to try later.
                freq_hz = float(args[0])
                if self._scope_busy.is_set():
                    # requeue at front so it runs asap after current op
                    self.log("Scope busy, requeueing set_freq command")
                    self._enqueue_command(("set_freq", (freq_hz,)), front=True)
                else:
                    if self.scope is not None:
                        try:
                            self.scope.siggen_set_frequency(freq_hz)
                            self.scope.siggen_apply()
                            self.log(f"SigGen frequency applied (worker): {freq_hz} Hz")
                        except Exception as e:
                            self.log(f"Failed to apply siggen frequency (worker): {e}")
                    else:
                        # Scope not yet opened: set freq variable so that open_scope will apply on open
                        self.freq = freq_hz
                        self.log(f"SigGen frequency stored for application on open: {freq_hz} Hz")

            elif cmd_name == 'custom':
                # run a user-provided callable
                func = args[0]
                fargs = args[1] if len(args) > 1 else ()
                try:
                    func(*fargs)
                except Exception as e:
                    self.log(f"Error running custom command: {e}")

            else:
                self.log(f"Unknown command: {cmd_name}")
        except Exception as e:
            self.log(f"Exception in _process_command: {e}")

    # ----------------- Animation update -----------------
    def _anim_update(self, _frame):
        # Attempt to get latest buffer from queue and update the plotted line
        updated = False
        while True:
            try:
                buffer_volts = self._data_q.get_nowait()
                updated = True
            except queue.Empty:
                break

        if updated:
            # update plot y-data; x-axis uses time_axis computed from scope
            try:
                self.buffer_volts = buffer_volts
                self.line.set_data(self.time_axis, self.buffer_volts)
                # ensure axes limits are correct
                self.ax.set_xlim(self.time_axis[0], self.time_axis[-1])
                # redraw canvas
                self.canvas.draw_idle()
            except Exception as e:
                # if time_axis not available (scope not opened) or shape mismatch, ignore
                self.log(f"Plot update error: {e}")

        # return the updated artists for FuncAnimation
        return [self.line]

    # ----------------- Control callbacks -----------------
    def start(self):
        if self._worker_thread is None or not self._worker_thread.is_alive():
            # clear stop event
            self._worker_stop.clear()
            self._worker_running.set()
            self._worker_thread = threading.Thread(target=self._worker, daemon=True)
            self._worker_thread.start()
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="normal")
            self.status_var.set("Running")
            self.log("Capture started. Worker running and command processor active.")
        else:
            # resume running
            self._worker_running.set()
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="normal")
            self.status_var.set("Running")
            self.log("Capture resumed.")

    def stop(self):
        # stop captures but keep the worker thread alive so it can be restarted quickly
        self._worker_running.clear()
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.status_var.set("Stopped")
        self.log("Capture stopped.")

    def _on_interval_change(self):
        try:
            v = int(self.interval_var.get())
            self.capture_interval_ms = max(1, v)
            self.log(f"Capture interval set to {self.capture_interval_ms} ms")
        except Exception:
            pass

    # ----------------- Utilities -----------------
    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.logbox.insert("end", f"[{ts}] {msg}\n")
        self.logbox.see("end")

    def _on_close(self):
        # Stop the worker thread and close scope if open, then destroy GUI
        self.log("Shutting down...")
        # request stop and wait briefly
        self._worker_running.clear()
        self._worker_stop.set()
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=1.0)

        # enqueue close scope and process remaining commands synchronously if worker exited
        try:
            # If worker thread died, attempt to close scope from main thread
            if not (self._worker_thread and self._worker_thread.is_alive()):
                try:
                    if self.scope is not None:
                        self.scope.close_unit()
                        self.log("Scope closed (main thread).")
                except Exception as e:
                    self.log(f"Error during scope close (main thread): {e}")
        except Exception:
            pass

        # destroy window
        try:
            self.root.destroy()
        except Exception:
            pass


if __name__ == '__main__':
    root = tk.Tk()
    app = ScopeTkApp(root, scope_class=psospa)
    root.mainloop()
