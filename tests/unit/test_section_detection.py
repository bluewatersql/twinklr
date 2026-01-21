"""Unit tests for section detection to prevent over-classification of chorus."""

from __future__ import annotations

from blinkb0t.core.domains.audio.structure.sections import label_section as _label_section


class TestSectionLabeling:
    """Test section labeling heuristics."""

    def test_intro_detection(self) -> None:
        """Test that intro sections are detected at the start with low energy."""
        label = _label_section(
            idx=0,
            total_sections=8,
            repeat_count=0,
            max_similarity=0.7,
            energy_rank=0.3,
            start_s=0.0,
            end_s=15.0,
            duration=180.0,
        )
        assert label == "intro"

    def test_outro_detection(self) -> None:
        """Test that outro sections are detected at the end with low energy."""
        label = _label_section(
            idx=7,
            total_sections=8,
            repeat_count=0,
            max_similarity=0.6,
            energy_rank=0.2,
            start_s=165.0,
            end_s=180.0,
            duration=180.0,
        )
        assert label == "outro"

    def test_chorus_high_repeat_high_energy(self) -> None:
        """Test that high repetition + high energy = chorus."""
        label = _label_section(
            idx=3,
            total_sections=8,
            repeat_count=4,
            max_similarity=0.95,
            energy_rank=0.85,
            start_s=60.0,
            end_s=90.0,
            duration=180.0,
        )
        assert label == "chorus"

    def test_chorus_moderate_repeat_very_high_energy(self) -> None:
        """Test that moderate repetition + very high energy = chorus."""
        label = _label_section(
            idx=3,
            total_sections=8,
            repeat_count=2,
            max_similarity=0.88,
            energy_rank=0.90,
            start_s=60.0,
            end_s=90.0,
            duration=180.0,
        )
        assert label == "chorus"

    def test_verse_moderate_repeat_moderate_energy(self) -> None:
        """Test that moderate repetition + moderate energy = verse (not chorus)."""
        # This is the key test - prevents the bug where everything became chorus
        label = _label_section(
            idx=2,
            total_sections=8,
            repeat_count=2,
            max_similarity=0.85,
            energy_rank=0.55,  # Moderate energy (was being classified as chorus before)
            start_s=30.0,
            end_s=60.0,
            duration=180.0,
        )
        assert label == "verse", "Moderate repeat + moderate energy should be verse, not chorus"

    def test_verse_moderate_repeat_low_energy(self) -> None:
        """Test that moderate repetition + low energy = verse."""
        label = _label_section(
            idx=2,
            total_sections=8,
            repeat_count=3,
            max_similarity=0.80,
            energy_rank=0.40,
            start_s=30.0,
            end_s=60.0,
            duration=180.0,
        )
        assert label == "verse"

    def test_verse_low_repeat_mid_energy(self) -> None:
        """Test that low repetition + mid energy = verse."""
        label = _label_section(
            idx=2,
            total_sections=8,
            repeat_count=1,
            max_similarity=0.70,
            energy_rank=0.50,
            start_s=30.0,
            end_s=60.0,
            duration=180.0,
        )
        assert label == "verse"

    def test_bridge_late_unique(self) -> None:
        """Test that unique sections late in song = bridge."""
        label = _label_section(
            idx=5,
            total_sections=8,
            repeat_count=0,
            max_similarity=0.65,
            energy_rank=0.55,
            start_s=120.0,
            end_s=145.0,
            duration=180.0,
        )
        assert label == "bridge"

    def test_bridge_low_repeat_late_position(self) -> None:
        """Test that low repetition in late position = bridge."""
        label = _label_section(
            idx=5,
            total_sections=8,
            repeat_count=1,
            max_similarity=0.70,
            energy_rank=0.60,
            start_s=110.0,
            end_s=135.0,
            duration=180.0,
        )
        assert label == "bridge"

    def test_not_all_high_energy_is_chorus(self) -> None:
        """Regression test: high energy alone shouldn't make it a chorus."""
        # Even with high energy, if repeats are low, it might be verse or bridge
        label = _label_section(
            idx=3,
            total_sections=8,
            repeat_count=1,
            max_similarity=0.70,
            energy_rank=0.75,
            start_s=60.0,
            end_s=90.0,
            duration=180.0,
        )
        # Should NOT be chorus (only 1 repeat)
        assert label != "chorus", "High energy with low repeats should not be chorus"

    def test_distribution_not_all_chorus(self) -> None:
        """Integration test: typical song shouldn't have all sections as chorus."""
        # Simulate a typical pop song structure
        sections_data = [
            # (idx, repeat_count, energy_rank) - typical values
            (0, 0, 0.3),  # intro
            (1, 2, 0.45),  # verse 1
            (2, 3, 0.80),  # chorus 1
            (3, 2, 0.50),  # verse 2
            (4, 3, 0.85),  # chorus 2
            (5, 1, 0.60),  # bridge
            (6, 3, 0.90),  # chorus 3
            (7, 0, 0.25),  # outro
        ]

        labels = []
        total_sections = len(sections_data)
        duration = 180.0

        for idx, repeat_count, energy_rank in sections_data:
            start_s = idx * (duration / total_sections)
            end_s = (idx + 1) * (duration / total_sections)
            label = _label_section(
                idx=idx,
                total_sections=total_sections,
                repeat_count=repeat_count,
                max_similarity=0.85,
                energy_rank=energy_rank,
                start_s=start_s,
                end_s=end_s,
                duration=duration,
            )
            labels.append(label)

        # Count section types
        chorus_count = labels.count("chorus")
        verse_count = labels.count("verse")

        # Should have a balanced distribution
        assert chorus_count <= 4, f"Too many chorus sections: {chorus_count} / {total_sections}"
        assert verse_count >= 2, f"Too few verse sections: {verse_count} / {total_sections}"
        assert "intro" in labels or "verse" in labels, "Should have intro or verse"
        assert chorus_count < total_sections * 0.6, (
            "More than 60% chorus indicates over-classification"
        )
