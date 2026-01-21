"""Unit tests for ContextShaper."""

import pytest

from blinkb0t.core.agents.moving_heads import (
    ContextShaper,
    ShapedContext,
    Stage,
    TokenEstimator,
)
from blinkb0t.core.config.models import JobConfig


class TestTokenEstimator:
    """Test TokenEstimator class."""

    def test_estimate_small_data(self) -> None:
        """Test token estimation for small data."""
        estimator = TokenEstimator()

        data = {"key": "value"}
        token_estimate = estimator.estimate(data)

        # Should be non-zero
        assert token_estimate > 0

        # Rough check (17 chars ≈ 5 tokens with overhead)
        assert 3 < token_estimate < 10

    def test_estimate_large_data(self) -> None:
        """Test token estimation for larger data."""
        estimator = TokenEstimator()

        data = {"key": "value" * 100}
        token_estimate = estimator.estimate(data)

        # Should be non-zero
        assert token_estimate > 0

        # Rough check (507 chars ≈ 152 tokens with overhead)
        assert 100 < token_estimate < 200


class TestContextShaper:
    """Test ContextShaper class."""

    @pytest.fixture
    def shaper(self) -> ContextShaper:
        """Create ContextShaper instance."""
        return ContextShaper(job_config=JobConfig())

    @pytest.fixture
    def mock_song_features(self) -> dict:
        """Create mock song features."""
        return {
            "duration_s": 180.0,
            "tempo_bpm": 120.0,
            "time_signature": {"time_signature": "4/4"},
            "bars_s": [i * 2.0 for i in range(90)],  # 90 bars
            "beats_s": [i * 0.5 for i in range(360)],  # 360 beats
            "energy": {
                "times_s": [i * 0.1 for i in range(1800)],
                "phrase_level": [0.5 + (i % 10) * 0.05 for i in range(1800)],
                "peaks": [{"t_s": 50.0, "val": 0.9}],
                "stats": {"min": 0.2, "max": 0.95, "mean": 0.6},
            },
            "assumptions": {"beats_per_bar": 4},
        }

    @pytest.fixture
    def mock_template_metadata(self) -> list[dict]:
        """Create mock template metadata."""
        return [
            {
                "template_id": "gentle_sweep_breathe",
                "name": "Gentle Sweep with Breathing Dimmer",
                "category": "low_energy",
                "metadata": {
                    "description": "Gentle movement",
                    "energy_range": [10, 40],
                    "recommended_sections": ["verse", "ambient"],
                    "tags": ["gentle", "sweep", "breathe"],
                },
                "step_count": 2,
                "steps": [
                    {
                        "step_id": "step1",
                        "movement_id": "sweep_lr",
                        "geometry_id": "fan",
                        "dimmer_id": "breathe",
                    },
                    {
                        "step_id": "step2",
                        "movement_id": "circle",
                        "geometry_id": None,
                        "dimmer_id": "hold",
                    },
                ],
                "timing": {
                    "mode": "MUSICAL",
                    "default_duration_bars": 8.0,
                },
            }
        ]

    @pytest.fixture
    def mock_seq_fingerprint(self) -> dict:
        """Create mock sequence fingerprint."""
        return {
            "existing_effects": {
                "total_count": 10,
                "by_type": {"rgb": 5, "matrix": 5},
                "coverage_pct": 80,
            },
            "color_palette": ["#FF0000", "#00FF00", "#0000FF"],
            "timing_density": {"low": 20, "medium": 50, "high": 30},
            "effect_coverage": {"pan_tilt_pct": 0, "dimmer_pct": 0},
            "timing_track_events": {
                "beat_track": [{"t_ms": 100}, {"t_ms": 600}],
                "phrase_track": [{"t_ms": 2000}],
                "other_track": [{"t_ms": 5000}],
            },
        }

    def test_shape_for_plan(self, shaper: ContextShaper, mock_song_features: dict) -> None:
        """Test context shaping for planning stage."""
        shaped = shaper.shape_for_stage(stage=Stage.PLAN, song_features=mock_song_features)

        assert isinstance(shaped, ShapedContext)
        assert shaped.stage == Stage.PLAN
        assert shaped.token_estimate < 5000  # Target ~4k
        assert shaped.reduction_pct > 80  # >80% reduction

        # Verify structure
        assert "timing" in shaped.data
        assert "energy" in shaped.data
        assert "recommendations" in shaped.data

    def test_shape_for_plan_with_templates(
        self,
        shaper: ContextShaper,
        mock_song_features: dict,
        mock_template_metadata: list,
    ) -> None:
        """Test planning context with template metadata."""
        shaped = shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=mock_song_features,
            template_metadata=mock_template_metadata,
        )

        assert "templates" in shaped.data
        assert len(shaped.data["templates"]) == 1
        assert shaped.data["templates"][0]["template_id"] == "gentle_sweep_breathe"

    def test_shape_for_plan_with_fingerprint(
        self,
        shaper: ContextShaper,
        mock_song_features: dict,
        mock_seq_fingerprint: dict,
    ) -> None:
        """Test planning context with sequence fingerprint."""
        shaped = shaper.shape_for_stage(
            stage=Stage.PLAN,
            song_features=mock_song_features,
            seq_fingerprint=mock_seq_fingerprint,
        )

        assert "sequence_fingerprint" in shaped.data
        fingerprint = shaped.data["sequence_fingerprint"]
        assert "existing_effects" in fingerprint
        assert "color_palette" in fingerprint
        assert len(fingerprint["color_palette"]) <= 5

    def test_shape_for_implementation(
        self, shaper: ContextShaper, mock_song_features: dict
    ) -> None:
        """Test context shaping for implementation stage."""
        plan = {"sections": [{"template_id": "test"}]}

        shaped = shaper.shape_for_stage(
            stage=Stage.IMPLEMENTATION, song_features=mock_song_features, plan=plan
        )

        assert shaped.stage == Stage.IMPLEMENTATION
        assert shaped.token_estimate < 8000  # Target ~6k

        # Verify structure - now uses unified song_map instead of separate timing arrays
        assert "plan" in shaped.data
        assert "song_map" in shaped.data
        assert "metadata" in shaped.data["song_map"]
        assert "events" in shaped.data["song_map"]

    def test_shape_for_judge(self, shaper: ContextShaper, mock_song_features: dict) -> None:
        """Test context shaping for judge stage."""
        plan = {"sections": [{"name": "verse_1", "template_id": "test"}]}

        shaped = shaper.shape_for_stage(
            stage=Stage.JUDGE, song_features=mock_song_features, plan=plan
        )

        assert shaped.stage == Stage.JUDGE
        assert shaped.token_estimate < 6000  # Target ~5k

        # Verify structure
        assert "plan_summary" in shaped.data
        assert "audio_summary" in shaped.data

    def test_shape_for_refinement(self, shaper: ContextShaper, mock_song_features: dict) -> None:
        """Test context shaping for refinement stage."""
        plan = {"sections": [{"template_id": "test"}]}

        shaped = shaper.shape_for_stage(
            stage=Stage.REFINEMENT, song_features=mock_song_features, plan=plan
        )

        assert shaped.stage == Stage.REFINEMENT
        assert "previous_plan" in shaped.data
        assert shaped.data["previous_plan"] == plan

    def test_consolidate_timing(self, shaper: ContextShaper, mock_song_features: dict) -> None:
        """Test timing consolidation reduces tokens."""
        timing = shaper._consolidate_timing(mock_song_features)

        # Should have summary, not full array
        assert len(timing["bars_summary"]) < len(mock_song_features["bars_s"])
        assert timing["bar_count"] == len(mock_song_features["bars_s"])
        assert "duration_s" in timing
        assert "tempo_bpm" in timing

    def test_consolidate_timing_short_song(self, shaper: ContextShaper) -> None:
        """Test timing consolidation for short songs."""
        song_features = {
            "duration_s": 40.0,
            "tempo_bpm": 120.0,
            "time_signature": {"time_signature": "4/4"},
            "bars_s": [i * 2.0 for i in range(15)],  # Only 15 bars
            "assumptions": {"beats_per_bar": 4},
        }

        timing = shaper._consolidate_timing(song_features)

        # Short songs should keep all bars
        assert len(timing["bars_summary"]) == len(song_features["bars_s"])

    def test_downsample_energy(self, shaper: ContextShaper, mock_song_features: dict) -> None:
        """Test energy downsampling."""
        energy = shaper._downsample_energy(mock_song_features)

        # Should have ~30 points
        assert len(energy["curve"]) <= 30
        assert len(energy["peaks"]) <= 5
        assert "stats" in energy

    def test_downsample_energy_no_energy(self, shaper: ContextShaper) -> None:
        """Test energy downsampling with no energy data."""
        song_features = {"duration_s": 180.0}

        energy = shaper._downsample_energy(song_features)

        # Should return empty dict
        assert energy == {}

    def test_compact_template_metadata(
        self, shaper: ContextShaper, mock_template_metadata: list
    ) -> None:
        """Test template metadata compaction with step summaries."""
        compacted = shaper._compact_template_metadata(mock_template_metadata)

        assert len(compacted) == 1
        template = compacted[0]
        assert "template_id" in template
        assert "name" in template
        assert "category" in template
        assert "description" in template
        assert "energy_range" in template
        assert len(template.get("tags", [])) <= 5

        # Check step summaries
        assert "movements" in template
        assert "geometries" in template
        assert "dimmers" in template
        assert "geometry_type" in template
        assert template["geometry_type"] in ["SYMMETRIC", "ASYMMETRIC"]

        # Check timing information
        assert "timing_type" in template
        assert "min_duration_bars" in template
        assert template["timing_type"] == "MUSICAL"
        assert template["min_duration_bars"] == 8.0

        # Verify distinct values are extracted
        assert len(template["movements"]) == 2  # sweep_lr, circle
        assert len(template["dimmers"]) == 2  # breathe, hold
        assert len(template["geometries"]) == 1  # fan (step2 has None)

    def test_summarize_fingerprint(self, shaper: ContextShaper, mock_seq_fingerprint: dict) -> None:
        """Test sequence fingerprint summarization."""
        summary = shaper._summarize_fingerprint(mock_seq_fingerprint)

        assert "existing_effects" in summary
        assert "color_palette" in summary
        assert "timing_density" in summary
        assert len(summary["color_palette"]) <= 5

    def test_calculate_recommendations(
        self, shaper: ContextShaper, mock_song_features: dict
    ) -> None:
        """Test planning recommendations calculation."""
        recommendations = shaper._calculate_recommendations(mock_song_features)

        assert "recommended_bars_per_section" in recommendations
        assert "target_section_duration_s" in recommendations
        assert "min_sections" in recommendations
        assert "max_sections" in recommendations
        assert recommendations["min_sections"] <= recommendations["max_sections"]

    def test_filter_timing_tracks(self, shaper: ContextShaper, mock_seq_fingerprint: dict) -> None:
        """Test timing track filtering."""
        filtered = shaper._filter_timing_tracks(mock_seq_fingerprint)

        # Should only include beat/phrase tracks
        assert "beat_track" in filtered
        assert "phrase_track" in filtered
        assert "other_track" not in filtered

        # Should limit events
        for events in filtered.values():
            assert len(events) <= 50

    def test_extract_selected_templates(
        self, shaper: ContextShaper, mock_template_metadata: list
    ) -> None:
        """Test extracting selected templates from plan."""
        plan = {"sections": [{"templates": ["gentle_sweep_breathe"]}]}

        selected = shaper._extract_selected_templates(mock_template_metadata, plan)

        assert len(selected) == 1
        assert selected[0]["template_id"] == "gentle_sweep_breathe"

    def test_extract_selected_templates_no_match(
        self, shaper: ContextShaper, mock_template_metadata: list
    ) -> None:
        """Test extracting templates with no match."""
        plan = {"sections": [{"templates": ["nonexistent"]}]}

        selected = shaper._extract_selected_templates(mock_template_metadata, plan)

        assert len(selected) == 0

    def test_summarize_plan(self, shaper: ContextShaper) -> None:
        """Test plan summarization."""
        plan = {
            "sections": [
                {
                    "name": "verse_1",
                    "template_id": "template_a",
                    "start_bar": 1,
                    "end_bar": 16,
                },
                {
                    "name": "chorus_1",
                    "template_id": "template_b",
                    "start_bar": 17,
                    "end_bar": 32,
                },
            ]
        }

        summary = shaper._summarize_plan(plan)

        assert summary["section_count"] == 2
        assert len(summary["sections"]) == 2
        assert len(summary["templates_used"]) == 2
        assert "template_a" in summary["templates_used"]
        assert "template_b" in summary["templates_used"]

    def test_summarize_plan_none(self, shaper: ContextShaper) -> None:
        """Test plan summarization with None."""
        summary = shaper._summarize_plan(None)

        assert summary == {}

    def test_unknown_stage_raises_error(
        self, shaper: ContextShaper, mock_song_features: dict
    ) -> None:
        """Test that unknown stage raises ValueError."""
        with pytest.raises(ValueError, match="Unknown stage"):
            shaper.shape_for_stage(
                stage="invalid_stage",  # type: ignore
                song_features=mock_song_features,
            )
