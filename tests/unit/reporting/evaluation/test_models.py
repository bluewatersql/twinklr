"""Tests for evaluation report models."""

from pathlib import Path

from pydantic import ValidationError
import pytest

from blinkb0t.core.reporting.evaluation.models import (
    ContinuityCheck,
    CurveAnalysis,
    CurveStats,
    EvaluationReport,
    ReportFlag,
    ReportFlagLevel,
    ReportSummary,
    RunMetadata,
    SectionReport,
    SongMetadata,
    TargetResolution,
    TemplateSelection,
)


class TestReportFlag:
    """Tests for ReportFlag model."""

    def test_valid_flag(self):
        """Test creating a valid report flag."""
        flag = ReportFlag(
            level=ReportFlagLevel.WARNING,
            code="CLAMP_PCT",
            message="Curve clamps 15% of samples",
            details={"clamp_pct": 15.0},
        )
        assert flag.level == ReportFlagLevel.WARNING
        assert flag.code == "CLAMP_PCT"
        assert flag.details["clamp_pct"] == 15.0

    def test_flag_is_frozen(self):
        """Test that flag is immutable."""
        flag = ReportFlag(level=ReportFlagLevel.ERROR, code="TEST", message="Test message")
        with pytest.raises(ValidationError):
            flag.level = ReportFlagLevel.INFO  # type: ignore


class TestRunMetadata:
    """Tests for RunMetadata model."""

    def test_valid_metadata(self):
        """Test creating valid run metadata."""
        metadata = RunMetadata(
            run_id="abc123",
            timestamp="2026-01-24T12:00:00Z",
            git_sha="def456",
            engine_version="1.0.0",
            checkpoint_path=Path("/tmp/checkpoint.json"),
        )
        assert metadata.run_id == "abc123"
        assert metadata.git_sha == "def456"

    def test_metadata_without_git_sha(self):
        """Test metadata with None git SHA."""
        metadata = RunMetadata(
            run_id="abc123",
            timestamp="2026-01-24T12:00:00Z",
            git_sha=None,
            engine_version="1.0.0",
            checkpoint_path=Path("/tmp/checkpoint.json"),
        )
        assert metadata.git_sha is None


class TestSongMetadata:
    """Tests for SongMetadata model."""

    def test_valid_song_metadata(self):
        """Test creating valid song metadata."""
        metadata = SongMetadata(
            bpm=128.0,
            time_signature="3/4",
            bars_total=96,
            bar_duration_ms=1875.0,
            song_structure={"intro": [0, 8]},
        )
        assert metadata.bpm == 128.0
        assert metadata.time_signature == "3/4"
        assert metadata.bars_total == 96


class TestCurveStats:
    """Tests for CurveStats model."""

    def test_valid_stats(self):
        """Test creating valid curve statistics."""
        stats = CurveStats(
            min=0.1,
            max=0.9,
            range=0.8,
            mean=0.5,
            std=0.2,
            clamp_pct=5.0,
            energy=0.15,
        )
        assert stats.min == 0.1
        assert stats.max == 0.9
        assert stats.clamp_pct == 5.0


class TestContinuityCheck:
    """Tests for ContinuityCheck model."""

    def test_passing_continuity(self):
        """Test continuity check that passes."""
        check = ContinuityCheck(loop_delta=0.02, ok=True, threshold=0.05)
        assert check.ok is True
        assert check.loop_delta == 0.02

    def test_failing_continuity(self):
        """Test continuity check that fails."""
        check = ContinuityCheck(loop_delta=0.10, ok=False, threshold=0.05)
        assert check.ok is False


