"""Millimeter geometry, separate from samples and visual styling."""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field, fields
from importlib.resources import files
from pathlib import Path


def row_name(index: int) -> str:
    """Zero-based row index -> A, B, ..., Z, AA, ... ."""
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise ValueError("Row index must be a nonnegative integer")
    result = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def normalize_well(value: str) -> str:
    match = re.fullmatch(r"([A-Za-z]+)0*([1-9][0-9]*)", str(value).strip())
    if not match:
        raise ValueError(f"Invalid well address: {value!r}; use e.g. A1 or A01")
    return match[1].upper() + str(int(match[2]))


def finite_number(value: object, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result) or (result <= 0 if positive else result < 0):
        qualifier = "positive" if positive else "nonnegative"
        raise ValueError(f"{name} must be finite and {qualifier}")
    return result


@dataclass(frozen=True)
class TemplateSource:
    kind: str = "illustrative"
    url: str = ""
    checked_on: str = ""
    notes: str = "Not verified against a physical product."
    document_name: str = ""
    document_sha256: str = ""
    drawing_number: str = ""
    drawing_version: str = ""
    page: str = ""

    def __post_init__(self):
        if self.kind not in {"illustrative", "manufacturer", "measured"}:
            raise ValueError("source.kind must be illustrative, manufacturer, or measured")
        if self.kind == "manufacturer" and not self.url:
            raise ValueError("Manufacturer dimensions require a source URL")
        if self.kind != "illustrative" and (not self.checked_on or not self.notes):
            raise ValueError("Verified templates require checked_on and source notes")
        for item in fields(self):
            if not isinstance(getattr(self, item.name), str):
                raise ValueError(f"source.{item.name} must be text")
        if self.document_sha256 and not re.fullmatch(r"[0-9a-f]{64}", self.document_sha256):
            raise ValueError("source.document_sha256 must be 64 lowercase hexadecimal characters")


