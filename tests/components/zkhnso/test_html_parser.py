"""Tests for the HTML parsing helpers."""
from custom_components.zkhnso.html_parser import (
    extract_table_rows_with_children,
    html_to_json,
    html_to_json_simple,
)


HTML = """
<section><h1 data-id="42"> Title </h1><ul><li>A</li><li>B</li></ul>
<table id="data"><tr><th> Name </th><th> Value </th></tr>
<tr><td>Meter <span>ignored</span></td><td> 12 </td></tr></table></section>
"""


def test_simple_and_multiple_extraction() -> None:
    """Text and attributes are extracted from CSS selectors."""
    assert html_to_json_simple(HTML, "h1") == "Title"
    assert html_to_json_simple(HTML, "h1", attribute="data-id") == "42"
    assert html_to_json_simple(HTML, "li", multiple=True) == ["A", "B"]
    assert html_to_json_simple(HTML, ".missing") is None
    assert html_to_json_simple(HTML, ".missing", multiple=True) == []


def test_nested_and_table_extraction() -> None:
    """Nested configs and table cell extraction preserve expected text."""
    assert html_to_json(
        HTML,
        {"selector": "table", "children": {"name": "td", "value": {"selector": "td:nth-of-type(2)"}}},
    ) == {"name": "Meterignored", "value": "12"}
    assert extract_table_rows_with_children(HTML, "#data tr") == [
        ["Name", "Value"],
        ["Meter", "12"],
    ]
    assert extract_table_rows_with_children(HTML, ".missing") is None
