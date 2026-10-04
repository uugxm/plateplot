import pytest

from plateplot import WellData, load_csv, load_template
from plateplot.data import prepare_data


def test_bom_quoted_csv_and_custom_fields(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text(
        "\ufeffwell,sample_name,concentration,concentration_unit,note\n"
        'A01,"Sample, with comma",2.5,µM,"line 1\nline 2"\n',
        encoding="utf-8",
    )
    row = load_csv(path)[0]
    assert row.well == "A1"
    assert row.sample_name == "Sample, with comma"
    assert row.text("concentration") == "2.5 µM"
    assert row.text("note") == "line 1\nline 2"


@pytest.mark.parametrize(
    "text",
    [
        "sample_name\ntest\n",
        "well,well\nA1,A2\n",
        "well,name\nA1\n",
        "well\nA1,extra\n",
        "well,concentration\nA1,nan\n",
        "well,concentration\nA1,inf\n",
        "well,concentration\nA1,-2\n",
        "well,fill_color\nA1,invalid-color\n",
        "well, sample_name\nA1,sample\n",
    ],
)
def test_bad_csv(tmp_path, text):
    path = tmp_path / "input.csv"
    path.write_text(text)
    with pytest.raises(ValueError):
        load_csv(path)


def test_duplicate_normalized_wells():
    with pytest.raises(ValueError, match="Duplicate well A1"):
        prepare_data([{"well": "A01"}, {"well": "a1"}], load_template(96))


def test_out_of_range():
    with pytest.raises(ValueError, match="outside"):
        prepare_data([WellData("P24")], load_template(96))


def test_zero_blank_and_extra():
    assert WellData("A1", concentration=0).text("concentration") == "0"
    assert WellData.from_mapping({"well": "A1", "concentration": ""}).concentration is None
    with pytest.raises(ValueError, match="shadow"):
        WellData("A1", extra={"group": "bad"})
    with pytest.raises(ValueError, match="Unknown label"):
        WellData("A1").text("typo")
