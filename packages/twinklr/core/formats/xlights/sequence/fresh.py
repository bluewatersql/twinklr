"""The one fresh-`.xsq` emitter.

Twinklr used to build a from-nothing sequence in two places that disagreed with each
other (P5-M3): the moving-heads exporter stamped version 2024.10 with a 50 ms grid,
the display renderer stamped version 2024.01 with a 20 ms grid, and *both* wrote
`media_file=""` — which Twinklr's own parser rejects as a fatal error
(`parser.py`, "Missing required field: mediaFile/MediaFile"). Since P1P-T11 retired the
template-merge branch, generate-fresh is the only way a `.xsq` is produced, so the
stamp and the grid are the product's output contract and there is exactly one of each
here.

Whether xLights 2026.15 accepts these artifacts is answered empirically by P1P-T12, not
by this module.
"""

from __future__ import annotations

from pathlib import Path

from twinklr.core.formats.xlights.sequence.models.xsq import SequenceHead, XSequence

XLIGHTS_VERSION_STAMP = "2026.15"
"""Version written into every sequence Twinklr emits.

xLights warns (does not reject) on pre-2020 stamps, a boundary introduced in 2026.04
that can ratchet upward, so the stamp tracks the version the project targets rather
than the 2024.10/2024.01 pair it inherited. Updating it costs nothing; P1P-T12 confirms
acceptance against a real xLights.
"""

EFFECT_GRID_MS = 20
"""Grid used only for emitted effect boundaries; timing tracks remain source-exact."""

SEQUENCE_TIMING = f"{EFFECT_GRID_MS} ms"
"""The single sequence timing grid.

The owner selected 20 ms for P3-T6. Only effect endpoints are snapped; timing-track
markers and sequence duration remain unchanged.
"""

DEFAULT_AUTHOR = "Twinklr"

PLACEHOLDER_MEDIA_FILE = "twinklr-media-not-set.mp3"
"""Last-resort `mediaFile` for callers with no audio path.

`mediaFile` must be non-empty or the file is unopenable, so a caller that genuinely
does not know the media names this placeholder and the user repoints it in xLights.
Anything that renders a real song passes the real audio path instead.
"""


def resolve_media_file(audio_path: str | Path | None) -> str:
    """Return a non-empty `mediaFile` value for `audio_path`.

    Args:
        audio_path: Audio file the sequence is choreographed against, if known.

    Returns:
        The audio file name, or `PLACEHOLDER_MEDIA_FILE` when there is nothing to name.
    """
    if audio_path is None:
        return PLACEHOLDER_MEDIA_FILE
    name = Path(str(audio_path)).name.strip()
    return name or PLACEHOLDER_MEDIA_FILE


def build_fresh_sequence(
    *,
    media_file: str,
    duration_ms: int,
    song: str = "",
    artist: str = "",
    author: str = DEFAULT_AUTHOR,
) -> XSequence:
    """Build a self-contained `XSequence` with no user document involved.

    Args:
        media_file: Audio file the sequence plays against. Must be non-empty.
        duration_ms: Sequence duration in milliseconds.
        song: Song title for the head, when known.
        artist: Artist for the head, when known.
        author: Author stamp.

    Returns:
        An `XSequence` carrying only a head — callers add timing tracks and effects.

    Raises:
        ValueError: If `media_file` is empty, which would make the emitted file
            unopenable and unparseable by Twinklr's own parser.
    """
    if not media_file.strip():
        raise ValueError(
            "media_file must be non-empty: xLights and XSQParser both treat a missing "
            "mediaFile as fatal. Use resolve_media_file() if the audio path is unknown."
        )

    return XSequence(
        document_origin="fresh",
        head=SequenceHead(
            version=XLIGHTS_VERSION_STAMP,
            author=author,
            song=song,
            artist=artist,
            sequence_timing=SEQUENCE_TIMING,
            media_file=media_file,
            sequence_duration_ms=duration_ms,
        ),
    )
