"""Tracked, deterministic MIR A/B fixture definitions and synthesis."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class FixtureSection(BaseModel):
    """Annotated functional section."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_s: float = Field(ge=0.0)
    end_s: float = Field(gt=0.0)
    label: str


class SynthesisRecipe(BaseModel):
    """Parameters sufficient to recreate an excerpt without tracked audio blobs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["metered", "annotated_beats", "ambient", "syncopated"]
    bpm: float | None = Field(default=None, gt=0.0)
    accent_pattern: list[float]
    tone_hz: list[float]


class MIRFixture(BaseModel):
    """One fully annotated benchmark excerpt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    description: str
    category: str
    duration_s: float = Field(gt=0.0)
    beats_per_bar: int = Field(gt=0)
    beat_times_s: list[float]
    downbeat_times_s: list[float]
    sections: list[FixtureSection]
    synthesis: SynthesisRecipe

    @property
    def section_boundaries_s(self) -> list[float]:
        """Annotated functional transitions, excluding trivial excerpt edges."""
        return [section.start_s for section in self.sections[1:]]


class MIRFixtureManifest(BaseModel):
    """Versioned collection of committed MIR fixtures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    sample_rate: int = Field(gt=0)
    fixtures: list[MIRFixture]


def load_fixture_manifest(path: Path) -> MIRFixtureManifest:
    """Load and validate a fixture manifest."""
    return MIRFixtureManifest.model_validate_json(path.read_text(encoding="utf-8"))


def synthesize_fixture(fixture: MIRFixture, *, sample_rate: int) -> np.ndarray:
    """Recreate a fixture exactly from its committed annotations and recipe."""
    sample_count = round(fixture.duration_s * sample_rate)
    time = np.arange(sample_count, dtype=np.float64) / sample_rate
    audio = np.zeros(sample_count, dtype=np.float64)

    for section_index, section in enumerate(fixture.sections):
        start = max(0, round(section.start_s * sample_rate))
        end = min(sample_count, round(section.end_s * sample_rate))
        frequency = fixture.synthesis.tone_hz[section_index % len(fixture.synthesis.tone_hz)]
        local_time = time[start:end] - section.start_s
        fade_samples = min(round(0.08 * sample_rate), max(1, (end - start) // 4))
        envelope = np.ones(end - start, dtype=np.float64)
        envelope[:fade_samples] = np.linspace(0.0, 1.0, fade_samples, endpoint=False)
        envelope[-fade_samples:] = np.linspace(1.0, 0.0, fade_samples, endpoint=False)
        audio[start:end] += 0.14 * envelope * np.sin(2.0 * np.pi * frequency * local_time)

    click_length = max(8, round(0.012 * sample_rate))
    click_time = np.arange(click_length, dtype=np.float64) / sample_rate
    click = np.exp(-click_time * 180.0) * np.sin(2.0 * np.pi * 1800.0 * click_time)
    ambient_scale = 0.38 if fixture.synthesis.kind == "ambient" else 1.0
    for beat_index, beat_s in enumerate(fixture.beat_times_s):
        start = round(beat_s * sample_rate)
        end = min(sample_count, start + click_length)
        if start >= sample_count:
            continue
        accent = fixture.synthesis.accent_pattern[
            beat_index % len(fixture.synthesis.accent_pattern)
        ]
        audio[start:end] += ambient_scale * accent * click[: end - start]

    if fixture.synthesis.kind == "syncopated":
        for first, second in zip(fixture.beat_times_s, fixture.beat_times_s[1:], strict=False):
            start = round(((first + second) / 2.0) * sample_rate)
            end = min(sample_count, start + click_length)
            audio[start:end] += 0.28 * click[: end - start]

    peak = float(np.max(np.abs(audio)))
    if peak > 0.0:
        audio *= 0.9 / peak
    return audio.astype(np.float32)
