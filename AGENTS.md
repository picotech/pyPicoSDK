# Conventions for PicoSDK constant definitions

## Module layout
- Import statements at the top, separated from the first definition by a single blank line.
- All constants and public structures live in `pypicosdk/constants.py`.
- The bottom of the file maintains a comprehensive `__all__` list enumerating every exported name.

## Enumerations and constant groups
- When constants map directly to integer values, use an `IntEnum` subclass.
  For example: `class CHANNEL(IntEnum):`.
- For simpler sets of constants that don’t require an enum type, use a plain class with uppercase attributes.
- Constant names are **UPPERCASE_WITH_UNDERSCORES**.
- Every enumeration or constant group includes a docstring with:
  - A short summary line.
  - An `Attributes:` section listing each constant.
  - Optionally an `Examples:` section demonstrating usage.
- One blank line separates each class definition.

## ctypes structures
- `ctypes.Structure` classes replicate PicoSDK structs.
- Set `_pack_ = 1` to mirror the 1-byte packing used in the SDK headers.
- Declare `_fields_` as a list of `(field_name, ctype)` tuples.
- Field names have a trailing underscore (`triggerTime_`) to match the C struct names exactly.
- Provide a docstring explaining the purpose of the structure and any special naming conventions.

## Miscellaneous
- Lists or helper constants (e.g., `CHANNEL_NAMES`) are defined at module scope with uppercase names.
- Indentation uses four spaces and no tabs.
- Keep line lengths reasonably short for readability (many existing lines are under 79 characters).

## Python wrapper style
- All public functions and methods include a triple-quoted docstring. Start with a
  short summary line followed by `Args:` and `Returns:` sections. Use `Raises:`
  when applicable.
- Type hints annotate function arguments and return values to clarify expected
  types.
- Private helper functions are prefixed with an underscore.
- Classes have a brief docstring summarizing their purpose.
- Each module ends with an explicit `__all__` list enumerating all exported
  names. The package ``__init__`` re-exports these names for static analysers.

Following these conventions keeps new constants and structures consistent with the existing definitions in `pypicosdk/constants.py`.
