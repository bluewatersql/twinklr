"""Utility for generating JSON schemas from Pydantic models.

Ensures agent prompts always use the current schema definition,
avoiding synchronization bugs between hardcoded schemas and models.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import hashlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel


STRICT_SCHEMA_PROPERTY_LIMIT = 5_000
STRICT_SCHEMA_MAX_DEPTH = 10
STRICT_SCHEMA_ENUM_LIMIT = 1_000
STRICT_SCHEMA_UNSUPPORTED_KEYWORDS = frozenset(
    {
        "allOf",
        "dependentRequired",
        "dependentSchemas",
        "discriminator",
        "else",
        "if",
        "not",
        "oneOf",
        "then",
    }
)
STRICT_SCHEMA_REF_ANNOTATION_KEYWORDS = frozenset(
    {
        "$comment",
        "default",
        "deprecated",
        "description",
        "examples",
        "readOnly",
        "title",
        "writeOnly",
    }
)


@dataclass(frozen=True)
class StrictSchemaStats:
    """OpenAI Structured Outputs complexity counters."""

    property_count: int
    max_depth: int
    enum_value_count: int


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

    schema = _normalize_supported_schema(schema)

    return json.dumps(schema, indent=indent)


def response_schema_hash(model: type[BaseModel]) -> str:
    """Return a deterministic identity for a Pydantic response contract.

    The same machine-derived schema is sent to the provider and included in
    stage cache identity.  A model-only contract change therefore cannot reuse
    a plan generated against the previous schema.
    """
    canonical = json.dumps(
        strict_json_schema(model),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def strict_response_format(model: type[BaseModel]) -> dict[str, Any]:
    """Build the Responses API strict format directly from a Pydantic model."""
    return {
        "type": "json_schema",
        "name": model.__name__[:64],
        "schema": strict_json_schema(model),
        "strict": True,
    }


def chat_completions_response_format(model: type[BaseModel]) -> dict[str, Any]:
    """Build the Chat Completions strict format from the same Pydantic schema.

    Chat Completions nests the schema descriptor under ``json_schema`` while
    Responses accepts that descriptor directly as ``text.format``.
    """
    response_format = strict_response_format(model)
    return {
        "type": "json_schema",
        "json_schema": {key: response_format[key] for key in ("name", "schema", "strict")},
    }


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Derive and validate the OpenAI-supported subset of a Pydantic schema.

    Pydantic discriminated unions emit JSON Schema ``oneOf`` plus
    ``discriminator`` metadata.  OpenAI Structured Outputs supports nested
    ``anyOf`` branches, but not those two keywords.  Rewriting ``oneOf`` to
    ``anyOf`` preserves the branch constraints while Pydantic remains the
    client-side semantic validator after generation.
    """
    schema: dict[str, Any] = _normalize_supported_schema(model.model_json_schema())
    _validate_strict_schema(schema)
    return schema


def strict_schema_stats(schema: dict[str, Any]) -> StrictSchemaStats:
    """Measure provider-documented property, depth, and enum ceilings."""
    nodes = list(_iter_schema_nodes(schema))
    return StrictSchemaStats(
        property_count=sum(len(node.get("properties", {})) for node in nodes),
        max_depth=_schema_max_depth(schema),
        enum_value_count=sum(len(node.get("enum", ())) for node in nodes),
    )


def _normalize_supported_schema(value: Any, _path: tuple[str, ...] = ()) -> Any:
    """Recursively normalize Pydantic output without hand-editing model schemas."""
    if isinstance(value, list):
        return [
            _normalize_supported_schema(item, (*_path, str(index)))
            for index, item in enumerate(value)
        ]
    if not isinstance(value, dict):
        return value

    if "oneOf" in value and "anyOf" in value:
        raise ValueError("JSON Schema node cannot contain both oneOf and anyOf")

    if "$ref" in value:
        siblings = set(value) - {"$ref"}
        semantic_siblings = siblings - STRICT_SCHEMA_REF_ANNOTATION_KEYWORDS
        if semantic_siblings:
            location = "/".join(_path) or "<root>"
            raise ValueError(
                f"JSON Schema $ref at {location} has semantic sibling keywords: "
                + ", ".join(sorted(semantic_siblings))
            )
        # OpenAI requires reference nodes to contain no sibling keywords.  Pydantic
        # commonly attaches field annotations such as ``description`` to a ref;
        # dropping those annotations does not alter validation semantics.
        return {"$ref": value["$ref"]}

    normalized: dict[str, Any] = {}
    for key, child in value.items():
        if key == "discriminator":
            continue
        normalized_key = "anyOf" if key == "oneOf" else key
        normalized[normalized_key] = _normalize_supported_schema(child, (*_path, normalized_key))
    return normalized


