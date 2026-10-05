import re
from xml.etree import ElementTree as ET

import pytest
from matplotlib import font_manager
from pypdf import PdfReader

from plateplot import draw_plate, load_template

SVG = "{http://www.w3.org/2000/svg}"


def node(root, identity):
    return root.find(f".//*[@id='{identity}']")


def bounds(root, identity):
    path = node(root, identity).find(f"{SVG}path")
    numbers = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", path.get("d"))]
    xs, ys = numbers[0::2], numbers[1::2]
    return min(xs), min(ys), max(xs), max(ys)


@pytest.mark.parametrize("count", [6, 12, 24, 48, 96, 384])
def test_all_wells_vector_and_editable_text(tmp_path, count):
    result = draw_plate(
        count,
        [{"well": "A1", "sample_name": "S1", "group": "Control"}],
        output=tmp_path / f"plate-{count}.svg",
    )
    root = ET.parse(result.path).getroot()
    assert len(root.findall(".//*[@id]")) > count
    assert sum(element.get("id", "").startswith("well-") for element in root.iter()) == count
    assert node(root, "label-A1") is not None
    assert root.findall(f".//{SVG}text")
    assert not root.findall(f".//{SVG}image")
    assert root.get("width").endswith("mm")


@pytest.mark.parametrize("scale", [1, 2.5])
@pytest.mark.parametrize(
    "name",
    [
        "generic-96",
        "nunc-167008",
        "nunc-161093",
        "nunc-140675-schematic",
        "nunc-142485",
        "nunc-144530",
        "nunc-150628-schematic",
    ],
)
def test_physical_geometry_in_svg(tmp_path, scale, name):
    template = load_template(name)
    result = draw_plate(
        template,
        output=tmp_path / "plate.svg",
        scale=scale,
        mode="physical" if scale == 1 else "annotation",
        show_dimensions=True,
        coordinate_font_size=12,
        show_scale_bar=False,
    )
    root = ET.parse(result.path).getroot()
    x0, y0, x1, y1 = bounds(root, "well-A1")
    factor = 72 / 25.4 * scale
    assert x1 - x0 == pytest.approx(template.well_diameter_mm * factor, abs=1e-5)
    assert y1 - y0 == pytest.approx(template.well_diameter_mm * factor, abs=1e-5)
    bx0, _, bx1, _ = bounds(root, "well-A2")
    assert (bx0 + bx1 - x0 - x1) / 2 == pytest.approx(template.pitch_x_mm * factor, abs=1e-5)
    _, by0, _, by1 = bounds(root, "well-B1")
    assert (by0 + by1 - y0 - y1) / 2 == pytest.approx(template.pitch_y_mm * factor, abs=1e-5)
    ox0, oy0, ox1, oy1 = bounds(root, "plate-outline")
    assert ox1 - ox0 == pytest.approx(template.width_mm * factor, abs=1e-5)
    assert oy1 - oy0 == pytest.approx(template.height_mm * factor, abs=1e-5)
    assert (x0 + x1) / 2 - ox0 == pytest.approx(template.a1_x_mm * factor, abs=1e-5)
    assert (y0 + y1) / 2 - oy0 == pytest.approx(template.a1_y_mm * factor, abs=1e-5)
    view_width = float(root.get("viewBox").split()[2])
    assert view_width == pytest.approx(result.width_mm * 72 / 25.4, abs=1e-5)


def test_manufacturer_outline_notice_is_visible(tmp_path):
    result = draw_plate("nunc-167008", output=tmp_path / "plate.svg", show_parameters=True)
    root = ET.parse(result.path).getroot()
    assert "simplified outline" in " ".join(root.itertext())
    assert any("Outline simplified" in notice for notice in result.notices)
    assert not any("Illustrative" in notice for notice in result.notices)


def test_default_draw_numbers_every_well(tmp_path):
    result = draw_plate(output=tmp_path / "default.svg", label_fields=["well"], color_by="none")
    root = ET.parse(result.path).getroot()
    for well in load_template("nunc-167008").wells():
        assert node(root, f"well-{well}") is not None
        assert well in "".join(node(root, f"label-{well}").itertext())
    assert "Nunc 167008" not in " ".join(e.text or "" for e in root.findall(f".//{SVG}text"))
    x0, _, x1, _ = bounds(root, "well-A1")
    assert x1 - x0 == pytest.approx(6.97 * 72 / 25.4 * result.scale, abs=1e-5)


@pytest.mark.parametrize(
    "show_title,show_parameters", [(False, False), (True, False), (False, True), (True, True)]
)
def test_optional_title_and_parameters(tmp_path, show_title, show_parameters):
    result = draw_plate(
        output=tmp_path / "clean.pdf", show_title=show_title, show_parameters=show_parameters
    )
    page = PdfReader(result.path).pages[0]
    text = page.extract_text()
    assert ("Nunc 167008" in text) == show_title
    assert ("6.97" in text) == show_parameters
    assert ("simplified outline" in text) == show_parameters
    if not show_title and not show_parameters:
        assert result.width_mm / result.scale == pytest.approx(127.76 + 6)
        assert result.height_mm / result.scale == pytest.approx(85.48 + 6)
    assert "nunc-167008" in PdfReader(result.path).metadata.subject


