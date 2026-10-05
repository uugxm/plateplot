# Changelog

## 0.1.0a4 - 2026-10-05

- Move row/column coordinates inside the plate by default and enlarge them from 7 to 12 pt.
- Add independent coordinate font size/position options and check available margin space.

## 0.1.0a3 - 2026-10-05

- Make Nunc 167008 the default 96-well cell culture plate for Python and CLI drawing.
- Resolve 96 / cell-culture-96 to Nunc; preserve explicit generic-96 and other plate sizes.
- Add a reproducible blank plate diagram with A1–H12 well addresses.

## 0.1.0a2 - 2026-10-05

- Add Nunc 167008 / 161093 templates from supplied drawing 2817 version 10.
- Preserve the asymmetric grid datum: H-row bottom margin 11.3 mm gives A1 top margin 11.18 mm.
- Store distinct opening, bottom and outer well diameters, plate height and well depth.
- Add document SHA-256/drawing provenance and explicit simplified-outline notices.
- Add manufacturer-specific vector examples and geometry regression coverage.

## 0.1.0a1 - 2026-10-05

- Add illustrative 12/24/48/96/384 plate templates and validated custom JSON geometry.
- Add per-well CSV/Python data with sample names, concentrations, colors, and custom labels.
- Add vector SVG/PDF output, physical 1:1 scale, dimensions, group legends, and vector colorbars.
- Add measured text wrapping, fitting, overflow errors, and font glyph validation.
- Add CLI, synthetic examples, regression tests, and Python 3.10/3.12 CI.
