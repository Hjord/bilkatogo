import dataclasses
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any


@dataclass
class BilkaDataClass:
    def __iter__(self) -> Iterator[tuple[str, Any]]:
        for f in dataclasses.fields(self):
            if f.name == "_raw":
                continue
            value = getattr(self, f.name)
            if isinstance(value, BilkaDataClass):
                value = dict(value)
            elif isinstance(value, list):
                value = [dict(item) if isinstance(item, BilkaDataClass) else item for item in value]
            yield f.name, value
