"""Reported-usage pricing contracts for the one-request image exposure."""

from __future__ import annotations

import pytest

from twinklr.core.agents.assets.models import ImageGenerationUsage
from twinklr.core.agents.assets.pricing import calculate_image_cost


def test_complete_gpt_image_2_usage_gets_dated_model_specific_cost() -> None:
    usage = ImageGenerationUsage(
        input_tokens=110,
        input_text_tokens=100,
        input_image_tokens=10,
        output_tokens=200,
        output_image_tokens=200,
        output_text_tokens=0,
        total_tokens=310,
    )

    cost = calculate_image_cost(usage, model="gpt-image-2")

    assert cost is not None
    assert cost.pricing_as_of == "2026-08-26"
    assert cost.model_snapshot == "gpt-image-2-2026-04-21"
    assert cost.actual_image_usd == pytest.approx(0.00658)


@pytest.mark.parametrize(
    "usage",
    [
        ImageGenerationUsage(input_tokens=10, output_tokens=20, total_tokens=30),
        ImageGenerationUsage(
            input_tokens=10,
            input_text_tokens=10,
            input_image_tokens=0,
            output_tokens=20,
            output_text_tokens=0,
            output_image_tokens=19,
            total_tokens=30,
        ),
        ImageGenerationUsage(
            input_tokens=10,
            input_text_tokens=10,
            input_image_tokens=0,
            output_tokens=20,
            output_text_tokens=1,
            output_image_tokens=19,
            total_tokens=30,
        ),
    ],
)
def test_partial_or_inconsistent_usage_has_no_actual_cost(
    usage: ImageGenerationUsage,
) -> None:
    assert calculate_image_cost(usage, model="gpt-image-2") is None


def test_unpriced_model_has_no_actual_cost() -> None:
    usage = ImageGenerationUsage(
        input_tokens=10,
        input_text_tokens=10,
        input_image_tokens=0,
        output_tokens=20,
        output_text_tokens=0,
        output_image_tokens=20,
        total_tokens=30,
    )
    assert calculate_image_cost(usage, model="future-image-model") is None
