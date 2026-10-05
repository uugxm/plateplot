"""Vector rendering. Geometry stays in mm; page scale is explicit."""

from __future__ import annotations

import math
import os
import tempfile
import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

import matplotlib as mpl
from matplotlib import colormaps, font_manager
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import Normalize, is_color_like, to_hex, to_rgba
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.ft2font import FT2Font
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle

from .data import WellData, prepare_data
from .models import PlateTemplate, finite_number, load_template, row_name

PALETTE = ["#80B1D3", "#FDB462", "#8DD3C7", "#BEBADA", "#FB8072", "#B3DE69", "#FCCDE5", "#D9D9D9"]


@dataclass(frozen=True)
class RenderResult:
    path: Path
    width_mm: float
    height_mm: float
    scale: float
    label_font_sizes: Mapping[str, float]
    notices: tuple[str, ...]


def _font(font_path: str | Path | None) -> FontProperties:
    if font_path is not None:
        path = Path(font_path)
        if not path.is_file():
            raise ValueError(f"Font file does not exist: {path}")
        return FontProperties(fname=str(path))
    available = {item.name for item in font_manager.fontManager.ttflist}
    for name in (
        "Noto Sans CJK SC",
        "Noto Sans SC",
        "PingFang SC",
        "Arial Unicode MS",
        "Hiragino Sans GB",
        "Heiti SC",
    ):
        if name in available:
            return FontProperties(family=name)
    return FontProperties(family="DejaVu Sans")


def _check_glyphs(strings: Iterable[str], font: FontProperties) -> None:
    face = FT2Font(font_manager.findfont(font, fallback_to_default=False))
    supported = face.get_charmap()
    missing = sorted(
        {
            char
            for text in strings
            for char in text
            if not char.isspace() and ord(char) not in supported
        }
    )
    if missing:
        display = " ".join(f"{char} (U+{ord(char):04X})" for char in missing[:12])
        raise ValueError(f"Font is missing glyphs: {display}. Supply --font-file / font_path.")


def _wrap(text: str, width_px: float, renderer, font: FontProperties) -> str:
    def width(value):
        return renderer.get_text_width_height_descent(value, font, ismath=False)[0]

    wrapped = []
    for paragraph in text.split("\n"):
        if not paragraph:
            wrapped.append("")
            continue
        line = ""
        for character in paragraph:
            trial = line + character
            if line and width(trial) > width_px:
                # Prefer a word boundary; split long unbroken identifiers by character.
                if " " in line and line.rfind(" ") > 0:
                    head, tail = line.rsplit(" ", 1)
                    wrapped.append(head)
                    line = tail + character
                    # The tail is shorter than the previously accepted line.
                    if width(line) > width_px:
                        wrapped.append(tail)
                        line = character
                else:
                    wrapped.append(line)
                    line = character
            else:
                line = trial
        wrapped.append(line.strip())
    return "\n".join(wrapped)


def _text(ax, x, y, text, font, *, size=8, color="#243247", ha="center", **kwargs):
    return ax.text(
        x,
        y,
        text,
        fontsize=size,
        fontproperties=font,
        color=color,
        ha=ha,
        va="center",
        linespacing=1.05,
        parse_math=False,
        **kwargs,
    )


def _fit_label(ax, x, y, text, diameter, renderer, font, size, minimum):
    # A square inscribed in the circle keeps every corner of the text inside the well.
    a = ax.transData.transform((0, 0))
    b = ax.transData.transform((diameter * 0.67, diameter * 0.67))
    max_width, max_height = abs(b[0] - a[0]), abs(b[1] - a[1])
    # Prefer complete identifiers / concentrations on their original lines.
    # Only introduce new line breaks if even the minimum size cannot fit them.
    for wrap in (False, True):
        candidate = size
        while True:
            properties = font.copy()
            properties.set_size(candidate)
            value = _wrap(text, max_width, renderer, properties) if wrap else text
            artist = _text(ax, x, y, value, font, size=candidate)
            box = artist.get_window_extent(renderer=renderer)
            if box.width <= max_width + 0.01 and box.height <= max_height + 0.01:
                return artist, candidate
            artist.remove()
            if candidate <= minimum:
                break
            candidate = max(minimum, candidate - 0.5)
    return None, minimum


