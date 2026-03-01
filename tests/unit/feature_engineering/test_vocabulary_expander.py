"""Tests for VocabularyExpander — Spec 05 (Vocabulary Expansion).

Covers all 6 test cases from the spec:
1. Compound motion discovery
2. Compound energy discovery
3. Support filtering
4. Signature parsing
5. Sidecar integration
6. Edge cases
"""

from __future__ import annotations

import json
from pathlib import Path
import uuid

from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.stacks import (
    EffectStack,
    EffectStackCatalog,
    EffectStackLayer,
)
from twinklr.core.feature_engineering.models.vocabulary import (
    VocabularyExtensions,
)
from twinklr.core.feature_engineering.vocabulary_expander import VocabularyExpander
from twinklr.core.sequencer.vocabulary import BlendMode, LayerRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _phrase(
    *,
    effect_family: str = "color_wash",
    effect_type: str = "colorwash",
    motion_class: str = "static",
    energy_class: str = "low",
    layer_index: int = 0,
    start_ms: int = 0,
    end_ms: int = 5000,
    package_id: str = "pkg-1",
    sequence_file_id: str = "seq-1",
    target_name: str = "MegaTree",
) -> EffectPhrase:
    """Build a minimal EffectPhrase for testing."""
    phrase_id = str(uuid.uuid4())
    return EffectPhrase(
        schema_version="1.2",
        phrase_id=phrase_id,
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        effect_event_id=str(uuid.uuid4()),
        effect_type=effect_type,
        effect_family=effect_family,
        motion_class=MotionClass(motion_class),
        color_class=ColorClass.UNKNOWN,
        energy_class=EnergyClass(energy_class),
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name=target_name,
        layer_index=layer_index,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        param_signature="abc123",
    )


def _stack(
    *,
    families: tuple[str, ...] = ("color_wash", "single_strand"),
    roles: tuple[str, ...] = ("b", "a"),
    blends: tuple[str, ...] | None = None,
    count: int = 20,
) -> tuple[EffectStack, ...]:
    """Build ``count`` identical EffectStack instances with the given layers.

    Args:
        families: Effect family for each layer.
        roles: Role abbreviation for each layer (b=base, r=rhythm, a=accent).
        blends: Blend mode for each layer.  Defaults to NORMAL for all.
        count: Number of duplicate stacks to produce.

    Returns:
        Tuple of EffectStack instances.
    """
    if blends is None:
        blends = tuple("normal" for _ in families)

    _role_map = {"b": LayerRole.BASE, "r": LayerRole.RHYTHM, "a": LayerRole.ACCENT}
    _blend_map = {
        "normal": BlendMode.NORMAL,
        "add": BlendMode.ADD,
        "screen": BlendMode.SCREEN,
    }

    # Build effect-family -> axis lookup for phrases
    _family_axes: dict[str, dict[str, str]] = {
        "color_wash": {"motion_class": "static", "energy_class": "low"},
        "single_strand": {"motion_class": "sweep", "energy_class": "mid"},
        "on": {"motion_class": "static", "energy_class": "mid"},
        "twinkle": {"motion_class": "sparkle", "energy_class": "mid"},
        "bars": {"motion_class": "sweep", "energy_class": "high"},
        "shimmer": {"motion_class": "sparkle", "energy_class": "high"},
        "shockwave": {"motion_class": "sweep", "energy_class": "high"},
        "fireworks": {"motion_class": "sparkle", "energy_class": "burst"},
        "strobe": {"motion_class": "pulse", "energy_class": "burst"},
        "lightning": {"motion_class": "pulse", "energy_class": "burst"},
        "guitar": {"motion_class": "pulse", "energy_class": "high"},
    }

    layers: list[EffectStackLayer] = []
    sig_parts: list[str] = []
    for i, (fam, role_abbrev, blend_str) in enumerate(zip(families, roles, blends)):
        axes = _family_axes.get(fam, {"motion_class": "unknown", "energy_class": "unknown"})
        p = _phrase(
            effect_family=fam,
            effect_type=fam,
            motion_class=axes["motion_class"],
            energy_class=axes["energy_class"],
            layer_index=i,
        )
        layer_role = _role_map.get(role_abbrev, LayerRole.BASE)
        blend_mode = _blend_map.get(blend_str, BlendMode.NORMAL)
        layers.append(
            EffectStackLayer(
                phrase=p,
                layer_role=layer_role,
                blend_mode=blend_mode,
                mix=1.0,
            )
        )
        sig_parts.append(f"{fam}@{role_abbrev}|{blend_str}")

    signature = "+".join(sig_parts)

    stacks: list[EffectStack] = []
    for _ in range(count):
        stack_id = str(uuid.uuid4())
        stacks.append(
            EffectStack(
                stack_id=stack_id,
                package_id="pkg-1",
                sequence_file_id="seq-1",
                target_name="MegaTree",
                start_ms=0,
                end_ms=5000,
                duration_ms=5000,
                layers=tuple(layers),
                layer_count=len(layers),
                stack_signature=signature,
            )
        )
    return tuple(stacks)


