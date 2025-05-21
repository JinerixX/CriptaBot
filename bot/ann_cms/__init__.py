"""
bot.ann_cms package

• Содержит announcer-классы, которые парсят CMS / блоги бирж.
• Создаёт псевдоним «ann_cms» → «bot.ann_cms», чтобы старые импорты
  вида `from ann_cms.base import ...` не ломались.
"""

from __future__ import annotations

import importlib
import sys as _sys

# ─── псевдоним пакета ───────────────────────────────────────────────
#   ann_cms       -> bot.ann_cms
#   ann_cms.base  -> bot.ann_cms.base

_pkg = _sys.modules[__name__]
_sys.modules.setdefault("ann_cms", _pkg)
_sys.modules.setdefault("ann_cms.base", importlib.import_module("bot.ann_cms.base"))

# ─── публичный API пакета (можно перечислить announcer-классы) ───────
from .binance import BinanceAnnouncer  # noqa: F401,E402
from .bybit   import BybitAnnouncer    # noqa: F401,E402
from .okx import OkxAnnouncer      # noqa: F401,E402
from .bitget  import BitgetAnnouncer   # noqa: F401,E402

__all__ = [
    "BinanceAnnouncer",
    "BybitAnnouncer",
    "OkxAnnouncer",
    "BitgetAnnouncer",
]