def test_explicit_custom_title_is_shown(tmp_path):
    result = draw_plate(output=tmp_path / "title.pdf", title="Experiment 1")
    text = PdfReader(result.path).pages[0].extract_text()
    assert "Experiment 1" in text
    assert "well diameter" not in text


@pytest.mark.parametrize("position", ["inside", "outside"])
def test_coordinate_placement_and_font(tmp_path, position):
    result = draw_plate(output=tmp_path / "coordinates.svg", coordinate_position=position)
    root = ET.parse(result.path).getroot()
    bx0, by0, bx1, by1 = bounds(root, "plate-outline")
    for row in "ABCDEFGH":
        text = node(root, f"coordinate-row-{row}").find(f"{SVG}text")
        x, y = float(text.get("x")), float(text.get("y"))
        assert (bx0 < x < bounds(root, f"well-{row}1")[0]) == (position == "inside")
        assert by0 < y < by1
        assert "font-size: 16px" in text.get("style")
    for column in range(1, 13):
        text = node(root, f"coordinate-column-{column}").find(f"{SVG}text")
        x, y = float(text.get("x")), float(text.get("y"))
        assert (by0 < y < bounds(root, f"well-A{column}")[1]) == (position == "inside")
        assert bx0 < x < bx1


def test_coordinate_overflow_is_reported(tmp_path):
    with pytest.raises(ValueError, match="coordinates cannot fit"):
        draw_plate(output=tmp_path / "oversize.svg", coordinate_font_size=100)


@pytest.mark.parametrize("scale", [1, 2, 2.5])
@pytest.mark.parametrize("length", [10, 20])
def test_scale_bar_physical_length_and_position(tmp_path, scale, length):
    result = draw_plate(output=tmp_path / "bar.svg", scale=scale, scale_bar_mm=length)
    root = ET.parse(result.path).getroot()
    x0, y0, x1, y1 = bounds(root, "scale-bar")
    bx0, by0, bx1, by1 = bounds(root, "plate-outline")
    assert x1 - x0 == pytest.approx(length * 72 / 25.4 * scale, abs=1e-5)
    assert bx0 < x0 < x1 < bx1
    assert by0 < y0 == y1 < by1
    assert y0 > bounds(root, "well-H12")[3]
    assert f"{length} mm" in "".join(node(root, "scale-bar-label").itertext())
    assert "stroke-width: 0.85" in node(root, "well-A1").find(f"{SVG}path").get("style")


def test_scale_bar_can_be_hidden_and_rejects_overflow(tmp_path):
    result = draw_plate(output=tmp_path / "bar.svg", show_scale_bar=False)
    assert node(ET.parse(result.path).getroot(), "scale-bar") is None
    with pytest.raises(ValueError, match="Scale bar cannot fit"):
        draw_plate(output=tmp_path / "oversize.svg", scale_bar_mm=200)


@pytest.mark.parametrize(
    "name,count",
    [
        ("nunc-140675-schematic", 6),
        ("nunc-150628-schematic", 12),
        ("nunc-142485", 24),
        ("nunc-144530", 24),
    ],
)
def test_new_plate_style_and_assumption_notices(tmp_path, name, count):
    result = draw_plate(name, output=tmp_path / "plate.svg", label_fields=["well"], font_size=16)
    root = ET.parse(result.path).getroot()
    assert sum(e.get("id", "").startswith("well-") for e in root.iter()) == count
    assert any("not manufacturer-verified" in notice for notice in result.notices)
    x0, y0, x1, y1 = bounds(root, "scale-bar")
    bx0, by0, bx1, by1 = bounds(root, "plate-outline")
    assert bx0 < x0 < x1 < bx1 and by0 < y0 == y1 < by1
    assert x1 - x0 == pytest.approx(10 * 72 / 25.4 * result.scale, abs=1e-5)
    visible = " ".join(e.text or "" for e in root.findall(f".//{SVG}text"))
    assert "Nunc" not in visible
    assert "16.3" not in visible


def test_pdf_scale_and_no_raster_images(tmp_path):
    result = draw_plate(
        96,
        [{"well": "A1", "sample_name": "S1", "concentration": 5, "concentration_unit": "µM"}],
        output=tmp_path / "plate.pdf",
        mode="physical",
        color_by="concentration",
    )
    page = PdfReader(result.path).pages[0]
    assert float(page.mediabox.width) == pytest.approx(result.width_mm * 72 / 25.4)
    assert float(page.mediabox.height) == pytest.approx(result.height_mm * 72 / 25.4)
    assert not list(page.images)
    assert "Concentration" in page.extract_text()


def test_numeric_legend_is_vector(tmp_path):
    result = draw_plate(
        96,
        [
            {"well": "A1", "concentration": 0, "concentration_unit": "µM"},
            {"well": "A2", "concentration": 10, "concentration_unit": "µM"},
        ],
        output=tmp_path / "plate.svg",
        color_by="concentration",
    )
    root = ET.parse(result.path).getroot()
    assert not root.findall(f".//{SVG}image")
    assert "Concentration (µM)" in " ".join(root.itertext())


