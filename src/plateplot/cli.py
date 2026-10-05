"""Command-line interface with concise actionable errors."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .models import list_templates, load_template
from .render import draw_plate


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="plateplot", description="Vector well plate diagrams")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("templates", help="List built-in geometry templates")
    export = commands.add_parser("export-template", help="Save an editable JSON geometry template")
    export.add_argument("template")
    export.add_argument("output", type=Path)
    blank = commands.add_parser("blank-csv", help="Write an empty one-row-per-well CSV")
    blank.add_argument("template")
    blank.add_argument("output", type=Path)
    draw = commands.add_parser("draw", help="Draw an SVG or PDF")
    draw.add_argument(
        "--template",
        default="96",
        help="12/24/48/96/384, name, or JSON file (default: 96 = Nunc 167008)",
    )
    draw.add_argument("--data", type=Path, help="CSV file; omitted for a blank plate")
    draw.add_argument("--output", required=True, type=Path)
    draw.add_argument(
        "--labels", default="sample_name,concentration", help="Comma-separated fields"
    )
    draw.add_argument(
        "--color-by", default="group", choices=["group", "concentration", "fill_color", "none"]
    )
    draw.add_argument("--mode", default="annotation", choices=["annotation", "physical"])
    draw.add_argument("--scale", type=float)
    draw.add_argument("--title")
    draw.add_argument("--palette", type=Path, help="JSON mapping group names to colors")
    draw.add_argument("--cmap", default="viridis")
    draw.add_argument("--font-size", type=float, default=9)
    draw.add_argument("--min-font-size", type=float, default=4)
    draw.add_argument("--font-file", type=Path)
    draw.add_argument("--svg-text", default="text", choices=["text", "path"])
    draw.add_argument("--overflow", default="error", choices=["error", "warn"])
    draw.add_argument("--no-legend", action="store_true")
    draw.add_argument("--dimensions", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "templates":
            for name in list_templates():
                template = load_template(name)
                print(f"{name}\t{template.rows}x{template.columns}\t{template.source.kind}")
        elif arguments.command == "export-template":
            load_template(arguments.template).save(arguments.output)
            print(arguments.output)
        elif arguments.command == "blank-csv":
            with arguments.output.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream, lineterminator="\n")
                writer.writerow(
                    [
                        "well",
                        "sample_name",
                        "group",
                        "concentration",
                        "concentration_unit",
                        "fill_color",
                        "label",
                    ]
                )
                writer.writerows(
                    [well, "", "", "", "", "", ""]
                    for well in load_template(arguments.template).wells()
                )
            print(arguments.output)
        else:
            palette = (
                json.loads(arguments.palette.read_text(encoding="utf-8"))
                if arguments.palette
                else None
            )
            result = draw_plate(
                arguments.template,
                arguments.data,
                output=arguments.output,
                label_fields=tuple(f.strip() for f in arguments.labels.split(",") if f.strip()),
                color_by=arguments.color_by,
                mode=arguments.mode,
                scale=arguments.scale,
                title=arguments.title,
                palette=palette,
                cmap=arguments.cmap,
                font_size=arguments.font_size,
                min_font_size=arguments.min_font_size,
                font_path=arguments.font_file,
                svg_text=arguments.svg_text,
                show_legend=not arguments.no_legend,
                show_dimensions=arguments.dimensions,
                overflow=arguments.overflow,
            )
            print(
                f"{result.path} ({result.width_mm:g} x {result.height_mm:g} mm; "
                f"scale {result.scale:g}:1)"
            )
            for notice in result.notices:
                print(f"Notice: {notice}", file=sys.stderr)
        return 0
    except (ValueError, OSError, KeyError, csv.Error) as exc:
        print(f"plateplot: {exc}", file=sys.stderr)
        return 2
