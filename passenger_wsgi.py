"""Root-level Passenger startup file (cPanel "Setup Python App" → Startup file: passenger_wsgi.py).

cPanel may not accept a nested startup path, so this shim loads the real entry point
`deployment/cpanel/passenger_wsgi.py` by file path. Entry point: application.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REAL = Path(__file__).resolve().parent / "deployment" / "cpanel" / "passenger_wsgi.py"
_spec = importlib.util.spec_from_file_location("smy_passenger_wsgi", _REAL)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

application = _module.application