def _iter_schema_nodes(schema: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield schema nodes while skipping property/definition name maps."""
    yield schema
    for mapping_key in ("properties", "$defs", "definitions", "patternProperties"):
        mapping = schema.get(mapping_key)
        if isinstance(mapping, dict):
            for child in mapping.values():
                if isinstance(child, dict):
                    yield from _iter_schema_nodes(child)
    items = schema.get("items")
    if isinstance(items, dict):
        yield from _iter_schema_nodes(items)
    for sequence_key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        sequence = schema.get(sequence_key)
        if isinstance(sequence, list):
            for child in sequence:
                if isinstance(child, dict):
                    yield from _iter_schema_nodes(child)
    for child_key in ("not", "if", "then", "else"):
        child = schema.get(child_key)
        if isinstance(child, dict):
            yield from _iter_schema_nodes(child)


def _schema_max_depth(schema: dict[str, Any]) -> int:
    """Count object and array containers along dereferenced instance paths."""
    definitions = schema.get("$defs", {})

    def walk(node: dict[str, Any], depth: int, seen_refs: frozenset[str]) -> int:
        ref = node.get("$ref")
        if isinstance(ref, str):
            if ref == "#" or ref in seen_refs:
                return depth
            prefix = "#/$defs/"
            if ref.startswith(prefix):
                target = definitions.get(ref.removeprefix(prefix))
                if isinstance(target, dict):
                    return walk(target, depth, seen_refs | {ref})
            return depth

        if node.get("type") in ("object", "array") or "properties" in node:
            depth += 1
        maximum = depth
        properties = node.get("properties", {})
        if isinstance(properties, dict):
            for child in properties.values():
                if isinstance(child, dict):
                    maximum = max(maximum, walk(child, depth, seen_refs))
        items = node.get("items")
        if isinstance(items, dict):
            maximum = max(maximum, walk(items, depth, seen_refs))
        for sequence_key in ("anyOf", "oneOf"):
            sequence = node.get(sequence_key, ())
            if isinstance(sequence, list):
                for child in sequence:
                    if isinstance(child, dict):
                        maximum = max(maximum, walk(child, depth, seen_refs))
        return maximum

    return walk(schema, 0, frozenset())


def _validate_strict_schema(schema: dict[str, Any]) -> None:
    """Fail before an API call when a derived schema exceeds the supported subset."""
    if schema.get("type") != "object" or "anyOf" in schema:
        raise ValueError("Structured Outputs response root must be an object, not anyOf")

    for node in _iter_schema_nodes(schema):
        if "$ref" in node and set(node) != {"$ref"}:
            raise ValueError("Every Structured Outputs $ref node must have no sibling keywords")
        unsupported = STRICT_SCHEMA_UNSUPPORTED_KEYWORDS.intersection(node)
        if unsupported:
            raise ValueError(
                "Unsupported Structured Outputs JSON Schema keywords: "
                + ", ".join(sorted(unsupported))
            )
        if node.get("type") == "object" or "properties" in node:
            properties = node.get("properties", {})
            if node.get("additionalProperties") is not False:
                raise ValueError("Every Structured Outputs object must forbid extra properties")
            if set(node.get("required", ())) != set(properties):
                raise ValueError("Every Structured Outputs object property must be required")

    stats = strict_schema_stats(schema)
    if stats.property_count > STRICT_SCHEMA_PROPERTY_LIMIT:
        raise ValueError(
            f"Structured Outputs schema has {stats.property_count} properties; "
            f"limit is {STRICT_SCHEMA_PROPERTY_LIMIT}"
        )
    if stats.max_depth > STRICT_SCHEMA_MAX_DEPTH:
        raise ValueError(
            f"Structured Outputs schema depth is {stats.max_depth}; "
            f"limit is {STRICT_SCHEMA_MAX_DEPTH}"
        )
    if stats.enum_value_count > STRICT_SCHEMA_ENUM_LIMIT:
        raise ValueError(
            f"Structured Outputs schema has {stats.enum_value_count} enum values; "
            f"limit is {STRICT_SCHEMA_ENUM_LIMIT}"
        )


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
