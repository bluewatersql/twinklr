"""Tests for pipeline stage utilities — resolve_typed_input.

P2.3: Standardize stage input/output contracts.
"""

from __future__ import annotations

from pydantic import BaseModel
import pytest


class _FakeModel(BaseModel):
    """Minimal model for testing resolve_typed_input."""

    value: str = "hello"


class TestResolveTypedInput:
    """Tests for the resolve_typed_input utility."""

    def test_returns_model_when_input_is_model(self) -> None:
        """If input is already the expected type, return it directly."""
        from twinklr.core.pipeline.stage import resolve_typed_input

        model = _FakeModel(value="direct")
        result, extras = resolve_typed_input(model, _FakeModel, "key")
        assert result is model
        assert extras == {}

    def test_extracts_model_from_dict(self) -> None:
        """If input is a dict, extract the model via dict_key."""
        from twinklr.core.pipeline.stage import resolve_typed_input

        model = _FakeModel(value="from-dict")
        data: dict = {"key": model, "other": 42}
        result, extras = resolve_typed_input(data, _FakeModel, "key")
        assert result is model
        assert extras == {"other": 42}

    def test_extras_excludes_extracted_key(self) -> None:
        """Extras dict should not include the extracted key."""
        from twinklr.core.pipeline.stage import resolve_typed_input

        model = _FakeModel()
        data: dict = {"primary": model, "a": 1, "b": 2}
        _, extras = resolve_typed_input(data, _FakeModel, "primary")
        assert "primary" not in extras
        assert extras == {"a": 1, "b": 2}

    def test_raises_type_error_for_missing_dict_key(self) -> None:
        """If dict doesn't have the expected key, raise TypeError."""
        from twinklr.core.pipeline.stage import resolve_typed_input

        data: dict = {"wrong_key": _FakeModel()}
        with pytest.raises(TypeError, match="missing key 'expected'"):
            resolve_typed_input(data, _FakeModel, "expected")

    def test_raises_type_error_for_none_value_in_dict(self) -> None:
        """If dict has the key but value is None, raise TypeError."""
        from twinklr.core.pipeline.stage import resolve_typed_input

        data: dict = {"key": None}
        with pytest.raises(TypeError, match="missing key 'key'"):
            resolve_typed_input(data, _FakeModel, "key")

    def test_raises_type_error_for_unexpected_type(self) -> None:
        """If input is neither model nor dict, raise TypeError."""
        from twinklr.core.pipeline.stage import resolve_typed_input

        with pytest.raises(TypeError, match="Expected _FakeModel"):
            resolve_typed_input("not-a-model", _FakeModel, "key")

    def test_raises_type_error_for_int_input(self) -> None:
        """Numeric input should raise TypeError."""
        from twinklr.core.pipeline.stage import resolve_typed_input

        with pytest.raises(TypeError, match="got int"):
            resolve_typed_input(42, _FakeModel, "key")

    def test_dict_key_none_with_dict_input_raises(self) -> None:
        """If dict_key is None and input is dict, raise TypeError."""
        from twinklr.core.pipeline.stage import resolve_typed_input

        with pytest.raises(TypeError, match="Expected _FakeModel"):
            resolve_typed_input({"k": 1}, _FakeModel, None)

    def test_subclass_of_model_is_accepted(self) -> None:
        """A subclass of the expected type should be accepted directly."""
        from twinklr.core.pipeline.stage import resolve_typed_input

        class _SubModel(_FakeModel):
            extra: int = 10

        sub = _SubModel(value="sub")
        result, extras = resolve_typed_input(sub, _FakeModel, "key")
        assert result is sub
        assert extras == {}


class TestStageDefinitionTypeAnnotations:
    """Tests for input_type/output_type metadata on StageDefinition."""

    def test_input_output_type_default_to_none(self) -> None:
        """By default, input_type and output_type should be None."""
        from twinklr.core.pipeline.definition import StageDefinition

        stage_def = StageDefinition(id="test", stage=object())
        assert stage_def.input_type is None
        assert stage_def.output_type is None

    def test_input_output_type_stored(self) -> None:
        """input_type and output_type should be stored when provided."""
        from twinklr.core.pipeline.definition import StageDefinition

        stage_def = StageDefinition(
            id="test",
            stage=object(),
            input_type="str",
            output_type="SongBundle",
        )
        assert stage_def.input_type == "str"
        assert stage_def.output_type == "SongBundle"

    def test_pipeline_definition_accepts_type_annotations(self) -> None:
        """Pipeline definition should accept stages with type annotations."""
        from twinklr.core.pipeline.definition import PipelineDefinition, StageDefinition

        stages = [
            StageDefinition(
                id="audio",
                stage=object(),
                input_type="str",
                output_type="SongBundle",
            ),
            StageDefinition(
                id="profile",
                stage=object(),
                inputs=["audio"],
                input_type="SongBundle",
                output_type="AudioProfileModel",
            ),
        ]
        pipeline = PipelineDefinition(name="test", stages=stages)
        assert pipeline.stages[0].input_type == "str"
        assert pipeline.stages[1].output_type == "AudioProfileModel"
