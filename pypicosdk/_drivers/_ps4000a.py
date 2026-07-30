try:
    from typing import override  # type: ignore
except ImportError:
    from typing_extensions import override  # type: ignore
from ..base import PicoScopeBase
from ..shared._ps5000a_ps6000a import Sharedps5000aPs6000a
from ..shared._ps5000a_ps4000a import Sharedps5000aPs4000a


class ps4000a(PicoScopeBase, Sharedps5000aPs6000a, Sharedps5000aPs4000a):  # pylint: disable=C0103
    """PicoScope 4000 (A) API specific functions"""

    @override
    def __init__(self, *args, **kwargs):
        super().__init__("ps4000a", *args, **kwargs)