def test_mixed_units_rejected(tmp_path):
    with pytest.raises(ValueError, match="consistent unit"):
        draw_plate(
            96,
            [
                {"well": "A1", "concentration": 1, "concentration_unit": "mM"},
                {"well": "A2", "concentration": 2, "concentration_unit": "µM"},
            ],
            output=tmp_path / "bad.svg",
            color_by="concentration",
        )


def test_long_label_preserves_existing_output_and_warn_omits(tmp_path):
    path = tmp_path / "plate.svg"
    path.write_text("existing output")
    records = [{"well": "A1", "sample_name": "very-long-sample-name-" * 30}]
    with pytest.raises(ValueError, match="label cannot fit"):
        draw_plate(384, records, output=path)
    assert path.read_text() == "existing output"
    with pytest.warns(UserWarning, match="label omitted"):
        result = draw_plate(384, records, output=path, overflow="warn")
    root = ET.parse(path).getroot()
    assert node(root, "well-A1") is not None
    assert node(root, "label-A1") is None
    assert any("omitted" in item for item in result.notices)


def test_literal_xml_and_math_characters(tmp_path):
    result = draw_plate(
        12,
        [{"well": "A1", "sample_name": "$x$ <A&B>"}],
        output=tmp_path / "plate.svg",
        show_legend=False,
    )
    root = ET.parse(result.path).getroot()
    assert "$x$ <A&B>" in " ".join(node(root, "label-A1").itertext())


def test_svg_outlined_text(tmp_path):
    result = draw_plate(
        12, [{"well": "A1", "sample_name": "S1"}], output=tmp_path / "plate.svg", svg_text="path"
    )
    root = ET.parse(result.path).getroot()
    assert not root.findall(f".//{SVG}text")
    assert not root.findall(f".//{SVG}image")
    assert node(root, "label-A1") is not None


@pytest.mark.parametrize(
    "options",
    [
        {"scale": 0},
        {"scale": float("inf")},
        {"scale": 2, "mode": "physical"},
        {"mode": "bad"},
        {"label_fields": "sample_name"},
        {"label_fields": ["typo"]},
        {"min_font_size": 12},
        {"coordinate_font_size": 0},
        {"coordinate_font_size": float("nan")},
        {"coordinate_position": "bad"},
        {"well_line_width": 0},
        {"well_line_width": float("inf")},
        {"scale_bar_mm": -1},
        {"scale_bar_mm": float("nan")},
        {"svg_text": "bad"},
        {"overflow": "bad"},
        {"color_by": "bad"},
        {"palette": {"Control": "bad-color"}},
        {"empty_color": "bad-color"},
    ],
)
def test_invalid_options(tmp_path, options):
    with pytest.raises(ValueError):
        draw_plate(96, output=tmp_path / "plate.svg", **options)


def test_missing_font_glyph(tmp_path):
    font_path = font_manager.findfont("DejaVu Sans")
    with pytest.raises(ValueError, match="missing glyphs"):
        draw_plate(
            96,
            [{"well": "A1", "sample_name": "\U0010ffff"}],
            output=tmp_path / "plate.svg",
            font_path=font_path,
        )


def test_colors_deterministic_and_manual_overrides(tmp_path):
    records = [{"well": "A1", "group": "B"}, {"well": "A2", "group": "A", "fill_color": "#000000"}]
    first = draw_plate(96, records, output=tmp_path / "a.svg")
    second = draw_plate(96, list(reversed(records)), output=tmp_path / "b.svg")
    a, b = ET.parse(first.path).getroot(), ET.parse(second.path).getroot()
    for well in ("A1", "A2"):
        assert node(a, f"well-{well}").find(f"{SVG}path").get("style") == (
            node(b, f"well-{well}").find(f"{SVG}path").get("style")
        )
    # Black may be omitted from the style because it is SVG's default fill.
    style = node(a, "well-A2").find(f"{SVG}path").get("style")
    assert "#80b1d3" not in style and "#fdb462" not in style


def test_too_many_groups_require_palette(tmp_path):
    records = [{"well": f"A{i + 1}", "group": f"G{i}"} for i in range(9)]
    with pytest.raises(ValueError, match="explicit palette"):
        draw_plate(96, records, output=tmp_path / "bad.svg")


def test_custom_extra_labels_on_sparse_data(tmp_path):
    result = draw_plate(
        96, [{"well": "A1", "note": "hello"}], output=tmp_path / "plate.svg", label_fields=["note"]
    )
    assert "A1" in result.label_font_sizes


def test_short_384_identifier_kept_on_one_line(tmp_path):
    result = draw_plate(
        384,
        [{"well": "A1", "sample_name": "S001"}],
        output=tmp_path / "plate.svg",
        label_fields=["sample_name"],
    )
    root = ET.parse(result.path).getroot()
    texts = node(root, "label-A1").findall(f".//{SVG}text")
    assert len(texts) == 1
    assert texts[0].text == "S001"
