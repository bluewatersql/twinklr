"""Viseme mapping for phonemes (Phase 6).

Maps ARPAbet phonemes to viseme mouth shapes for lip-sync animation.

Constants:
    PHONEME_TO_VISEME: Phoneme to viseme mapping dict

Functions:
    phoneme_to_viseme: Convert phoneme to viseme code
    merge_adjacent_visemes: Merge adjacent identical visemes
    apply_min_hold: Apply minimum hold duration to visemes

Viseme Codes:
    A - Open mouth (ah, aa)
    E - Slightly open (eh, ae)
    I - Smile (ee, ih)
    O - Rounded (oh, oo)
    U - Pucker (oo, uw)
    BMP - Lips together (b, m, p)
    FV - Bottom lip to teeth (f, v)
    TH - Tongue between teeth
    TD - Tongue to alveolar ridge (t, d, s, z)
    KG - Back of tongue (k, g)
    CHJ - Palatal (ch, j, sh, zh)
    L - Tongue to roof
    R - R sound
    N - Nasal
    W - Rounded lips
    Y - Y sound
    H - Aspirated
    REST - Silence/neutral

Example:
    >>> phoneme_to_viseme("AH0")
    'A'
    >>> phoneme_to_viseme("B")
    'BMP'
"""

from blinkb0t.core.audio.models.phonemes import VisemeEvent

# ARPAbet phoneme to viseme mapping
# Based on standard lip-sync viseme codes
PHONEME_TO_VISEME: dict[str, str] = {
    # Vowels
    "AA": "A",  # father
    "AE": "A",  # cat
    "AH": "A",  # cut
    "AO": "O",  # caught
    "AW": "O",  # cow
    "AY": "A",  # ride
    "EH": "E",  # bed
    "ER": "R",  # bird
    "EY": "E",  # bait
    "IH": "I",  # bit
    "IY": "I",  # beat
    "OW": "O",  # boat
    "OY": "O",  # boy
    "UH": "U",  # book
    "UW": "U",  # boot
    # Consonants - Bilabials
    "P": "BMP",  # put
    "B": "BMP",  # but
    "M": "BMP",  # mat
    # Consonants - Labiodentals
    "F": "FV",  # fat
    "V": "FV",  # vat
    # Consonants - Dental
    "TH": "TH",  # thick
    "DH": "TH",  # that
    # Consonants - Alveolar
    "T": "TD",  # tip
    "D": "TD",  # dip
    "S": "TD",  # sip
    "Z": "TD",  # zip
    "N": "N",   # nip
    # Consonants - Velar
    "K": "KG",  # kite
    "G": "KG",  # gate
    "NG": "KG", # sing
    # Consonants - Palatal
    "CH": "CHJ",  # church
    "JH": "CHJ",  # judge
    "SH": "CHJ",  # ship
    "ZH": "CHJ",  # measure
    "Y": "Y",     # yes
    # Consonants - Liquid
    "L": "L",  # lip
    "R": "R",  # rip
    # Consonants - Glide
    "W": "W",  # wet
    # Consonants - Glottal
    "HH": "H",  # hit
}


def phoneme_to_viseme(phoneme: str) -> str:
    """Convert phoneme to viseme code.

    Strips stress markers before lookup.

    Args:
        phoneme: Phoneme text (ARPAbet format, e.g., "AH0", "B")

    Returns:
        Viseme code (e.g., "A", "BMP")

    Example:
        >>> phoneme_to_viseme("AH0")
        'A'
        >>> phoneme_to_viseme("B")
        'BMP'
        >>> phoneme_to_viseme("UNKNOWN")
        'REST'
    """
    # Strip stress markers (0, 1, 2) and convert to uppercase
    normalized = "".join(ch for ch in phoneme.upper() if not ch.isdigit())

    # Lookup viseme
    return PHONEME_TO_VISEME.get(normalized, "REST")


def merge_adjacent_visemes(
    events: list[VisemeEvent],
    *,
    max_gap_ms: int = 20,
) -> list[VisemeEvent]:
    """Merge adjacent identical visemes.

    Adjacent visemes with the same code are merged into a single event.
    Small gaps (< max_gap_ms) between identical visemes are also merged.

    Args:
        events: List of viseme events
        max_gap_ms: Maximum gap to merge across (default: 20ms)

    Returns:
        List of merged viseme events

    Example:
        >>> events = [
        ...     VisemeEvent(viseme="A", start_ms=0, end_ms=100),
        ...     VisemeEvent(viseme="A", start_ms=100, end_ms=200),
        ... ]
        >>> merged = merge_adjacent_visemes(events)
        >>> len(merged)
        1
        >>> merged[0].end_ms
        200
    """
    if not events:
        return []

    # Sort by start time
    sorted_events = sorted(events, key=lambda e: e.start_ms)

    merged: list[VisemeEvent] = []

    for event in sorted_events:
        if not merged:
            # First event
            merged.append(event)
        else:
            prev = merged[-1]

            # Check if same viseme and adjacent/near
            gap = event.start_ms - prev.end_ms
            if prev.viseme == event.viseme and gap <= max_gap_ms:
                # Merge: extend previous event to cover this one
                merged[-1] = VisemeEvent(
                    viseme=prev.viseme,
                    start_ms=prev.start_ms,
                    end_ms=max(prev.end_ms, event.end_ms),
                    confidence=min(prev.confidence, event.confidence),
                )
            else:
                # Different viseme or too far apart: add as new
                merged.append(event)

    return merged


def apply_min_hold(
    events: list[VisemeEvent],
    *,
    min_hold_ms: int = 50,
) -> list[VisemeEvent]:
    """Apply minimum hold duration to visemes.

    Ensures each viseme is held for at least min_hold_ms.
    Adjusts subsequent events to maintain timing.

    Args:
        events: List of viseme events
        min_hold_ms: Minimum hold duration in milliseconds

    Returns:
        List of events with min hold applied

    Example:
        >>> events = [VisemeEvent(viseme="A", start_ms=0, end_ms=30)]
        >>> result = apply_min_hold(events, min_hold_ms=50)
        >>> result[0].end_ms
        50
    """
    if not events or min_hold_ms <= 0:
        return events

    result: list[VisemeEvent] = []
    current_time = 0

    for event in events:
        # Adjust start time if previous event was extended
        start_ms = max(event.start_ms, current_time)
        duration = event.end_ms - event.start_ms

        if duration < min_hold_ms:
            # Extend to min hold
            end_ms = start_ms + min_hold_ms
        else:
            # Keep original duration from adjusted start
            end_ms = start_ms + duration

        result.append(
            VisemeEvent(
                viseme=event.viseme,
                start_ms=start_ms,
                end_ms=end_ms,
                confidence=event.confidence,
            )
        )

        # Track where next event should start
        current_time = end_ms

    return result
