"""Tests for prompt renderer."""

import pytest

from twinklr.core.agents.prompts.renderer import PromptRenderer, RenderError


def test_render_simple_template():
    """Test rendering simple template."""
    renderer = PromptRenderer()

    template = "Hello {{ name }}!"
    variables = {"name": "World"}

    result = renderer.render(template, variables)

    assert result == "Hello World!"


def test_render_with_multiple_variables():
    """Test rendering with multiple variables."""
    renderer = PromptRenderer()

    template = "Agent: {{ agent_name }}, Iteration: {{ iteration }}"
    variables = {"agent_name": "planner", "iteration": 5}

    result = renderer.render(template, variables)

    assert result == "Agent: planner, Iteration: 5"


def test_render_with_missing_variable():
    """Test that missing variables raise error in strict mode."""
    renderer = PromptRenderer()

    template = "Hello {{ name }}!"
    variables = {}  # Missing 'name'

    with pytest.raises(RenderError) as exc_info:
        renderer.render(template, variables)

    assert "undefined" in str(exc_info.value).lower() or "name" in str(exc_info.value)


def test_render_with_conditional():
    """Test rendering with conditional."""
    renderer = PromptRenderer()

    template = "{% if feedback %}Feedback: {{ feedback }}{% else %}No feedback{% endif %}"

    # With feedback
    result1 = renderer.render(template, {"feedback": "Test feedback"})
    assert result1 == "Feedback: Test feedback"

    # Without feedback
    result2 = renderer.render(template, {"feedback": None})
    assert result2 == "No feedback"


def test_render_with_loop():
    """Test rendering with loop."""
    renderer = PromptRenderer()

    template = """Items:
{% for item in items %}
- {{ item }}
{% endfor %}"""

    variables = {"items": ["one", "two", "three"]}

    result = renderer.render(template, variables)

    assert "- one" in result
    assert "- two" in result
    assert "- three" in result


def test_render_with_filter():
    """Test rendering with Jinja2 filter."""
    renderer = PromptRenderer()

    template = "Count: {{ items|length }}"
    variables = {"items": [1, 2, 3, 4, 5]}

    result = renderer.render(template, variables)

    assert result == "Count: 5"


def test_render_empty_template():
    """Test rendering empty template."""
    renderer = PromptRenderer()

    result = renderer.render("", {})

    assert result == ""


def test_render_no_variables():
    """Test rendering template without variables."""
    renderer = PromptRenderer()

    template = "Static text only"

    result = renderer.render(template, {})

    assert result == "Static text only"


def test_render_with_whitespace_control():
    """Test rendering with whitespace control."""
    renderer = PromptRenderer()

    template = """Line 1
{%- if True %}
Line 2
{%- endif %}
Line 3"""

    result = renderer.render(template, {})

    # Whitespace control should work
    assert "Line 1" in result
    assert "Line 2" in result
    assert "Line 3" in result


def test_render_with_nested_data():
    """Test rendering with nested data structure."""
    renderer = PromptRenderer()

    template = "Tempo: {{ context.timing.tempo_bpm }} BPM"
    variables = {"context": {"timing": {"tempo_bpm": 128}}}

    result = renderer.render(template, variables)

    assert result == "Tempo: 128 BPM"


def test_render_error_wrapping():
    """Test that Jinja2 errors are wrapped in RenderError."""
    renderer = PromptRenderer()

    # Invalid template syntax
    template = "{{ unclosed"

    with pytest.raises(RenderError):
        renderer.render(template, {})
