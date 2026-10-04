import json

import pytest

from plateplot import PlateTemplate, TemplateSource, list_templates, load_template
from plateplot.models import normalize_well, row_name


@pytest.mark.parametrize(
    "count,rows,columns,last",
    [
        (12, 3, 4, "C4"),
        (24, 4, 6, "D6"),
        (48, 6, 8, "F8"),
        (96, 8, 12, "H12"),
        (384, 16, 24, "P24"),
    ],
)
def test_builtins(count, rows, columns, last):
    template = load_template(count)
    assert (template.rows, template.columns) == (rows, columns)
    assert template.wells()[0] == "A1"
    assert template.wells()[-1] == last
    assert len(template.wells()) == count
    assert template.source.kind == "illustrative"
    x, y = template.center("B02")
    assert x == pytest.approx(template.a1_x_mm + template.pitch_x_mm)
    assert y == pytest.approx(template.a1_y_mm + template.pitch_y_mm)


def test_template_roundtrip(tmp_path):
    value = load_template(96).to_dict()
    value.update(template_id="measured-example", well_diameter_mm=6.1)
    value["source"] = {
        "kind": "measured",
        "checked_on": "2026-10-05",
        "notes": "Synthetic test fixture only.",
    }
    template = PlateTemplate.from_dict(value)
    path = template.save(tmp_path / "measured.json")
    assert load_template(path) == template
    assert json.loads(path.read_text())["well_diameter_mm"] == 6.1


@pytest.mark.parametrize(
    "change",
    [
        {"units": "cm"},
        {"rows": 8.5},
        {"rows": True},
        {"schema_version": True},
        {"columns": 0},
        {"width_mm": float("nan")},
        {"pitch_y_mm": 0},
        {"well_diameter_mm": 10},
        {"a1_x_mm": 1},
        {"a1_y_mm": 80},
        {"width_mm": float("inf")},
        {"corner_radius_mm": 100},
        {"diameter_mm": 6},
        {"source": "manufacturer"},
        {"source": {"kind": "unknown"}},
        {"source": {"kind": "manufacturer", "checked_on": "2026-10-05", "notes": "test"}},
    ],
)
def test_reject_invalid_templates(change):
    value = load_template(96).to_dict()
    value.update(change)
    with pytest.raises(ValueError):
        PlateTemplate.from_dict(value)


def test_rounded_corner_bounds():
    with pytest.raises(ValueError, match="rounded plate corner"):
        PlateTemplate("small", 1, 1, 10, 10, 2, 3, 3, 1, 1, corner_radius_mm=4)


@pytest.mark.parametrize("address", ["A0", "A-1", "1A", "", "A1x"])
def test_invalid_addresses(address):
    with pytest.raises(ValueError):
        normalize_well(address)


def test_addresses():
    assert normalize_well(" a001 ") == "A1"
    assert row_name(0) == "A"
    assert row_name(26) == "AA"
    assert row_name(31) == "AF"
    with pytest.raises(ValueError, match="outside"):
        load_template(96).center("I1")
    with pytest.raises(ValueError, match="outside"):
        load_template(96).center("A13")
    assert list_templates() == [
        "generic-12",
        "generic-24",
        "generic-384",
        "generic-48",
        "generic-96",
        "nunc-161093",
        "nunc-167008",
    ]
    with pytest.raises(ValueError):
        TemplateSource(kind="manufacturer", url="https://example.org")


@pytest.mark.parametrize("catalog", ["167008", "161093"])
def test_nunc_drawing_2817_v10(catalog, tmp_path):
    template = load_template(f"nunc-{catalog}")
    assert template.catalog_number == catalog
    assert template.well_count == 96
    assert (template.width_mm, template.height_mm) == (127.76, 85.48)
    assert template.well_diameter_mm == 6.97
    assert template.well_bottom_diameter_mm == 6.17
    assert template.well_outer_diameter_mm == 8.4
    assert template.plate_height_mm == 14.4
    assert template.well_depth_mm == 11.4
    assert (template.pitch_x_mm, template.pitch_y_mm) == (9, 9)
    assert template.center("A1") == pytest.approx((14.3, 11.18))
    assert template.center("H12") == pytest.approx((113.3, 74.18))
    assert template.height_mm - template.center("H1")[1] == pytest.approx(11.3)
    assert template.width_mm - template.center("A12")[0] == pytest.approx(14.46)
    assert template.source.kind == "manufacturer"
    assert template.source.drawing_number == "2817"
    assert template.source.drawing_version == "10"
    assert template.source.document_sha256 == (
        "a042684dec585378c7772da1cee73c391e43825450c2e9b561ebc1657114c122"
    )
    assert template.outline_simplified
    assert template.corner_radius_mm == 0
    assert load_template(template.save(tmp_path / "roundtrip.json")) == template


@pytest.mark.parametrize(
    "change",
    [
        {"plate_height_mm": -1},
        {"well_depth_mm": float("nan")},
        {"well_outer_diameter_mm": 0},
        {"outline_simplified": "yes"},
        {"source": {"document_sha256": "bad"}},
    ],
)
def test_invalid_additional_geometry(change):
    value = load_template(96).to_dict()
    value.update(change)
    with pytest.raises(ValueError):
        PlateTemplate.from_dict(value)