def _colors(records, color_by, palette, empty_color, cmap):
    valid = {"group", "concentration", "fill_color", "none"}
    if color_by not in valid:
        raise ValueError(f"color_by must be one of {sorted(valid)}")
    if not is_color_like(empty_color):
        raise ValueError(f"Invalid empty_color: {empty_color!r}")
    if palette is not None and (
        not isinstance(palette, Mapping) or any(not is_color_like(c) for c in palette.values())
    ):
        raise ValueError("palette must map group names to valid colors")
    groups = sorted({row.group for row in records.values() if row.group})
    if len(groups) > len(PALETTE) and palette is None and color_by == "group":
        raise ValueError("More than 8 groups: supply an explicit palette to avoid repeated colors")
    group_colors = {
        group: (palette or {}).get(group, PALETTE[i % len(PALETTE)])
        for i, group in enumerate(groups)
    }
    if (
        color_by == "group"
        and len(groups) > len(PALETTE)
        and any(group not in (palette or {}) for group in groups)
    ):
        raise ValueError("For more than 8 groups, palette must specify every group")
    cmap_object = colormaps[cmap]
    numeric = [row for row in records.values() if row.concentration is not None]
    scale_info = None
    if color_by == "concentration" and numeric:
        units = {row.concentration_unit for row in numeric}
        if len(units) != 1:
            raise ValueError(
                "Concentration colors require one consistent unit; convert units first"
            )
        low = min(row.concentration for row in numeric)
        high = max(row.concentration for row in numeric)
        norm = Normalize(low, high) if high > low else None
        scale_info = (low, high, next(iter(units)), cmap_object)
    else:
        norm = None
    fills = {}
    entries = set()
    for well, row in records.items():
        color = empty_color
        if color_by == "group" and row.group:
            color = group_colors[row.group]
        elif color_by == "concentration" and row.concentration is not None:
            color = cmap_object(float(norm(row.concentration)) if norm is not None else 0.5)
        if row.fill_color and color_by != "none":
            color = row.fill_color
        fills[well] = color
        if color_by == "group" and row.group:
            entries.add((row.group, to_hex(color, keep_alpha=True)))
        elif row.fill_color and color_by != "none":
            entries.add((f"Manual {row.fill_color}", to_hex(color, keep_alpha=True)))
    return fills, sorted(entries), scale_info


def _contrast(color):
    red, green, blue, alpha = to_rgba(color)
    red, green, blue = [channel * alpha + 1 - alpha for channel in (red, green, blue)]
    return "#FFFFFF" if 0.2126 * red + 0.7152 * green + 0.0722 * blue < 0.48 else "#172B42"


