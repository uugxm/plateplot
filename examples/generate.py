"""Reproduce synthetic example CSVs and diagrams; no laboratory records are used."""

import csv
from pathlib import Path

from plateplot import draw_plate, load_template

ROOT = Path(__file__).resolve().parent


def records(count):
    result = []
    template = load_template(count)
    for i, well in enumerate(template.wells()):
        group_index = (i % template.columns) * 3 // template.columns
        result.append(
            {
                "well": well,
                "sample_name": f"S{i + 1:03}",
                "group": ["Control", "Treatment A", "Treatment B"][group_index],
                "concentration": 0 if group_index == 0 else (i % 6 + 1) * 5,
                "concentration_unit": "µM",
                "fill_color": "",
            }
        )
    return result


def main():
    figures = ROOT / "figures"
    figures.mkdir(exist_ok=True)
    for count in [12, 24, 48, 96, 384]:
        rows = records(count)
        with (ROOT / f"samples-{count}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        draw_plate(
            count,
            rows,
            output=figures / f"plate-{count}.svg",
            label_fields=["sample_name"] if count == 384 else ["sample_name", "concentration"],
            font_size={12: 22, 24: 18, 48: 12, 96: 9, 384: 9}[count],
        )
    draw_plate(96, records(96), output=figures / "plate-96.pdf")
    draw_plate(96, output=figures / "plate-96-physical.svg", mode="physical", show_dimensions=True)
    draw_plate(
        96, records(96), output=figures / "plate-96-concentration.svg", color_by="concentration"
    )
    for catalog in ("167008", "161093"):
        template = f"nunc-{catalog}"
        draw_plate(template, records(96), output=figures / f"{template}.svg")
        draw_plate(
            template,
            output=figures / f"{template}-physical.svg",
            mode="physical",
            show_dimensions=True,
        )
    draw_plate("nunc-167008", records(96), output=figures / "nunc-167008.pdf")
    draw_plate(
        output=figures / "96-cell-culture-blank.svg",
        label_fields=["well"],
        color_by="none",
        show_legend=False,
        title="96-well cell culture plate - Nunc 167008 / 161093",
    )
    print(f"Synthetic examples generated in {figures}")


if __name__ == "__main__":
    main()
