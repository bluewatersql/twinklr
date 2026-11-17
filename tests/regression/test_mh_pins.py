"""Committed pins of moving-head output, so an unintended change to it fails CI.

Every catalog family, base and each declared preset, renders one 8-bar section on four
heads (the zoom pilot rig for `zoom_wave`, the family rig otherwise) over two synthetic
grids, a steady 500 ms beat and a seeded mix of 430, 500 and 580 ms beats; one
multi-section plan of four families renders over the varied grid and delivers its
`.xsq`; one gated plan renders under a hand-built gate result (an excluded preset and
effective variants), over a dark span, with `reposition_fallback="preserve_aim"`. Each
case pins its render fingerprint and the SHA-256 of its encoded frames
(`_frames_sha256`); the multi-section and gated cases also pin the delivered `.xsq`.

The values were recorded when the old renderer was removed (C1.2), from that tree; the
encoded frames and the `.xsq` are byte-identical to those of the commit before it
(`mh-last-with-legacy-renderer`), whose fingerprints differ only because the render
policy lost its `mode` key. C1.3 re-recorded the fingerprints alone: the template and
rig dumps they hash lost the old renderer's fields; frames and `.xsq` are unchanged.
C1.4 re-recorded them again: the hashed revision string and template keys were renamed;
frames and `.xsq` are unchanged. W2 re-recorded them again: the plan they hash is in the
song-intent planner contract (parts, intent fields); frames and `.xsq` are unchanged. W4
re-recorded them again: `RENDERER_REVISION` 3 (a section's colour and gobo render);
frames and `.xsq` are unchanged, every pinned plan being as authored. W4 also added the
song-intent pin (`INTENT_PIN`): colour and gobo sections on a tagged rig. The W3/W4
review fix round re-recorded every fingerprint once more (revision 4); every frame and
`.xsq` hash, `INTENT_PIN`'s included, is unchanged (its boundaries dip at 120 BPM, as
before). An intended
output change bumps `RENDERER_REVISION` and re-records these pins in the same commit,
saying why.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
import hashlib
import json
from pathlib import Path
import random

import pytest

from tests.support import moving_heads as m
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.sequencer.moving_heads.export.frame_encoder import EncodedFixtureFrame
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline, TemplateAdmission
from twinklr.core.sequencer.moving_heads.song_intent import SectionPalette
from twinklr.core.sequencer.moving_heads.templates import get_template
from twinklr.core.sequencer.theming.catalog import get_palette
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

HEADS = ("MH1", "MH2", "MH3", "MH4")

PINS: dict[str, tuple[str, str]] = {
    "steady/finite_snap_hold/base": (
        "b389f4884015dc8fc874020ea8911a07cb2817273c5020dc06e3d0c2861e7bae",
        "8dc76627bbfb3e4e0a170d097e491277cdb571b09c41198381db8cbcc374e120",
    ),
    "steady/finite_snap_hold/narrow": (
        "fcb0b849f100e7d965b1f88145fc7047182c1994dc670a1b5451b174baa24601",
        "c0d8292c375a952740fbbb4fdec44ca69ed99c1bc90decfe2f2f22b57387ccce",
    ),
    "steady/finite_snap_hold/slow": (
        "a39776f8a12e7006d5f6dd796391f4ba71633dc4e6922dd9d9157bc8d33e6cd0",
        "4d455965979b705ad9af8136e4fd229c7b5374635e1786d07b8cab7636861b9d",
    ),
    "steady/fly_in_cascade/base": (
        "fca2c589e71c8510769125505c3e95798f498fcf6ed828557074168e3d2953f8",
        "ffdfb044c11edf3040dd81744d17558a2d46c21181071367cca5f752a8413b0d",
    ),
    "steady/fly_in_cascade/narrow": (
        "5fbc1dd578eeb91e167e03d08b0d6794674245de8c4135852ce835be9c78dcbb",
        "0280d85aaf1e832fc23b428e311b24ccb67dac720116f25f71d147261f88f310",
    ),
    "steady/fly_in_cascade/slow": (
        "9d897f2d6e136326b6aaea3b0a324daf1afdf37c4c9ef04574cd93466cb95421",
        "dd49563a5956e1e52f4a2c01e8f005a64a297ff28f9155f3eb05d10a29312433",
    ),
    "steady/fly_out_cascade/base": (
        "1d5f7da0a60f24108be1775004d2d7e6c380b74d2d969ed72a711db6f3eeb881",
        "4235e01012dddfdae05f050fa904a9efa2e8eb4cf4f3b7e2ddd06b23951c733e",
    ),
    "steady/fly_out_cascade/narrow": (
        "a183ecf318420b0d6d8541caebfceaf7647cca4312dcbc6be777b33181c25843",
        "150edd82e9273731bd9ab781ab5c6caf420cf5d1129cddb637915687dab01a88",
    ),
    "steady/fly_out_cascade/slow": (
        "6e9a7f9de87307c5e82895b9994bdba420b7d8187ce7bca453b0d76368835ddd",
        "c7e91342cab3b42a868f59ab824961da433ac89db0c5646f1fd41e29b0444a70",
    ),
    "steady/masked_wheel_flick/base": (
        "ff88d845dac863dd47150db64bb70e8addbd9a5d41a9dd653ef160ffad42ee80",
        "08ce9090980dbfefa79b6d78c90ef0f0b0c8ef3a19bb47d193d9af34805cd2de",
    ),
    "steady/masked_wheel_flick/narrow": (
        "94376d395788bca11c9c2c35e2b7963e545f5ea06f79246c5fd96e8a804b60e4",
        "2537e7e6cf39dad19aadb07a271b223f83c2af7fbbe52b4732f6416cee5993ad",
    ),
    "steady/masked_wheel_flick/slow": (
        "eb08ab9b110d396297ba6f94a691d5dbb2b4ad1a1ef700e7cc13b14640339f26",
        "56a758e57a37773c558bff6f8134843cf45c76d005021a6e882374d16d96431a",
    ),
    "steady/mirror_wings/base": (
        "8fe3228fd79d4abe3aaf935ddc35064dfc37b473121552d22add48672e4b4bd2",
        "8e3cb9be3de61f968b065d8d0442ac5551becdbbf4624afb76b13a58e0f000fd",
    ),
    "steady/mirror_wings/narrow": (
        "3f6242586390b0b190987fd19edda3f8e3695b9ef07c27a4bf534978c0c36800",
        "d83a23f4fea33e3e6f1b2bbfabdc0b5c26f605b673861c0021a1cc1c8bd36a1b",
    ),
    "steady/mirror_wings/slow": (
        "83b927f0f79c316669962ccd978ffedcfe96c06b933811531b7833df546eb345",
        "bbcdbab3564fa3d0a7f107562326940ef92fa3f38130a37ac9d8b43f68bdd3b6",
    ),
    "steady/target_orbit/base": (
        "6ab217cfc7bafc608ff1c9fb94873f801863ebc86e8c470665f05cda36cb7c12",
        "78d35ed327d359ca0cc456a151ae19f800a20b80ac1cc040ea4448be4d014ed1",
    ),
    "steady/target_orbit/narrow": (
        "a51a544fc6e33cb623a151b2ff73673a75b52df4e7b1438633730bc014712a6f",
        "a35e080540356862ecfe8738414c7cef0d781b639b869db97bc27ff0db5f180b",
    ),
    "steady/target_orbit/slow": (
        "5a8f5de6723a41748dbb0948c7d8b62fb12d038622fa6b066aa2a99d6e1d4389",
        "a2eb0bf1f4d04307af57da96941f9d02e8c47ffcc583db3361b0a754975c7d36",
    ),
    "steady/zoom_wave/base": (
        "271e4edb6b1c32c1ecd533c7fe37d79e6667cc8092c61bb7b8dd5f835b10f691",
        "bfa3f5ef5efd80d8f801f76ab412044d35161bb606288fc35f6fbeaf6970675a",
    ),
    "steady/zoom_wave/narrow": (
        "a63689f0288f1052afa23364dd7f86b19efbc7e31f1ebbe1ffcb4c9a3758252d",
        "0ddc62b56b92e1af2deedbc6b9bf47570bbe82663ff559091f3883f32e20169b",
    ),
    "steady/zoom_wave/slow": (
        "4adfb39d8a90fea7cf216b18446cb7a88d69a91de3158643187e9856baafdabc",
        "394aa7ae9fb0cc8e948e2c1b68264b9652edbddd44bcefd9d5ac0dea8e5cdb2c",
    ),
    "variable/finite_snap_hold/base": (
        "2a313918e22bedd867484bee3bfc6c4dfe18a3615de9770a3ee7ec6c8750a0af",
        "d03e6f47159bc26621e835d36e191f370e0f90955ddac4b356afb477e613ba0f",
    ),
    "variable/finite_snap_hold/narrow": (
        "a81d822443bd594a932866c6b76d8c2bb924e80fcb660b5216f40613543217d2",
        "9af804ac9d4aa9765aba26e095a80714399942811724696373cc015653545af6",
    ),
    "variable/finite_snap_hold/slow": (
        "f20b40b6d5080642221a64575f336cec5e35092bf874904133ff1af1587072de",
        "e4f7f3d9a0863c4f423dae91e481e8874d5971308aa2196a93e6fca84a6d8930",
    ),
    "variable/fly_in_cascade/base": (
        "ec07ec8c336c230e67aa2d8cedc8908c77ef02831f5eaeca13e1e7aa69cb373d",
        "34f9987fa593584b7894352d13944905315dd6c260035971de447db3c121fd7a",
    ),
    "variable/fly_in_cascade/narrow": (
        "8c8a00cb6a412cc7170309776bfd7ee86b55c3eaff6e03e716b15705c8e0cc51",
        "f2d02f0c7cdbcda887bcd350188338a8bfe0ae583b2b5e092c64b921985f1a9e",
    ),
    "variable/fly_in_cascade/slow": (
        "5c32c4458d0f6dd06268c23e8f36a1c3570e4d4306f5c24b07b008bbf8bcacc0",
        "49c484a8585d159fc61d0989eef1cc2a35fc22a5e46cf202f789736c8dd37ebe",
    ),
    "variable/fly_out_cascade/base": (
        "a787c19dfdc2f8ba5b85be4a9a68f3346fe8da1dffa1f691f9f4660bd6169ed4",
        "36f29b21188085c76c462a8cfd73f3e10f21f7adfdbca525a674c4960aca28d2",
    ),
    "variable/fly_out_cascade/narrow": (
        "0176525991abcc6165a3ef872b54f597a4d3deb1d09d1b8017cb1bfee237ac17",
        "c773f3be51097dd3ec2c309f6149f76e6c3bb7f6d1ea24416aba4662a10cb420",
    ),
    "variable/fly_out_cascade/slow": (
        "926143a009bc25a6026a64cb6a8126941385c036a96345b8eca3090a1b5ba3c9",
        "de6e5fb69f6beeeb43df051367101bd88d3d75b61e811bab2ac3e69d2edd499a",
    ),
    "variable/masked_wheel_flick/base": (
        "c44ed5fb896d7b3736dcac25b91caef4281ee6f070a61b9229af945e9e013103",
        "a628fb0ca672aba2a7c36e3ecfafcf1003b8d9c8a06adc5edcf0840004981f3f",
    ),
    "variable/masked_wheel_flick/narrow": (
        "fa6a2efdcd6296b189d7271afdef56707adaa92ae851a4de0f24d042ffc470ca",
        "a8b2c6b2cf905f657c6993dca020c6aa14bbfacc10f89bfb97491860bc81a6c3",
    ),
    "variable/masked_wheel_flick/slow": (
        "12a9cb512608e1414403252373fdbc6a6c455ccf9ee9c899b7d1d7ed3cca923c",
        "058ed1d9cbdde981fa5213dd23654d42fc86a9ebd6150fc50b089e07f85825f8",
    ),
    "variable/mirror_wings/base": (
        "37569601a2e66051a0cb5850726988f9070627df32f85c6770a088fe502a331c",
        "a59b343515d159c1603c1a0ed576afa3b6721178a643ad1c5fbc02d6bb706dde",
    ),
    "variable/mirror_wings/narrow": (
        "72c9276a466d43c480aae0e9630b42ec2ebd630fdb84895135092e9d465b1e8c",
        "4d326471bc6af0e6f429bd8e5d5b7e374587d3f545a2fe3d2ad3ef908ab6f801",
    ),
    "variable/mirror_wings/slow": (
        "4b9fc668c9bc3b5943192b8f8a0b5e12f45e4a8b5563659f178e503e873001c2",
        "cee179ea21422e5e6f268664dd79981055afedfd98c5849c5dbfd44f5b80904e",
    ),
    "variable/target_orbit/base": (
        "1cd7ba81373a0ccfbbcf43ed5867c516d30db733c18029caa7bcbf2f89368b91",
        "2bfe8b5bd75f0097dd6fb8011e38a11578764984050474ddf0ee402ae3c85fa1",
    ),
    "variable/target_orbit/narrow": (
        "f8a3e6d279d88ef33001256ca50bbfb4546c01db7b0c837319b4b867228e7916",
        "9f453dce2badb89d745c808896a8fe6d3b9feafacf5d122371d75d0a6377b4a6",
    ),
    "variable/target_orbit/slow": (
        "f5b36170eb83f6355a4376741e65b04fecd9500ac4e81fe86dde328bb488d6a9",
        "ac930585ef5e3f15f79cc7267d407f586e99f71923c67b287415b69ec32365c5",
    ),
    "variable/zoom_wave/base": (
        "35292cb8f288994166b0896bef527ccfa7f4698714c05d8d5e6970014e2be61e",
        "0020b12393f7dd4cf89bb4c4bbf3cd942ed5aa0de2abde665b3caffefdc751a7",
    ),
    "variable/zoom_wave/narrow": (
        "54dbc0402a84c1a231d5c0bdf997c91ed32ba347f7358c836887f03ffa84c6a9",
        "a39df6ddbe83086edd4664152946711a1b5a24a927837fd366218594215ce44a",
    ),
    "variable/zoom_wave/slow": (
        "adb234a4cf9f9efe3724f4bd64d2acf88cf9d6b18ae6fe01398795fa035ba102",
        "503a36b0d6d9b85cfa6e5518367e787f835571fbc02f9f44e09f96f2c6689561",
    ),
}
"""`grid/template/variant`: (render fingerprint, SHA-256 of the encoded frames)."""

MULTI_PIN = (
    "66dd4969d2ef370407f990c1195b946d63d56b770e7909e508ef3394f17b9669",
    "3ea6b3fca42f7ea4bbed6068c580331ce3649c6ef4c49f77f7b23fff7599fba7",
    "9ef5b7a162ca49079bb1a5261223b9ebcd399f8b7bb48463942ba4271861c6fb",
)
"""The multi-section plan: (render fingerprint, frames SHA-256, delivered `.xsq` SHA-256)."""

MULTI_SECTIONS = ("mirror_wings", "target_orbit", "finite_snap_hold", "fly_in_cascade")

GATED_PIN = (
    "ac4becde042f5b3346dab2eed6897664858e44e3c9a659dc8c82272d379be27e",
    "b971080b47c7c7b20e2466c76bfa187b6bb1872a5ec4ac6c316b9d0c614c96bd",
    "7f2d1e3bf22d121835f2c586bdea34718958dc234d6c2577fed66900fc4be14d",
)
"""The gated plan: (render fingerprint, frames SHA-256, delivered `.xsq` SHA-256). The
frames and `.xsq` hashes were rendered from `mh-last-with-legacy-renderer` (its job
carrying `mode: physical_v2`); the fingerprint is this tree's (re-recorded in C1.3, C1.4,
W2, W4 and its fix round)."""

GATED_ADMISSION = TemplateAdmission(
    admitted=("mirror_wings", "target_orbit", "fly_in_cascade", "finite_snap_hold"),
    admitted_presets={
        "mirror_wings": ("slow",),
        "target_orbit": ("narrow", "slow"),
        "fly_in_cascade": ("narrow", "slow"),
        "finite_snap_hold": ("narrow", "slow"),
    },
    effective_preset={
        "mirror_wings": "slow",
        "target_orbit": "narrow",
        "fly_in_cascade": None,
        "finite_snap_hold": None,
    },
    exclusions=(),
    preset_exclusions=(
        {"template_id": "mirror_wings", "preset_id": "narrow", "reason": "pinned exclusion"},
    ),
    entry_dips={},
    offer=m.untagged_offer(),
)
"""A gate result in which `mirror_wings`' `narrow` is not admitted and two templates
play a preset as their effective variant."""


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with m.family_catalog():
        yield


def _grid(name: str) -> BeatGrid:
    if name == "steady":
        return m.bars_grid(*([500.0] * 8))
    rng = random.Random(11)
    return m.bars_grid(*[rng.choice([430.0, 500.0, 580.0]) for _ in range(8)])


def _frames_sha256(frames: Sequence[EncodedFixtureFrame]) -> str:
    payload = [[f.fixture_id, f.time_ms, [list(c) for c in f.channels]] for f in frames]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def _render(
    sections: Sequence[tuple[str, int, int]],
    preset: str | None,
    grid: BeatGrid,
    output_path: Path | None = None,
) -> RenderingPipeline:
    zoom = any(template_id == "zoom_wave" for template_id, _, _ in sections)
    plan = m.sections_plan(*sections)
    if preset is not None:
        plan = plan.model_copy(
            update={"sections": [m.with_preset(s, preset) for s in plan.sections]}
        )
    pipeline = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=grid,
        fixture_group=(m.zoom_rig if zoom else m.family_rig)(HEADS),
        job_config=(m.zoom_job if zoom else m.family_job)(HEADS),
        output_path=output_path,
        media_file="silence.wav",
    )
    pipeline.render()
    return pipeline


def test_every_family_variant_is_pinned_on_both_grids() -> None:
    expected = {
        f"{grid}/{template_id}/{preset or 'base'}"
        for grid in ("steady", "variable")
        for template_id in m.CATALOG_IDS
        for preset in (None, *(p.preset_id for p in get_template(template_id).presets))
    }
    assert set(PINS) == expected


@pytest.mark.parametrize("case", sorted(PINS))
def test_family_variant_output_is_pinned(case: str) -> None:
    grid, template_id, variant = case.split("/")
    pipeline = _render([(template_id, 1, 8)], None if variant == "base" else variant, _grid(grid))

    assert (pipeline.fingerprint(), _frames_sha256(pipeline.frames)) == PINS[case]


def test_multi_section_output_and_delivered_xsq_are_pinned(tmp_path: Path) -> None:
    output_path = tmp_path / "song.xsq"
    pipeline = _render(
        [(template_id, 2 * i + 1, 2 * i + 2) for i, template_id in enumerate(MULTI_SECTIONS)],
        None,
        _grid("variable"),
        output_path,
    )

    assert (
        pipeline.fingerprint(),
        _frames_sha256(pipeline.frames),
        hashlib.sha256(output_path.read_bytes()).hexdigest(),
    ) == MULTI_PIN


def test_gated_render_with_dark_spans_and_a_fallback_is_pinned(tmp_path: Path) -> None:
    """A render under a gate result, over a dark span, with `reposition_fallback` set: a
    section naming a preset the gate left out, and one naming none, play their
    template's effective variant."""
    output_path = tmp_path / "song.xsq"
    plan = m.sections_plan(
        ("mirror_wings", 1, 2),
        ("target_orbit", 3, 4),
        ("fly_in_cascade", 5, 6),
        ("finite_snap_hold", 7, 8),
    )
    plan = plan.model_copy(
        update={
            "sections": [
                m.with_preset(plan.sections[0], "narrow"),
                *plan.sections[1:],
            ]
        }
    )
    job = m.family_job(HEADS)
    job = job.model_copy(
        update={
            "moving_heads": job.moving_heads.model_copy(
                update={"reposition_fallback": "preserve_aim"}
            )
        }
    )
    pipeline = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=_grid("variable"),
        fixture_group=m.family_rig(HEADS),
        job_config=job,
        output_path=output_path,
        media_file="silence.wav",
        admission=GATED_ADMISSION,
        dark_spans=((6000, 7500),),
    )
    pipeline.render()

    assert pipeline.render_record is not None
    assert pipeline.render_record["admission_effective_presets"] == {
        "mirror_wings": "slow",
        "target_orbit": "narrow",
    }
    assert pipeline.render_record["dark_spans"] == [[6000, 7500]]
    assert (
        pipeline.fingerprint(),
        _frames_sha256(pipeline.frames),
        hashlib.sha256(output_path.read_bytes()).hexdigest(),
    ) == GATED_PIN


