<!-- Copyright (C) 2018-2022 Pico Technology Ltd. See LICENSE file for terms. -->
# Streaming
Streaming in a PicoScope is a great tool for monitoring a waveform for a long period of time
without the delay between block captures. Though this method of capture is fairly limited in 
sample rate and usability in comparison to a `block capture` and especially `rapid block capture`.

## Using Streaming in pyPicoSDK
Streaming is implemented in this package as a class to take advantage of the benefits offered by an object-oriented approach.
For a quick start-up use the [example code](https://github.com/JamesPicoTech/pyPicoSDK/blob/main/examples/streaming) and alter it to your application.

## Methods & Functions
Below are the included public methods for streaming:
::: pypicosdk.streaming.StreamingScope
    options:
        show_root_toc_entry: true
        summary: true