"""Utility for generating JSON schemas from Pydantic models.

Ensures agent prompts always use the current schema definition,
avoiding synchronization bugs between hardcoded schemas and models.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel


def get_json_schema_example(
    model: type[BaseModel],
    indent: int = 2,
    exclude_fields: list[str] | None = None,
    optional_fields: list[str] | None = None,
) -> str:
    """Generate a filtered JSON schema from a Pydantic model.

    This function returns the full JSON schema but allows filtering
    to match the agent's specific scope and responsibilities.

    Args:
        model: Pydantic model class
        indent: JSON indentation level
        exclude_fields: List of field names to exclude from schema (e.g., deprecated fields)
        optional_fields: List of field names to make optional (even if required in model)

    Returns:
        Formatted JSON schema string for use in prompts
    """
    # Get the full JSON schema from Pydantic
    schema = model.model_json_schema()

    # Apply filters if specified
    if exclude_fields or optional_fields:
        schema = _filter_schema(schema, exclude_fields or [], optional_fields or [])

    return json.dumps(schema, indent=indent)


def _filter_schema(schema: dict, exclude_fields: list[str], optional_fields: list[str]) -> dict:
    """Filter a JSON schema to match agent scope.

    Args:
        schema: JSON schema dict from Pydantic
        exclude_fields: Fields to remove completely
        optional_fields: Fields to make optional (remove from required list)

    Returns:
        Filtered schema dict
    """
    # Work on a copy
    schema = schema.copy()

    # Remove excluded fields from properties
    if "properties" in schema:
        properties = schema["properties"].copy()
        for field in exclude_fields:
            properties.pop(field, None)
        schema["properties"] = properties

    # Update required fields list
    if "required" in schema:
        required = [f for f in schema["required"] if f not in exclude_fields]
        required = [f for f in required if f not in optional_fields]
        schema["required"] = required

    # Also filter nested definitions if present
    if "$defs" in schema:
        defs = schema["$defs"].copy()
        for def_schema in defs.values():
            if "properties" in def_schema:
                properties = def_schema["properties"].copy()
                for field in exclude_fields:
                    properties.pop(field, None)
                def_schema["properties"] = properties

            if "required" in def_schema:
                required = [f for f in def_schema["required"] if f not in exclude_fields]
                required = [f for f in required if f not in optional_fields]
                def_schema["required"] = required

        schema["$defs"] = defs

    return schema
