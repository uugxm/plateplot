import csv
import subprocess
import sys

from plateplot.cli import main


def test_cli_templates_and_blank_csv(tmp_path, capsys):
    assert main(["templates"]) == 0
    assert "generic-384" in capsys.readouterr().out
    path = tmp_path / "blank.csv"
    assert main(["blank-csv", "96", str(path)]) == 0
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 96
    assert rows[-1]["well"] == "H12"


def test_cli_export_and_draw(tmp_path):
    template = tmp_path / "template.json"
    output = tmp_path / "plate.svg"
    assert main(["export-template", "12", str(template)]) == 0
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "plateplot",
            "draw",
            "--template",
            str(template),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert output.is_file()
    assert "Illustrative" in result.stderr


def test_cli_error_is_concise(tmp_path, capsys):
    assert main(["draw", "--template", "96", "--output", str(tmp_path / "plate.png")]) == 2
    message = capsys.readouterr().err
    assert "Output must end in .svg or .pdf" in message
    assert "Traceback" not in message


def test_cli_default_is_nunc_cell_culture_plate(tmp_path, capsys):
    output = tmp_path / "default.svg"
    assert main(["draw", "--output", str(output), "--labels", "well"]) == 0
    assert "Nunc 167008" in output.read_text()
    assert "Outline simplified" in capsys.readouterr().err
    assert main(["draw", "--template", "generic-96", "--output", str(output)]) == 0
    assert "Illustrative" in capsys.readouterr().err


def test_cli_metadata_is_opt_in(tmp_path):
    from pypdf import PdfReader

    path = tmp_path / "plate.pdf"
    assert main(["draw", "--output", str(path)]) == 0
    assert "Nunc 167008" not in PdfReader(path).pages[0].extract_text()
    assert main(["draw", "--output", str(path), "--show-title", "--show-parameters"]) == 0
    text = PdfReader(path).pages[0].extract_text()
    assert "Nunc 167008" in text
    assert "6.97" in text
