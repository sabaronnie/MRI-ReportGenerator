"""Put the repo root on sys.path so `services.*` imports resolve when running pytest from here."""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
