"""Reproduce estimates from supplied MD6 PDF vector contours (not production dimensions).

Optional dependencies: PyMuPDF, numpy, scipy. The manufacturer PDF stays outside the repo.
Usage: python scripts/measure_nunc_6.py /path/to/140675.pdf output.json
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pymupdf
from scipy.optimize import least_squares

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("pdf", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
expected = "8a70f2f4e02d784d419f559e77f72c17c05cce205a210bedee809e6a2124ff4e"
if hashlib.sha256(args.pdf.read_bytes()).hexdigest() != expected:
    raise SystemExit("This measurement recipe is restricted to the supplied MD6 PDF revision.")

with pymupdf.open(args.pdf) as document:
    page = document[1]
    segments = []
    for path in page.get_drawings():
        for item in path["items"]:
            if item[0] != "l":
                continue
            a, b = item[1] * page.rotation_matrix, item[2] * page.rotation_matrix
            if (
                465 < min(a.x, b.x)
                and max(a.x, b.x) < 662
                and 120 < min(a.y, b.y)
                and max(a.y, b.y) < 390
            ):
                segments.append((a.x, a.y, b.x, b.y))

lines = np.array(segments)
horizontal = lines[
    (np.abs(lines[:, 1] - lines[:, 3]) < 0.01) & (np.abs(lines[:, 0] - lines[:, 2]) > 70)
]
vertical = lines[
    (np.abs(lines[:, 0] - lines[:, 2]) < 0.01) & (np.abs(lines[:, 1] - lines[:, 3]) > 130)
]
left, right = float(vertical[:, 0].min()), float(vertical[:, 0].max())
top, bottom = float(horizontal[:, 1].min()), float(horizontal[:, 1].max())
sx, sy = (right - left) / 85.46, (bottom - top) / 127.76
points = np.concatenate([lines[:, :2], lines[:, 2:]])
circles = []
for cy in (175.5, 255.55, 335.7):
    for cx in (523.92, 604.02):
        distance = np.linalg.norm(points - [cx, cy], axis=1)
        selected = points[(distance > 34.1) & (distance < 34.7)]
        result = least_squares(
            lambda v, selected=selected: np.linalg.norm(selected - v[:2], axis=1) - v[2],
            [cx, cy, 34.45],
            loss="soft_l1",
            f_scale=0.02,
        )
        x, y, radius = result.x
        circles.append(
            {
                "center_pdf_pt": [float(x), float(y)],
                "landscape_center_mm": [float((y - top) / sy), float((right - x) / sx)],
                "visible_inner_diameter_mm": float(2 * radius / np.mean([sx, sy])),
                "selected_endpoints": len(selected),
                "residual_rms_pdf_pt": float(
                    np.sqrt(
                        np.mean((np.linalg.norm(selected - result.x[:2], axis=1) - radius) ** 2)
                    )
                ),
            }
        )

centers = np.array([c["landscape_center_mm"] for c in circles]).reshape(3, 2, 2)
estimate = {
    "well_diameter_mm": round(float(np.mean([c["visible_inner_diameter_mm"] for c in circles])), 1),
    "pitch_x_mm": round(float(np.diff(centers[:, :, 0], axis=0).mean()), 1),
    "pitch_y_mm": round(float(-np.diff(centers[:, :, 1], axis=1).mean()), 1),
    "a1_x_mm": round(float(centers[0, 1, 0]), 1),
    "a1_y_mm": round(float(centers[0, 1, 1]), 1),
}
report = {
    "source_sha256": expected,
    "page": 2,
    "method": (
        "Least-squares fit to innermost visible vector contour; selected fixed view and contour "
        "band, independently calibrated using dimensioned footprint. Landscape rotation "
        "puts A1 upper-left."
    ),
    "limitation": (
        "Estimates rounded to 0.1 mm; not manufacturer dimensions or manufacturing tolerances. "
        "The depicted inner contour cannot unambiguously establish top vs bottom internal diameter."
    ),
    "outline_pdf_pt": [left, top, right, bottom],
    "calibration_pdf_pt_per_mm": {"width_axis": sx, "length_axis": sy},
    "circles": circles,
    "rounded_template_values": estimate,
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(estimate))
