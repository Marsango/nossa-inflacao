"""Serialize complete browser lifetimes, including temporary-profile cleanup."""

from threading import Lock

# Botasaurus registers drivers and cleans temporary profiles process-wide.
# Keep this separate from HTTP workers so ordinary API work can still overlap.
browser_session = Lock()
