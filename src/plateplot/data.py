"""CSV input and per-well data validation."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path

from matplotlib.colors import is_color_like

from .models import PlateTemplate, finite_number, normalize_well


@dataclass(frozen=True)
class WellData:
    well: str
    sample_name: str = ""
    group: str = ""
    concentration: float | None = None
    concentration_unit: str = ""
    fill_color: str = ""
    label: str = ""
    extra: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "well", normalize_well(self.well))
        for name in ("sample_name", "group", "concentration_unit", "fill_color", "label"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise ValueError(f"{self.well}: {name} must be text")
        if self.concentration is not None:
            object.__setattr__(
                self,
                "concentration",
                finite_number(self.concentration, f"{self.well}: concentration"),
            )
        if self.fill_color and not is_color_like(self.fill_color):
            raise ValueError(f"{self.well}: invalid fill_color {self.fill_color!r}")
        if not isinstance(self.extra, Mapping) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in self.extra.items()
        ):
            raise ValueError(f"{self.well}: extra fields must map text keys to text values")
        if self.extra.keys() & {item.name for item in fields(self)}:
            raise ValueError(f"{self.well}: extra fields cannot shadow built-in fields")
        object.__setattr__(self, "extra", dict(self.extra))

    @classmethod
    def from_mapping(cls, row: Mapping) -> WellData:
        if not isinstance(row, Mapping):
            raise ValueError("Each data row must be a WellData or mapping")
        if "well" not in row:
            raise ValueError("Each data row requires a well field")
        known = {item.name for item in fields(cls)} - {"extra"}
        values = {key: value for key, value in row.items() if key in known}
        if values.get("concentration") in ("", None):
            values["concentration"] = None
        extras = dict(row.get("extra", {}))
        extras.update(
            {key: str(value) for key, value in row.items() if key not in known and key != "extra"}
        )
        return cls(**values, extra=extras)

    def text(self, name: str) -> str:
        if name == "concentration":
            if self.concentration is None:
                return ""
            return f"{self.concentration:g} {self.concentration_unit}".strip()
        if name in {"well", "sample_name", "group", "concentration_unit", "fill_color", "label"}:
            return getattr(self, name)
        if name in self.extra:
            return self.extra[name]
        raise ValueError(f"Unknown label field {name!r} for {self.well}")


def load_csv(path: str | Path) -> list[WellData]:
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        names = reader.fieldnames
        if not names or "well" not in names:
            raise ValueError("CSV must have a well column")
        if len(names) != len(set(names)):
            raise ValueError("CSV contains duplicate column headers")
        if any(not name.strip() or name != name.strip() for name in names):
            raise ValueError("CSV headers must be nonempty, without surrounding whitespace")
        result = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV line {reader.line_num}: inconsistent column count")
            if not any(value.strip() for value in row.values()):
                continue
            try:
                result.append(WellData.from_mapping(row))
            except ValueError as exc:
                raise ValueError(f"CSV line {reader.line_num}: {exc}") from exc
        return result


def prepare_data(
    data: str | Path | Iterable[WellData | Mapping] | None, template: PlateTemplate
) -> dict[str, WellData]:
    rows = load_csv(data) if isinstance(data, (str, Path)) else ([] if data is None else data)
    result = {}
    for item in rows:
        row = item if isinstance(item, WellData) else WellData.from_mapping(item)
        template.center(row.well)
        if row.well in result:
            raise ValueError(f"Duplicate well {row.well}")
        result[row.well] = row
    return result
