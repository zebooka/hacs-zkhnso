"""HTML parser utility for converting HTML responses to JSON using CSS selectors.

Example usage:

    # Simple extraction
    value = html_to_json_simple(html, "div.title", "text")
    
    # Complex nested extraction
    config = {
        "selector": "table.meters",
        "multiple": True,
        "children": {
            "id": {"selector": "td.id", "attribute": "text"},
            "value": {"selector": "td.value", "attribute": "text"},
            "unit": {"selector": "td.unit", "attribute": "text"}
        }
    }
    meters = html_to_json(html, config)
"""
from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


def html_to_json(
    html_content: str,
    selector_config: dict[str, Any],
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Convert HTML content to JSON using CSS selectors.

    Args:
        html_content: The HTML content to parse
        selector_config: Configuration dict with CSS selectors and extraction rules.
                        Format:
                        {
                            "selector": "css.selector",
                            "attribute": "attr_name" (optional, defaults to text),
                            "multiple": True/False (optional, defaults to False),
                            "children": {...} (optional, for nested structures)
                        }

    Returns:
        Dictionary, list of dictionaries, or None if no matches found
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        return _extract_data(soup, selector_config)
    except Exception as e:
        _LOGGER.error("Error parsing HTML: %s", e)
        return None


def _extract_data(
    element: BeautifulSoup | Any,
    config: dict[str, Any],
) -> dict[str, Any] | list[dict[str, Any]] | str | None:
    """Recursively extract data from HTML element based on config."""
    selector = config.get("selector")
    if not selector:
        return None

    attribute = config.get("attribute", "text")
    multiple = config.get("multiple", False)
    children = config.get("children")

    try:
        if multiple:
            elements = element.select(selector)
            if not elements:
                return []

            if children:
                # Multiple elements with nested structure
                return [
                    _extract_children(elem, children) for elem in elements if elem
                ]
            else:
                # Multiple simple elements
                return [
                    _get_attribute_value(elem, attribute) for elem in elements if elem
                ]
        else:
            elem = element.select_one(selector)
            if not elem:
                return None

            if children:
                # Single element with nested structure
                return _extract_children(elem, children)
            else:
                # Single simple element
                return _get_attribute_value(elem, attribute)
    except Exception as e:
        _LOGGER.error("Error extracting data with selector '%s': %s", selector, e)
        return None


def _extract_children(
    element: Any,
    children_config: dict[str, Any],
) -> dict[str, Any]:
    """Extract nested data from element based on children config."""
    result = {}

    for key, child_config in children_config.items():
        if isinstance(child_config, dict):
            result[key] = _extract_data(element, child_config)
        else:
            # Simple string selector
            result[key] = _extract_data(element, {"selector": child_config})

    return result


def _get_attribute_value(element: Any, attribute: str) -> str | None:
    """Get attribute value from element."""
    if attribute == "text":
        return element.get_text(strip=True)
    elif attribute == "html":
        return str(element)
    else:
        return element.get(attribute)


def html_to_json_simple(
    html_content: str,
    selector: str,
    attribute: str = "text",
    multiple: bool = False,
) -> str | list[str] | None:
    """Simple wrapper for extracting single selector values.

    Args:
        html_content: The HTML content to parse
        selector: CSS selector string
        attribute: Attribute to extract (default: "text")
        multiple: Whether to extract multiple matches (default: False)

    Returns:
        String, list of strings, or None
    """
    config = {
        "selector": selector,
        "attribute": attribute,
        "multiple": multiple,
    }
    result = html_to_json(html_content, config)
    return result if result is not None else ([] if multiple else None)


def extract_table_rows_with_children(
    html_content: str, selector: str
) -> list[list[str]] | None:
    """Extract table rows and their children (td elements) as text.

    Args:
        html_content: The HTML content to parse
        selector: CSS selector for table rows (e.g., "#countersForm table tr")

    Returns:
        List of rows, where each row is a list of cell text values, or None on error
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        rows = soup.select(selector)
        if not rows:
            return None

        _LOGGER.debug("Soup rows: %s", rows)

        result = []
        for row in rows:
            cells = row.find_all(["td", "th"])
            row_data = [_extract_cell_text(cell) for cell in cells]
            _LOGGER.debug("Row data: %s", row_data)
            result.append(row_data)

        return result
    except Exception as e:
        _LOGGER.error("Error extracting table rows: %s", e)
        return None


def _extract_cell_text(cell) -> str:
    """Extract text from table cell ignoring nested element contents."""
    if cell is None:
        return ""

    direct_text_parts: list[str] = []
    for content in cell.contents:
        if isinstance(content, str):
            text = content.strip()
            if text:
                direct_text_parts.append(text)

    if direct_text_parts:
        return " ".join(direct_text_parts)

    return cell.get_text(strip=True)

