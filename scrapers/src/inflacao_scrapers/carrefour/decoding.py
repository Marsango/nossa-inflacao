"""Decode the observed turbo-stream v2 JSON subset without rounding source money."""

import re

from ..vtex.json import decode_response, object_pairs


class ReferenceTable:
    def __init__(self, raw: str):
        self.entries = decode_response(raw)
        if not isinstance(self.entries, list) or not self.entries:
            raise ValueError("Carrefour source reference table absent; possible blocked response")

    def resolve(self, reference=0, active=frozenset()):
        if type(reference) is not int:
            raise ValueError("Carrefour source reference is not an integer")
        if reference in (-5, -7):  # turbo-stream v2 null and undefined, both explicitly unknown.
            return None
        if reference < 0 or reference >= len(self.entries):
            raise ValueError("Carrefour source reference out of bounds or unsupported")
        if reference in active or len(active) >= 64:
            raise ValueError("Carrefour cyclic or excessively nested source")
        return self.resolve_value(self.entries[reference], active | {reference})

    def resolve_value(self, value, active):
        if isinstance(value, dict):
            return object_pairs(
                (self.key(key, active), self.resolve(item, active)) for key, item in value.items()
            )
        if isinstance(value, list):
            return [self.resolve(item, active) for item in value]
        return value

    def key(self, key, active):
        if not re.fullmatch(r"_(?:0|[1-9][0-9]*)", key):
            raise ValueError("Carrefour source key reference malformed")
        resolved = self.resolve(int(key[1:]), active)
        if not isinstance(resolved, str):
            raise ValueError("Carrefour source key is not a string")
        return resolved

    def route(self, name):
        root = self.entries[0]
        if not isinstance(root, dict):
            raise ValueError("Carrefour source route mapping absent")
        matches = [value for key, value in root.items() if self.key(key, frozenset()) == name]
        if len(matches) != 1:
            raise ValueError("Carrefour search route absent or ambiguous; collection incomplete")
        return self.resolve(matches[0])["data"]
