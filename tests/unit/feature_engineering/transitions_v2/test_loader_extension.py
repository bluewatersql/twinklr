"""Tests for FEArtifactBundle loader extension (transition_model_v2_path field)."""

from __future__ import annotations

from twinklr.core.feature_engineering.loader import FEArtifactBundle


def test_fe_artifact_bundle_has_transition_model_v2_path_field() -> None:
    """FEArtifactBundle has transition_model_v2_path field defaulting to None."""
    bundle = FEArtifactBundle()
    assert hasattr(bundle, "transition_model_v2_path")
    assert bundle.transition_model_v2_path is None


def test_fe_artifact_bundle_transition_model_v2_path_accepts_string() -> None:
    """FEArtifactBundle accepts a string value for transition_model_v2_path."""
    bundle = FEArtifactBundle(transition_model_v2_path="/some/path/model.json")
    assert bundle.transition_model_v2_path == "/some/path/model.json"