INTENT_PIN = (
    "fb6ad90b90d1f293b490b075282350c1e0b00a4b9e5ed07215333ffc482b16a2",
    "ad91f4f2da8e0fc5bca0e07a7a9d9003d7880d59dee2499b30389be403e36d3b",
    "9968e9a4b0d5892d7891177fbdab9a0dca7d300d09998a946a5b908a51c17c46",
)
"""The song-intent plan on a tagged rig: (render fingerprint, frames SHA-256, delivered
`.xsq` SHA-256). Recorded in W4 (2026-11-17), when a section's colour and gobo started to
render; no earlier tree renders them, so these guard the new behaviour from here on."""


def test_section_colour_and_gobo_on_a_tagged_rig_are_pinned(tmp_path: Path) -> None:
    """Four sections on the steady grid and the tagged family rig: an explicit colour, a
    colour and a gobo, a palette role through a supplied macro palette over the overlay
    family, and an as-authored section after it; colour changes at lit boundaries dip
    dark before the section, where one fits."""
    output_path = tmp_path / "song.xsq"
    sections = [
        m.plan_section("s1", 1, 2, "mirror_wings", color="red"),
        m.plan_section("s2", 3, 4, "finite_snap_hold", color="blue", gobo="stars"),
        m.plan_section("s3", 5, 6, "masked_wheel_flick", color="PALETTE_PRIMARY"),
        m.plan_section("s4", 7, 8, "mirror_wings"),
    ]
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(sections=sections, overall_strategy=""),
        beat_grid=_grid("steady"),
        fixture_group=m.tagged_family_rig(HEADS),
        job_config=m.family_job(HEADS),
        output_path=output_path,
        media_file="silence.wav",
        palettes={"s3": section_palettes_of("spec.cosmic_night")},
    )
    pipeline.render()

    assert pipeline.render_record is not None
    assert [look["section_id"] for look in pipeline.render_record["section_looks"]] == [
        "s1",
        "s2",
        "s3",
        "s4",
    ]
    assert (
        pipeline.fingerprint(),
        _frames_sha256(pipeline.frames),
        hashlib.sha256(output_path.read_bytes()).hexdigest(),
    ) == INTENT_PIN


