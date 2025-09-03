from typing import Protocol


class _ProtocolBase(Protocol):
    """Protocol placeholder class for shared methods"""
    def _set_ylim(self, *args, **kwargs): ...
