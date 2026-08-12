"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

pytest file guarding ctypes struct layouts against the C SDK headers.

The driver writes these structs by its own definition, not ours: an undersized
or misaligned ctypes declaration is a silent heap overflow on every call that
passes one. PICO_USB_POWER_DETAILS was 42 bytes against the header's 49 from
v1.x through v1.7.4 (missing powerErrorLikely_; attachedDevice_ declared 1 byte
where the C enum is 4), corrupting the heap on every psospaOpenUnit call.

Expected sizes are the compiler's own sizeof() values for the structs in
PicoDeviceStructs.h, which wraps them in #pragma pack(push,1).
"""
import ctypes

from pypicosdk.constants import (
    PICO_USB_POWER_DELIVERY,
    PICO_USB_POWER_DETAILS,
)

# (struct, sizeof per the pack(1) C header)
HEADER_SIZES = [
    (PICO_USB_POWER_DELIVERY, 24),
    (PICO_USB_POWER_DETAILS, 49),
]


def test_struct_sizes_match_c_header():
    for struct, expected in HEADER_SIZES:
        actual = ctypes.sizeof(struct)
        assert actual == expected, (
            f"{struct.__name__} is {actual} bytes but the C header defines {expected}: "
            "the driver will read/write past the Python-owned allocation"
        )


def test_usb_power_delivery_field_offsets():
    expected = {
        "valid_": 0,
        "busVoltagemV_": 1,
        "rpCurrentLimitmA_": 5,
        "partnerConnected_": 9,
        "ccPolarity_": 10,
        "attachedDevice_": 11,   # 4-byte enum PICO_USB_POWER_DELIVERY_DEVICE_TYPE
        "contractExists_": 15,
        "currentPdo_": 16,
        "currentRdo_": 20,
    }
    for name, offset in expected.items():
        actual = getattr(PICO_USB_POWER_DELIVERY, name).offset
        assert actual == offset, f"PICO_USB_POWER_DELIVERY.{name} at {actual}, header says {offset}"


def test_usb_power_details_field_offsets():
    expected = {
        "powerErrorLikely_": 0,
        "dataPort_": 1,
        "powerPort_": 25,
    }
    for name, offset in expected.items():
        actual = getattr(PICO_USB_POWER_DETAILS, name).offset
        assert actual == offset, f"PICO_USB_POWER_DETAILS.{name} at {actual}, header says {offset}"