def _catalog(
    stacks: tuple[EffectStack, ...],
) -> EffectStackCatalog:
    """Wrap stacks in an EffectStackCatalog."""
    multi = sum(1 for s in stacks if s.layer_count > 1)
    single = len(stacks) - multi
    max_layers = max((s.layer_count for s in stacks), default=0)
    return EffectStackCatalog(
        total_phrase_count=sum(s.layer_count for s in stacks),
        total_stack_count=len(stacks),
        single_layer_count=single,
        multi_layer_count=multi,
        max_layer_count=max_layers,
        stacks=stacks,
    )


# ===========================================================================
# 1. Compound Motion Discovery
# ===========================================================================


class TestCompoundMotionDiscovery:
    """Stack combinations produce correct compound motion terms."""

    def test_wash_and_chase(self) -> None:
        """color_wash@b + single_strand@a -> wash_and_chase (static + sweep)."""
        stacks = _stack(families=("color_wash", "single_strand"), roles=("b", "a"), count=20)
        catalog = _catalog(stacks)
        expander = VocabularyExpander()
        result = expander.expand(stack_catalog=catalog)

        motion_terms = {t.term for t in result.compound_motion_terms}
        assert "wash_and_chase" in motion_terms

        term = next(t for t in result.compound_motion_terms if t.term == "wash_and_chase")
        assert term.component_families == ("color_wash", "single_strand")
        assert term.corpus_support == 20

    def test_dual_chase(self) -> None:
        """single_strand@b + single_strand@a -> dual_chase (sweep + sweep)."""
        stacks = _stack(families=("single_strand", "single_strand"), roles=("b", "a"), count=15)
        catalog = _catalog(stacks)
        expander = VocabularyExpander()
        result = expander.expand(stack_catalog=catalog)

        motion_terms = {t.term for t in result.compound_motion_terms}
        assert "dual_chase" in motion_terms

    def test_wash_and_sparkle(self) -> None:
        """color_wash@b + twinkle@a -> wash_and_sparkle (static + sparkle)."""
        stacks = _stack(families=("color_wash", "twinkle"), roles=("b", "a"), count=25)
        catalog = _catalog(stacks)
        expander = VocabularyExpander()
        result = expander.expand(stack_catalog=catalog)

        motion_terms = {t.term for t in result.compound_motion_terms}
        assert "wash_and_sparkle" in motion_terms


# ===========================================================================
# 2. Compound Energy Discovery
# ===========================================================================


class TestCompoundEnergyDiscovery:
    """Stack combinations produce correct compound energy terms."""

    def test_wash_burst(self) -> None:
        """base=low + accent=burst -> wash_burst."""
        stacks = _stack(families=("color_wash", "fireworks"), roles=("b", "a"), count=20)
        catalog = _catalog(stacks)
        expander = VocabularyExpander()
        result = expander.expand(stack_catalog=catalog)

        energy_terms = {t.term for t in result.compound_energy_terms}
        assert "wash_burst" in energy_terms

        term = next(t for t in result.compound_energy_terms if t.term == "wash_burst")
        assert term.base_energy == "low"
        assert term.accent_energy == "burst"

    def test_building(self) -> None:
        """base=mid + accent=high -> building."""
        stacks = _stack(families=("single_strand", "bars"), roles=("b", "a"), count=20)
        catalog = _catalog(stacks)
        expander = VocabularyExpander()
        result = expander.expand(stack_catalog=catalog)

        energy_terms = {t.term for t in result.compound_energy_terms}
        assert "building" in energy_terms

        term = next(t for t in result.compound_energy_terms if t.term == "building")
        assert term.base_energy == "mid"
        assert term.accent_energy == "high"


# ===========================================================================
# 3. Support Filtering
# ===========================================================================


