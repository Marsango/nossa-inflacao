"""Keep each diagnostic line intact when collector threads report together."""

from threading import Lock

output_lock = Lock()


def write_line(message, *, file=None, flush=True):
    with output_lock:
        print(message, file=file, flush=flush)