def section_palettes_of(palette_id: str) -> SectionPalette:
    return SectionPalette(
        palette_id=palette_id,
        stops=tuple(stop.hex[:7].upper() for stop in get_palette(palette_id).stops),
    )


FAST_INTENT_PIN = (
    "e710f7d09a10e3a2425ea788e5196b43cafa9af916d63bc150336c1ee7d43cc4",
    "2785d278f4341c611a0aaf60b9e22ee2e6e1accc8f70252442f7402bfd308a54",
)
"""The fast song-intent plan: (render fingerprint, frames SHA-256). Recorded in the W3/W4
review fix round, when a colour change that cannot dip before a lit boundary started to
turn in the section's first dark window, or else to keep the previous colour."""


def test_colour_changes_that_cannot_dip_at_170_bpm_are_pinned() -> None:
    """170 BPM on owner-like timings (close latency 20 ms, every wheel state settling in
    150 ms: a 180 ms change, more than half a beat): red, then blue over the overlay
    family (turned in its first mask), then red over `mirror_wings` (no dark moment: the
    heads keep blue), then green over `finite_snap_hold`."""
    payload = m.tagged_family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        profile = fixture["config"]["physical_profile"]
        profile["visibility"]["close_latency_ms"] = 20
        for channel in ("color", "gobo"):
            for state in profile["discrete"][channel]["states"].values():
                state["settle_ms"] = 150
    sections = [
        m.plan_section("s1", 1, 4, "mirror_wings", color="red"),
        m.plan_section("s2", 5, 8, "masked_wheel_flick", color="blue"),
        m.plan_section("s3", 9, 12, "mirror_wings", color="red"),
        m.plan_section("s4", 13, 16, "finite_snap_hold", color="white"),
    ]
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(sections=sections, overall_strategy=""),
        beat_grid=m.bars_grid(*([60_000 / 170] * 16)),
        fixture_group=FixtureGroup.model_validate(payload),
        job_config=m.family_job(HEADS),
        media_file="silence.wav",
    )
    pipeline.render()

    assert pipeline.render_record is not None
    outcomes = [
        sorted(
            {
                next(k for k in ("dark_dip", "deferred", "kept_previous") if k in b)
                for b in look.get("boundaries", [])
            }
        )
        for look in pipeline.render_record["section_looks"]
    ]
    assert outcomes == [[], ["deferred"], ["kept_previous"], []]
    assert (pipeline.fingerprint(), _frames_sha256(pipeline.frames)) == FAST_INTENT_PIN