class TestSupportFiltering:
    """Only terms with corpus_support >= 10 are included."""

    def test_below_threshold_filtered(self) -> None:
        """Stack pattern with 5 occurrences (< threshold 10) -> not in output."""
        stacks = _stack(families=("color_wash", "single_strand"), roles=("b", "a"), count=5)
        catalog = _catalog(stacks)
        expander = VocabularyExpander()
        result = expander.expand(stack_catalog=catalog)

        motion_terms = {t.term for t in result.compound_motion_terms}
        assert "wash_and_chase" not in motion_terms

    def test_above_threshold_included(self) -> None:
        """Stack pattern with 15 occurrences -> included."""
        stacks = _stack(families=("color_wash", "single_strand"), roles=("b", "a"), count=15)
        catalog = _catalog(stacks)
        expander = VocabularyExpander()
        result = expander.expand(stack_catalog=catalog)

        motion_terms = {t.term for t in result.compound_motion_terms}
        assert "wash_and_chase" in motion_terms


# ===========================================================================
# 4. Signature Parsing
# ===========================================================================


class TestSignatureParsing:
    """Stack signatures are correctly parsed into families and roles."""

    def test_three_layer_signature(self) -> None:
        """3-layer signature parses to correct families and roles."""
        stacks = _stack(
            families=("color_wash", "bars", "twinkle"),
            roles=("b", "r", "a"),
            blends=("normal", "add", "screen"),
            count=20,
        )
        catalog = _catalog(stacks)
        expander = VocabularyExpander()

        # Verify the signature format is correct
        sig = stacks[0].stack_signature
        assert sig == "color_wash@b|normal+bars@r|add+twinkle@a|screen"

        # Parse and verify
        parsed = expander.parse_signature(sig)
        assert parsed.families == ("color_wash", "bars", "twinkle")
        assert parsed.roles == ("b", "r", "a")


# ===========================================================================
# 5. Sidecar Integration
# ===========================================================================


class TestSidecarIntegration:
    """Vocabulary extensions load without changing phrase models."""

    def test_vocabulary_loads_as_json(self, tmp_path: Path) -> None:
        """VocabularyExtensions can be serialized/deserialized as JSON sidecar."""
        stacks = _stack(families=("color_wash", "single_strand"), roles=("b", "a"), count=20)
        catalog = _catalog(stacks)
        expander = VocabularyExpander()
        result = expander.expand(stack_catalog=catalog)

        # Serialize to JSON
        out_path = tmp_path / "vocabulary_extensions.json"
        out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

        # Reload
        raw = json.loads(out_path.read_text(encoding="utf-8"))
        reloaded = VocabularyExtensions.model_validate(raw)

        assert reloaded.schema_version == "v1.0.0"
        assert len(reloaded.compound_motion_terms) == len(result.compound_motion_terms)
        assert len(reloaded.compound_energy_terms) == len(result.compound_energy_terms)

    def test_no_effect_phrase_schema_changes(self) -> None:
        """EffectPhrase model does NOT have vocabulary extension fields."""
        fields = set(EffectPhrase.model_fields.keys())
        # Vocabulary terms are sidecar data -- not embedded in EffectPhrase
        assert "compound_motion_term" not in fields
        assert "compound_energy_term" not in fields


# ===========================================================================
# 6. Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases: single-layer stacks, unknown families, empty catalog."""

    def test_single_layer_stacks_no_compound_terms(self) -> None:
        """Single-layer stacks produce no compound terms."""
        stacks = _stack(families=("color_wash",), roles=("b",), count=50)
        catalog = _catalog(stacks)
        expander = VocabularyExpander()
        result = expander.expand(stack_catalog=catalog)

        assert len(result.compound_motion_terms) == 0
        assert len(result.compound_energy_terms) == 0

    def test_unknown_family_skipped(self) -> None:
        """Unknown effect family in stack -> that stack is skipped for term discovery."""
        stacks = _stack(
            families=("color_wash", "totally_unknown_effect"),
            roles=("b", "a"),
            count=20,
        )
        catalog = _catalog(stacks)
        expander = VocabularyExpander()
        result = expander.expand(stack_catalog=catalog)

        # Should not produce compound terms for unknown families
        assert len(result.compound_motion_terms) == 0
        assert len(result.compound_energy_terms) == 0

    def test_empty_catalog(self) -> None:
        """Empty catalog produces empty extensions."""
        catalog = EffectStackCatalog(
            total_phrase_count=0,
            total_stack_count=0,
            single_layer_count=0,
            multi_layer_count=0,
            max_layer_count=0,
            stacks=(),
        )
        expander = VocabularyExpander()
        result = expander.expand(stack_catalog=catalog)

        assert len(result.compound_motion_terms) == 0
        assert len(result.compound_energy_terms) == 0
        assert result.total_stack_signatures_analyzed == 0
        assert result.total_multi_layer_stacks == 0