def draw_plate(
    template: str | int | Path | PlateTemplate = 96,
    data: str | Path | Iterable[WellData | Mapping] | None = None,
    *,
    output: str | Path,
    label_fields: Sequence[str] = ("sample_name", "concentration"),
    color_by: str = "group",
    mode: str = "annotation",
    scale: float | None = None,
    title: str | None = None,
    show_title: bool = False,
    show_parameters: bool = False,
    palette: Mapping[str, str] | None = None,
    empty_color: str = "#FFFFFF",
    cmap: str = "viridis",
    font_size: float = 9,
    min_font_size: float = 4,
    coordinate_position: str = "inside",
    coordinate_font_size: float = 16,
    well_line_width: float = 0.85,
    show_scale_bar: bool = True,
    scale_bar_mm: float = 10,
    font_path: str | Path | None = None,
    svg_text: str = "text",
    show_legend: bool = True,
    show_dimensions: bool = False,
    overflow: str = "error",
) -> RenderResult:
    """Draw all wells; atomic SVG/PDF export with preserved physical geometry.

    The default 96-well cell culture plate is Nunc 167008 (161093 shares its geometry).
    Row/column coordinates default to 16 pt inside the plate's left/top margins.
    A 10 mm scale bar defaults to the bottom-right margin inside the plate.
    Plate title and parameters are hidden unless requested; an explicit title is shown.
    ``physical`` fixes scale=1; ``annotation`` defaults to scale=2 (3 for 384).
    Explicit fill colors override automatic group/concentration colors.
    Overlong labels raise by default. ``overflow='warn'`` omits the entire label.
    """
    template = load_template(template)
    records = prepare_data(data, template)
    output = Path(output)
    extension = output.suffix.lower()
    if extension not in {".svg", ".pdf"}:
        raise ValueError("Output must end in .svg or .pdf")
    if mode not in {"physical", "annotation"}:
        raise ValueError("mode must be physical or annotation")
    scale = finite_number(
        scale
        if scale is not None
        else (1 if mode == "physical" else 3 if template.well_count >= 384 else 2),
        "scale",
        positive=True,
    )
    if mode == "physical" and scale != 1:
        raise ValueError("physical mode requires scale=1")
    if svg_text not in {"text", "path"}:
        raise ValueError("svg_text must be text or path")
    if overflow not in {"error", "warn"}:
        raise ValueError("overflow must be error or warn")
    font_size = finite_number(font_size, "font_size", positive=True)
    min_font_size = finite_number(min_font_size, "min_font_size", positive=True)
    coordinate_font_size = finite_number(
        coordinate_font_size, "coordinate_font_size", positive=True
    )
    well_line_width = finite_number(well_line_width, "well_line_width", positive=True)
    scale_bar_mm = finite_number(scale_bar_mm, "scale_bar_mm", positive=True)
    if coordinate_position not in {"inside", "outside"}:
        raise ValueError("coordinate_position must be inside or outside")
    if min_font_size > font_size:
        raise ValueError("min_font_size must not exceed font_size")
    if (
        not isinstance(label_fields, Sequence)
        or isinstance(label_fields, str)
        or any(not isinstance(f, str) for f in label_fields)
    ):
        raise ValueError("label_fields must be a sequence of field names")
    known = {
        "well",
        "sample_name",
        "group",
        "concentration",
        "concentration_unit",
        "fill_color",
        "label",
    }
    extras = {key for row in records.values() for key in row.extra}
    if unknown := set(label_fields) - known - extras:
        raise ValueError(f"Unknown label fields: {', '.join(sorted(unknown))}")
    labels = {}
    for well in template.wells():
        row = records.get(well, WellData(well))
        lines = [
            row.text(name) if name in known or name in row.extra else "" for name in label_fields
        ]
        labels[well] = "\n".join(line for line in lines if line)
    fills, legend, scale_info = _colors(records, color_by, palette, empty_color, cmap)
    font = _font(font_path)
    show_title = show_title or title is not None
    title = (template.name or f"{template.well_count}-well plate") if title is None else title
    if not isinstance(title, str):
        raise ValueError("title must be text")
    # Wrapping legend text reserves sufficient page height before any artwork is drawn.
    left = 12.0 if coordinate_position == "outside" else 3.0
    right = 16.0 if show_dimensions else 3.0
    if show_title:
        top = 23.0 if show_parameters else 15.0
    elif show_parameters:
        top = 12.0
    else:
        top = 8.0 if coordinate_position == "outside" else 3.0
    width = template.width_mm + left + right
    legend_columns = max(1, min(3, int(template.width_mm / 35)))
    legend_rows = math.ceil(len(legend) / legend_columns) if show_legend else 0
    legend_height = legend_rows * 9
    colorbar_height = 17 if show_legend and scale_info else 0
    bottom = (
        (16 if show_parameters or legend_rows or colorbar_height else 3)
        + legend_height
        + colorbar_height
        + (7 if show_dimensions else 0)
    )
    height = template.height_mm + top + bottom
    notices = []
    if template.source.kind == "illustrative":
        notices.append("Illustrative template: dimensions are not verified against a product.")
    if template.outline_simplified:
        notices.append("Outline simplified: outer corner/chamfer details are not represented.")
    footer = (
        f"{template.source.kind.capitalize()} dimensions | "
        f"{template.template_id} @ {template.version} | circular top-view schematic"
    )
    if template.outline_simplified:
        footer = footer.replace("circular top-view schematic", "simplified outline")
    subtitle = (
        f"{template.rows} x {template.columns} | "
        f"{template.width_mm:g} x {template.height_mm:g} mm | "
        f"well diameter {template.well_diameter_mm:g} mm | scale {scale:g}:1"
    )
    _check_glyphs(
        [
            title if show_title else "",
            subtitle if show_parameters else "",
            footer if show_parameters else "",
            *labels.values(),
            *(label for label, _ in legend),
            scale_info[2] if scale_info else "",
        ],
        font,
    )
    fonts = {}
    # Avoid pyplot, global backend changes, tight bounding boxes, and rasterized colorbars.
    with mpl.rc_context(
        {
            "svg.fonttype": "none" if svg_text == "text" else "path",
            "svg.hashsalt": "plateplot",
            "pdf.fonttype": 42,
            "text.usetex": False,
            "savefig.bbox": None,
        }
    ):
        fig = Figure(figsize=(width * scale / 25.4, height * scale / 25.4), dpi=144)
        canvas = FigureCanvasAgg(fig)
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set_xlim(-left, template.width_mm + right)
        ax.set_ylim(template.height_mm + bottom, -top)
        ax.set_aspect("equal", adjustable="box")
        ax.set_axis_off()
        renderer = canvas.get_renderer()
        metadata_artists = []
        if show_title:
            metadata_artists.append(
                _text(
                    ax,
                    0,
                    -16 if show_parameters else -7,
                    title,
                    font,
                    size=14,
                    ha="left",
                    weight="bold",
                )
            )
        if show_parameters:
            metadata_artists.append(
                _text(ax, 0, -10 if show_title else -5, subtitle, font, size=7, ha="left")
            )
        outline = FancyBboxPatch(
            (0, 0),
            template.width_mm,
            template.height_mm,
            boxstyle=f"round,pad=0,rounding_size={template.corner_radius_mm}",
            linewidth=1,
            edgecolor="#59708A",
            facecolor="#F5F8FC",
            gid="plate-outline",
        )
        ax.add_patch(outline)
        left_gap = template.a1_x_mm - template.well_diameter_mm / 2
        top_gap = template.a1_y_mm - template.well_diameter_mm / 2

        def coordinate(x, y, text, identity, box):
            artist = _text(
                ax, x, y, text, font, size=coordinate_font_size, weight="bold", gid=identity
            )
            if coordinate_position == "inside":
                extent = artist.get_window_extent(renderer).transformed(ax.transData.inverted())
                xs, ys = extent.get_points().T
                if (
                    min(xs) < box[0] + 0.25
                    or max(xs) > box[2] - 0.25
                    or min(ys) < box[1] + 0.25
                    or max(ys) > box[3] - 0.25
                ):
                    raise ValueError(
                        "Row/column coordinates cannot fit inside the plate margin; "
                        "reduce coordinate_font_size / --coordinate-font-size, increase "
                        "annotation scale, or use coordinate_position='outside' / "
                        "--coordinate-position outside"
                    )

        for row in range(template.rows):
            y = template.a1_y_mm + row * template.pitch_y_mm
            coordinate(
                left_gap / 2 if coordinate_position == "inside" else -3,
                y,
                row_name(row),
                f"coordinate-row-{row_name(row)}",
                (0, y - template.pitch_y_mm / 2, left_gap, y + template.pitch_y_mm / 2),
            )
        for column in range(template.columns):
            x = template.a1_x_mm + column * template.pitch_x_mm
            coordinate(
                x,
                top_gap / 2 if coordinate_position == "inside" else -3,
                str(column + 1),
                f"coordinate-column-{column + 1}",
                (x - template.pitch_x_mm / 2, 0, x + template.pitch_x_mm / 2, top_gap),
            )
        for well in template.wells():
            x, y = template.center(well)
            color = fills.get(well, empty_color)
            ax.add_patch(
                Circle(
                    (x, y),
                    template.well_diameter_mm / 2,
                    facecolor=color,
                    edgecolor="#8495AA",
                    linewidth=well_line_width,
                    gid=f"well-{well}",
                )
            )
            if not labels[well]:
                continue
            artist, size = _fit_label(
                ax,
                x,
                y,
                labels[well],
                template.well_diameter_mm,
                renderer,
                font,
                font_size,
                min_font_size,
            )
            if artist is None:
                message = (
                    f"{well}: label cannot fit at {min_font_size:g} pt; "
                    "increase annotation scale, use fewer fields or a shorter label"
                )
                if overflow == "error":
                    raise ValueError(message)
                notices.append(message + "; label omitted")
                warnings.warn(message + "; label omitted", UserWarning, stacklevel=2)
            else:
                artist.set_color(_contrast(color))
                artist.set_gid(f"label-{well}")
                fonts[well] = size
                if size < 6:
                    notices.append(f"{well}: label uses small text ({size:g} pt)")
        if show_scale_bar:
            last_y = template.a1_y_mm + (template.rows - 1) * template.pitch_y_mm
            well_bottom = last_y + template.well_diameter_mm / 2
            bottom_gap = template.height_mm - well_bottom
            end_x = template.width_mm - max(4, template.corner_radius_mm + 0.5)
            start_x = end_x - scale_bar_mm
            bar_y = well_bottom + bottom_gap * 0.72
            label_y = well_bottom + bottom_gap * 0.28
            tick_half = min(0.6, bottom_gap * 0.1)
            label = _text(
                ax,
                (start_x + end_x) / 2,
                label_y,
                f"{scale_bar_mm:g} mm",
                font,
                size=8,
                gid="scale-bar-label",
            )
            box = label.get_window_extent(renderer).transformed(ax.transData.inverted())
            xs, ys = box.get_points().T
            if (
                start_x < max(0.5, template.corner_radius_mm)
                or min(xs) < 0.5
                or max(xs) > template.width_mm - 0.5
                or min(ys) < well_bottom + 0.25
                or max(ys) > bar_y - tick_half - 0.25
                or bar_y + tick_half > template.height_mm - 0.25
            ):
                raise ValueError(
                    "Scale bar cannot fit inside the bottom plate margin; reduce "
                    "scale_bar_mm / --scale-bar-mm, increase annotation scale, or use "
                    "show_scale_bar=False / --no-scale-bar"
                )
            ax.plot(
                [start_x, end_x],
                [bar_y, bar_y],
                color="#243247",
                linewidth=1.2,
                solid_capstyle="butt",
                gid="scale-bar",
            )
            for name, x in [("left", start_x), ("right", end_x)]:
                ax.plot(
                    [x, x],
                    [bar_y - tick_half, bar_y + tick_half],
                    color="#243247",
                    linewidth=1.2,
                    solid_capstyle="butt",
                    gid=f"scale-bar-tick-{name}",
                )
        base_y = template.height_mm + 9
        if show_dimensions:
            for start, end in [
                ((0, template.height_mm + 4), (template.width_mm, template.height_mm + 4)),
                ((template.width_mm + 5, 0), (template.width_mm + 5, template.height_mm)),
            ]:
                ax.add_patch(
                    FancyArrowPatch(
                        start,
                        end,
                        arrowstyle="|-|",
                        mutation_scale=3,
                        linewidth=0.5,
                        color="#59708A",
                    )
                )
            _text(
                ax,
                template.width_mm / 2,
                template.height_mm + 7,
                f"{template.width_mm:g} mm",
                font,
                size=6,
            )
            _text(
                ax,
                template.width_mm + 9,
                template.height_mm / 2,
                f"{template.height_mm:g} mm",
                font,
                size=6,
                rotation=90,
            )
            base_y += 7
        if show_legend:
            if scale_info:
                low, high, unit, color_map = scale_info
                _text(
                    ax,
                    0,
                    base_y,
                    f"Concentration ({unit or 'unit unspecified'})",
                    font,
                    size=7,
                    ha="left",
                )
                bar_width = template.width_mm * 0.65
                for i in range(64):
                    fraction = (i + 0.5) / 64 if high > low else 0.5
                    ax.add_patch(
                        Rectangle(
                            (i * bar_width / 64, base_y + 3),
                            bar_width / 64,
                            2,
                            facecolor=color_map(fraction),
                            edgecolor="none",
                        )
                    )
                _text(ax, 0, base_y + 8, f"{low:g}", font, size=6, ha="left")
                _text(ax, bar_width, base_y + 8, f"{high:g}", font, size=6, ha="right")
                base_y += colorbar_height
            cell_width = template.width_mm / legend_columns
            for i, (label, color) in enumerate(legend):
                x = i % legend_columns * cell_width
                y = base_y + i // legend_columns * 9
                ax.add_patch(
                    Rectangle(
                        (x, y - 1.2), 2.4, 2.4, facecolor=color, edgecolor="#8495AA", linewidth=0.4
                    )
                )
                properties = font.copy()
                properties.set_size(6)
                max_px = (cell_width - 6) * scale * fig.dpi / 25.4
                text = _wrap(label, max_px, renderer, properties)
                if len(text.splitlines()) > 3:
                    raise ValueError(
                        "Legend label is too long; shorten group names or increase scale"
                    )
                _text(ax, x + 4, y, text, font, size=6, ha="left")
        if show_parameters:
            metadata_artists.append(
                _text(
                    ax,
                    0,
                    template.height_mm + bottom - 4,
                    footer,
                    font,
                    size=6,
                    ha="left",
                    color="#59708A",
                )
            )
        # Titles / provenance must also fit instead of silently clipping outside the page.
        canvas.draw()
        for artist in metadata_artists:
            box = artist.get_window_extent(renderer=renderer)
            if box.x1 > fig.bbox.width - 4 or box.x0 < 0:
                raise ValueError(
                    "Title or template metadata exceeds page width; shorten it or scale up"
                )
        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=".plateplot-", suffix=extension, dir=output.parent
        )
        os.close(descriptor)
        temp_path = Path(temp_name)
        try:
            metadata = {"Creator": "PlatePlot", "Title": title}
            if extension == ".svg":
                metadata.update({"Date": None, "Description": footer})
            else:
                metadata.update({"CreationDate": None, "ModDate": None, "Subject": footer})
            fig.savefig(temp_path, format=extension[1:], bbox_inches=None, metadata=metadata)
            if extension == ".svg":
                # SVG's page declares physical mm; viewBox remains in Matplotlib's points.
                tree = ET.parse(temp_path)
                root = tree.getroot()
                root.set("width", f"{width * scale:.9g}mm")
                root.set("height", f"{height * scale:.9g}mm")
                tree.write(temp_path, encoding="utf-8", xml_declaration=True)
            os.replace(temp_path, output)
        finally:
            temp_path.unlink(missing_ok=True)
            fig.clear()
    return RenderResult(output, width * scale, height * scale, scale, fonts, tuple(notices))