@dataclass(frozen=True)
class PlateTemplate:
    template_id: str
    rows: int
    columns: int
    width_mm: float
    height_mm: float
    well_diameter_mm: float
    pitch_x_mm: float
    pitch_y_mm: float
    a1_x_mm: float
    a1_y_mm: float
    schema_version: int = 1
    units: str = "mm"
    version: str = "1"
    name: str = ""
    manufacturer: str = ""
    catalog_number: str = ""
    corner_radius_mm: float = 3.0
    well_bottom_diameter_mm: float | None = None
    plate_height_mm: float | None = None
    well_depth_mm: float | None = None
    well_outer_diameter_mm: float | None = None
    outline_simplified: bool = False
    assumed_fields: tuple[str, ...] = ()
    source: TemplateSource = field(default_factory=TemplateSource)

    def __post_init__(self):
        if not isinstance(self.template_id, str) or not self.template_id.strip():
            raise ValueError("template_id must be nonempty text")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Only template schema_version 1 is supported")
        if self.units != "mm":
            raise ValueError("Template units must be mm")
        for name in ("version", "name", "manufacturer", "catalog_number"):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f"{name} must be text")
        if not isinstance(self.source, TemplateSource):
            raise ValueError("source must be a TemplateSource")
        if type(self.outline_simplified) is not bool:
            raise ValueError("outline_simplified must be a boolean")
        assumed = self.assumed_fields
        geometry_fields = {
            "width_mm",
            "height_mm",
            "well_diameter_mm",
            "pitch_x_mm",
            "pitch_y_mm",
            "a1_x_mm",
            "a1_y_mm",
            "corner_radius_mm",
        }
        if (
            not isinstance(assumed, (list, tuple))
            or any(not isinstance(name, str) or name not in geometry_fields for name in assumed)
            or len(set(assumed)) != len(assumed)
        ):
            raise ValueError("assumed_fields must list distinct geometry field names")
        object.__setattr__(self, "assumed_fields", tuple(assumed))
        for name in ("rows", "columns"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.rows * self.columns > 10000:
            raise ValueError("Templates are limited to 10000 wells")
        for name in ("width_mm", "height_mm", "well_diameter_mm", "pitch_x_mm", "pitch_y_mm"):
            object.__setattr__(self, name, finite_number(getattr(self, name), name, positive=True))
        for name in ("a1_x_mm", "a1_y_mm", "corner_radius_mm"):
            object.__setattr__(self, name, finite_number(getattr(self, name), name))
        for name in (
            "well_bottom_diameter_mm",
            "plate_height_mm",
            "well_depth_mm",
            "well_outer_diameter_mm",
        ):
            if getattr(self, name) is not None:
                object.__setattr__(
                    self, name, finite_number(getattr(self, name), name, positive=True)
                )
        radius = self.well_diameter_mm / 2
        corner = self.corner_radius_mm
        if corner > min(self.width_mm, self.height_mm) / 2:
            raise ValueError("corner_radius_mm exceeds the plate dimensions")
        if (self.columns > 1 and self.well_diameter_mm > self.pitch_x_mm) or (
            self.rows > 1 and self.well_diameter_mm > self.pitch_y_mm
        ):
            raise ValueError("Wells overlap: diameter exceeds center-to-center spacing")
        for well in self.wells():
            x, y = self.center(well)
            if not (
                radius <= x <= self.width_mm - radius and radius <= y <= self.height_mm - radius
            ):
                raise ValueError(f"Well {well} extends outside the plate")
            # Inside a rounded rectangle: rectangle's signed distance + well radius <= 0.
            qx = abs(x - self.width_mm / 2) - (self.width_mm / 2 - corner)
            qy = abs(y - self.height_mm / 2) - (self.height_mm / 2 - corner)
            distance = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - corner
            if distance + radius > 1e-8:
                raise ValueError(f"Well {well} extends into the rounded plate corner")

    @property
    def well_count(self) -> int:
        return self.rows * self.columns

    def wells(self) -> list[str]:
        return [
            f"{row_name(row)}{column + 1}"
            for row in range(self.rows)
            for column in range(self.columns)
        ]

    def center(self, well: str) -> tuple[float, float]:
        well = normalize_well(well)
        match = re.fullmatch(r"([A-Z]+)([0-9]+)", well)
        letters, column_text = match.groups()
        row = 0
        for letter in letters:
            row = row * 26 + ord(letter) - 64
        row -= 1
        column = int(column_text) - 1
        if row >= self.rows or column >= self.columns:
            raise ValueError(f"Well {well} is outside template {self.template_id}")
        return self.a1_x_mm + column * self.pitch_x_mm, self.a1_y_mm + row * self.pitch_y_mm

    @classmethod
    def from_dict(cls, value: dict) -> PlateTemplate:
        if not isinstance(value, dict):
            raise ValueError("Template must be a JSON object")
        value = dict(value)
        allowed = {item.name for item in fields(cls)}
        if unknown := value.keys() - allowed:
            raise ValueError(f"Unknown template fields: {', '.join(sorted(unknown))}")
        if "source" in value:
            if not isinstance(value["source"], dict):
                raise ValueError("source must be a JSON object")
            try:
                value["source"] = TemplateSource(**value["source"])
            except TypeError as exc:
                raise ValueError(f"Invalid source metadata: {exc}") from exc
        try:
            return cls(**value)
        except TypeError as exc:
            raise ValueError(f"Invalid template: {exc}") from exc

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return path


def list_templates() -> list[str]:
    return sorted(
        item.name.removesuffix(".json")
        for item in files("plateplot").joinpath("templates").iterdir()
        if item.name.endswith(".json")
    )


def load_template(value: str | int | Path | PlateTemplate) -> PlateTemplate:
    if isinstance(value, PlateTemplate):
        return value
    name = str(value)
    aliases = {
        "96": "nunc-167008",
        "cell-culture-96": "nunc-167008",
        "6": "nunc-140675-schematic",
        "cell-culture-6": "nunc-140675-schematic",
        "cell-culture-24": "nunc-142485",
    }
    if name in aliases:
        name = aliases[name]
    elif name.isdigit():
        name = f"generic-{name}"
    if name in list_templates():
        text = files("plateplot").joinpath("templates", name + ".json").read_text(encoding="utf-8")
    else:
        path = Path(name)
        if not path.is_file():
            raise ValueError(f"Unknown template {name!r}; use a built-in name or a JSON file")
        text = path.read_text(encoding="utf-8")
    return PlateTemplate.from_dict(json.loads(text))