class TestCurveAnalysis:
    """Tests for CurveAnalysis model."""

    def test_valid_analysis(self):
        """Test creating valid curve analysis."""
        stats = CurveStats(
            min=0.0, max=1.0, range=1.0, mean=0.5, std=0.3, clamp_pct=0.0, energy=0.2
        )
        continuity = ContinuityCheck(loop_delta=0.01, ok=True)

        analysis = CurveAnalysis(
            role="OUTER_LEFT",
            channel="PAN",
            space="norm",
            plot_path=Path("/tmp/plot.png"),
            stats=stats,
            continuity=continuity,
        )
        assert analysis.role == "OUTER_LEFT"
        assert analysis.channel == "PAN"
        assert analysis.space == "norm"


class TestTemplateSelection:
    """Tests for TemplateSelection model."""

    def test_template_without_preset(self):
        """Test template selection without preset."""
        template = TemplateSelection(
            template_id="fan_pulse",
            preset_id=None,
            modifiers={"intensity": "high"},
            reasoning="High energy chorus",
        )
        assert template.template_id == "fan_pulse"
        assert template.preset_id is None
        assert template.modifiers["intensity"] == "high"

    def test_template_with_preset(self):
        """Test template selection with preset."""
        template = TemplateSelection(
            template_id="sweep_lr", preset_id="ENERGETIC", modifiers={}, reasoning=""
        )
        assert template.preset_id == "ENERGETIC"


class TestSectionReport:
    """Tests for SectionReport model."""

    def test_section_report_structure(self):
        """Test creating a section report."""
        targets = TargetResolution(
            bindings={"fixture_01": "OUTER_LEFT"}, resolved_roles=["OUTER_LEFT"]
        )

        report = SectionReport(
            section_id="verse_1",
            label="Verse 1",
            bar_range=(1.0, 21.0),
            time_range_ms=(0, 39375),
            selected_template=None,
            segments=None,
            targets=targets,
            curves=[],
            flags=[],
        )
        assert report.section_id == "verse_1"
        assert report.bar_range == (1.0, 21.0)
        assert len(report.flags) == 0


class TestReportSummary:
    """Tests for ReportSummary model."""

    def test_summary_defaults(self):
        """Test summary with default values."""
        summary = ReportSummary(sections=5)
        assert summary.sections == 5
        assert summary.total_warnings == 0
        assert summary.total_errors == 0

    def test_summary_with_counts(self):
        """Test summary with error/warning counts."""
        summary = ReportSummary(
            sections=10,
            total_warnings=3,
            total_errors=1,
            templates_used=["fan_pulse", "sweep_lr"],
        )
        assert summary.total_warnings == 3
        assert summary.total_errors == 1
        assert len(summary.templates_used) == 2


class TestEvaluationReport:
    """Tests for EvaluationReport model."""

    def test_minimal_report(self):
        """Test creating a minimal evaluation report."""
        run = RunMetadata(
            run_id="test",
            timestamp="2026-01-24T12:00:00Z",
            engine_version="1.0.0",
            checkpoint_path=Path("/tmp/test.json"),
        )
        song = SongMetadata(bpm=120.0, time_signature="4/4", bars_total=64, bar_duration_ms=2000.0)
        summary = ReportSummary(sections=0)

        report = EvaluationReport(run=run, song=song, summary=summary, sections=[])
        assert report.schema_version == "1.0.0"
        assert report.run.run_id == "test"
        assert len(report.sections) == 0

    def test_report_serialization(self):
        """Test that report can be serialized to dict."""
        run = RunMetadata(
            run_id="test",
            timestamp="2026-01-24T12:00:00Z",
            engine_version="1.0.0",
            checkpoint_path=Path("/tmp/test.json"),
        )
        song = SongMetadata(bpm=120.0, time_signature="4/4", bars_total=64, bar_duration_ms=2000.0)
        summary = ReportSummary(sections=0)

        report = EvaluationReport(run=run, song=song, summary=summary, sections=[])
        data = report.model_dump(mode="json")

        assert data["schema_version"] == "1.0.0"
        assert data["run"]["run_id"] == "test"
        assert isinstance(data["run"]["checkpoint_path"], str)
