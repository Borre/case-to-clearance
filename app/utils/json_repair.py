"""JSON repair utilities for fixing malformed LLM outputs."""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def repair_json(
    invalid_json: str,
    expected_keys: list[str] | None = None,
    strict: bool = False
) -> tuple[bool, dict[str, Any] | None, str]:
    """Attempt to repair malformed JSON.

    Args:
        invalid_json: The invalid JSON string
        expected_keys: Optional list of expected top-level keys
        strict: If True, fail unless all expected keys are present

    Returns:
        Tuple of (success, repaired_dict, error_message)
    """
    # Try parsing as-is first
    try:
        data = json.loads(invalid_json)
        return True, data, ""
    except json.JSONDecodeError:
        pass  # Continue to repair attempts

    # Attempt various repair strategies
    repair_functions = [
        _trim_extra_text,
        _fix_missing_quotes,
        _fix_trailing_commas,
        _fix_single_quotes,
        _fix_unescaped_quotes,
        _extract_json_block,
        _fix_bracket_mismatch,
    ]

    last_error = ""
    for repair_func in repair_functions:
        try:
            repaired = repair_func(invalid_json)
            data = json.loads(repaired)

            # Validate expected keys if provided
            if expected_keys:
                missing_keys = set(expected_keys) - set(data.keys())
                if missing_keys and strict:
                    continue  # Try next repair method
                elif missing_keys:
                    # Add missing keys with null values
                    for key in missing_keys:
                        data[key] = None

            return True, data, ""
        except (json.JSONDecodeError, ValueError) as e:
            last_error = str(e)
            continue

    # All repair attempts failed
    return False, None, f"Could not repair JSON: {last_error}"


def _trim_extra_text(text: str) -> str:
    """Trim extra text before or after JSON."""
    # Find first { or [
    start_idx = -1
    for char in ["{", "["]:
        idx = text.find(char)
        if idx != -1 and (start_idx == -1 or idx < start_idx):
            start_idx = idx

    if start_idx == -1:
        raise ValueError("No JSON start found")

    # Find matching closing bracket
    opening_char = text[start_idx]
    closing_char = "}" if opening_char == "{" else "]"

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start_idx, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == opening_char:
            depth += 1
        elif char == closing_char:
            depth -= 1
            if depth == 0:
                return text[start_idx:i + 1]

    raise ValueError("No matching closing bracket found")


def _fix_missing_quotes(text: str) -> str:
    """Fix missing quotes around property names."""
    # Pattern: property name without quotes followed by colon
    # e.g., {name: "value"} -> {"name": "value"}
    pattern = r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:'

    def add_quotes(match):
        return f'{match.group(1)} "{match.group(2)}":'

    return re.sub(pattern, add_quotes, text)


def _fix_trailing_commas(text: str) -> str:
    """Fix trailing commas in arrays/objects."""
    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _fix_single_quotes(text: str) -> str:
    """Replace single quotes with double quotes (cautiously)."""
    # Only replace if it looks like they're used for strings
    # This is a heuristic and may not always be correct
    result = text
    in_string = False
    escape_next = False
    quote_char = None

    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char in ["'", '"']:
            if not in_string:
                in_string = True
                quote_char = char
            elif char == quote_char:
                in_string = False
                quote_char = None

    # If we found single quotes used as string delimiters
    if "'" in text and '"' not in text[:text.find("'")]:
        # Replace single quotes with double quotes, except in strings with double quotes
        result = ""
        in_double = False
        in_single = False
        escape = False

        for char in text:
            if escape:
                result += char
                escape = False
                continue

            if char == "\\":
                escape = True
                result += char
                continue

            if char == '"' and not in_single:
                in_double = not in_double
                result += char
            elif char == "'" and not in_double:
                result += '"'
                in_single = not in_single
            else:
                result += char

        return result

    return text


def _fix_unescaped_quotes(text: str) -> str:
    """Fix unescaped quotes in strings."""
    # This is tricky - we need to identify quotes that should be escaped
    # A simple heuristic: quotes in the middle of a string value that aren't followed by comma/colon/bracket
    result = []
    i = 0

    while i < len(text):
        if text[i] == '"':
            # Check if this looks like a closing quote
            if i + 1 < len(text) and text[i + 1] in [',', '}', ']']:
                result.append('"')
            elif i + 1 < len(text) and text[i + 1] == ':' and i > 0 and text[i - 1] not in ['{', ',']:
                # This might be a property name (should have been handled)
                result.append('\\"')
            elif i > 0 and text[i - 1] in ['{', ',', ':', '[']:
                # This is likely an opening quote for a string value
                result.append('"')
            else:
                # Might be an unescaped quote in a string
                result.append('\\"')
        else:
            result.append(text[i])
        i += 1

    return "".join(result)


def _extract_json_block(text: str) -> str:
    """Extract JSON from markdown code blocks."""
    # Try to find JSON in markdown code blocks
    patterns = [
        r'```json\s*(.+?)\s*```',
        r'```\s*(.+?)\s*```',
        r'({.*})',  # Last resort: just find outermost braces
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0] if match else ""
            try:
                json.loads(match)
                return match
            except json.JSONDecodeError:
                continue

    return text


def _fix_bracket_mismatch(text: str) -> str:
    """Attempt to fix mismatched brackets."""
    # Count brackets
    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')

    result = text

    # Add missing closing brackets
    if open_braces > close_braces:
        result += '}' * (open_braces - close_braces)
    if open_brackets > close_brackets:
        result += ']' * (open_brackets - close_brackets)

    return result


def json_minify(data: dict[str, Any] | str) -> str:
    """Minify JSON (remove whitespace).

    Args:
        data: Dict to minify or JSON string

    Returns:
        Minified JSON string
    """
    if isinstance(data, str):
        data = json.loads(data)
    return json.dumps(data, separators=(',', ':'))


def json_pretty(data: dict[str, Any] | str, indent: int = 2) -> str:
    """Pretty print JSON.

    Args:
        data: Dict to prettify or JSON string
        indent: Indentation spaces

    Returns:
        Pretty JSON string
    """
    if isinstance(data, str):
        data = json.loads(data)
    return json.dumps(data, indent=indent, ensure_ascii=False)


def merge_json(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two JSON objects.

    Args:
        base: Base object
        update: Object to merge into base

    Returns:
        Merged object
    """
    result = base.copy()

    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_json(result[key], value)
        else:
            result[key] = value

    return result
