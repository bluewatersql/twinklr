"""Auditable GPT Image pricing from complete provider-reported usage only."""

from __future__ import annotations

from decimal import Decimal

from twinklr.core.agents.assets.models import ImageGenerationCost, ImageGenerationUsage
from twinklr.core.config.models import DEFAULT_IMAGE_MODEL

_PRICING_AS_OF = "2026-08-26"
_MODEL_SNAPSHOT = f"{DEFAULT_IMAGE_MODEL}-2026-04-21"
_SUPPORTED_MODELS = {DEFAULT_IMAGE_MODEL, _MODEL_SNAPSHOT}
_TEXT_INPUT_USD_PER_MILLION = Decimal("5.00")
_IMAGE_INPUT_USD_PER_MILLION = Decimal("8.00")
_IMAGE_OUTPUT_USD_PER_MILLION = Decimal("30.00")
_ONE_MILLION = Decimal(1_000_000)


def calculate_image_cost(
    usage: ImageGenerationUsage,
    *,
    model: str,
) -> ImageGenerationCost | None:
    """Price complete consistent usage; return unavailable for every uncertain case."""
    if model not in _SUPPORTED_MODELS:
        return None
    input_tokens = usage.input_tokens
    input_text_tokens = usage.input_text_tokens
    input_image_tokens = usage.input_image_tokens
    output_tokens = usage.output_tokens
    output_text_tokens = usage.output_text_tokens
    output_image_tokens = usage.output_image_tokens
    total_tokens = usage.total_tokens
    if (
        input_tokens is None
        or input_text_tokens is None
        or input_image_tokens is None
        or output_tokens is None
        or output_text_tokens is None
        or output_image_tokens is None
        or total_tokens is None
    ):
        return None
    if (
        input_tokens != input_text_tokens + input_image_tokens
        or output_tokens != output_text_tokens + output_image_tokens
        or total_tokens != input_tokens + output_tokens
        or output_text_tokens != 0
    ):
        return None
    actual = (
        Decimal(input_text_tokens) * _TEXT_INPUT_USD_PER_MILLION
        + Decimal(input_image_tokens) * _IMAGE_INPUT_USD_PER_MILLION
        + Decimal(output_image_tokens) * _IMAGE_OUTPUT_USD_PER_MILLION
    ) / _ONE_MILLION
    return ImageGenerationCost(
        pricing_as_of=_PRICING_AS_OF,
        model_snapshot=_MODEL_SNAPSHOT,
        text_input_usd_per_million=float(_TEXT_INPUT_USD_PER_MILLION),
        image_input_usd_per_million=float(_IMAGE_INPUT_USD_PER_MILLION),
        image_output_usd_per_million=float(_IMAGE_OUTPUT_USD_PER_MILLION),
        actual_image_usd=float(actual),
    )
