"""Builtin palette definitions.

Registers core and specialty palettes with the global registry.
"""

from twinklr.core.sequencer.theming.catalog import PALETTE_REGISTRY
from twinklr.core.sequencer.theming.models import ColorStop, PaletteDefinition


def _register_palettes() -> None:
    """Register all builtin palettes."""
    # -------------------------
    # Core show palettes
    # -------------------------
    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="core.rgb_primary",
            title="RGB Primary",
            description="Classic bright RGB primaries; clean high contrast.",
            stops=[
                ColorStop(hex="#FF1744", name="red"),
                ColorStop(hex="#00E676", name="green"),
                ColorStop(hex="#2979FF", name="blue"),
                ColorStop(hex="#FFFFFF", name="white", weight=0.6),
            ],
            usage_hint="bright RGB primaries with clean white highlights",
            background_hex="#070A12",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="core.rainbow_bright",
            title="Rainbow Bright",
            description="High-saturation rainbow sweep; good for spirals and waves.",
            stops=[
                ColorStop(hex="#FF1744", name="red"),
                ColorStop(hex="#FF9100", name="orange"),
                ColorStop(hex="#FFD600", name="yellow"),
                ColorStop(hex="#00E676", name="green"),
                ColorStop(hex="#00E5FF", name="cyan"),
                ColorStop(hex="#2979FF", name="blue"),
                ColorStop(hex="#D500F9", name="purple"),
            ],
            usage_hint="high-saturation rainbow gradients, crisp and clean",
            background_hex="#060814",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="core.ice_neon",
            title="Ice Neon",
            description="Cold neon cyan/blue with white; great for icy/cosmic/cyber.",
            stops=[
                ColorStop(hex="#00E5FF", name="electric_cyan"),
                ColorStop(hex="#2979FF", name="neon_blue"),
                ColorStop(hex="#7C4DFF", name="violet_pop", weight=0.6),
                ColorStop(hex="#FFFFFF", name="white"),
            ],
            usage_hint="cold neon cyan/blue with bright white highlights",
            background_hex="#050914",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="core.magma",
            title="Magma",
            description="Hot reds/oranges with bright yellow; bold and punchy.",
            stops=[
                ColorStop(hex="#FF1744", name="hot_red"),
                ColorStop(hex="#FF3D00", name="molten_orange"),
                ColorStop(hex="#FF9100", name="amber"),
                ColorStop(hex="#FFD600", name="flare_yellow"),
            ],
            usage_hint="hot reds/oranges with bright yellow highlights",
            background_hex="#120407",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="core.uv_party",
            title="UV Party",
            description="Purple/magenta/cyan pop; great for hype / arcade / retro.",
            stops=[
                ColorStop(hex="#D500F9", name="magenta"),
                ColorStop(hex="#7C4DFF", name="purple"),
                ColorStop(hex="#00E5FF", name="cyan"),
                ColorStop(hex="#FFFFFF", name="white", weight=0.5),
            ],
            usage_hint="purple/magenta with cyan accents and crisp white pops",
            background_hex="#090516",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="core.gold_warm",
            title="Gold Warm",
            description="Warm gold/amber with creamy whites; cozy without being 'Santa'.",
            stops=[
                ColorStop(hex="#FFB300", name="gold"),
                ColorStop(hex="#FF9100", name="amber"),
                ColorStop(hex="#F5F1E8", name="warm_white"),
                ColorStop(hex="#FFFFFF", name="white", weight=0.4),
            ],
            usage_hint="warm gold/amber with warm white highlights",
            background_hex="#0B0C12",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="core.mono_cool",
            title="Mono Cool",
            description="Monochrome cool whites and blues; clean and minimal.",
            stops=[
                ColorStop(hex="#FFFFFF", name="white"),
                ColorStop(hex="#B3E5FC", name="ice_light"),
                ColorStop(hex="#2979FF", name="blue_accent", weight=0.4),
            ],
            usage_hint="cool whites with a subtle blue accent",
            background_hex="#070A12",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="core.mono_warm",
            title="Mono Warm",
            description="Warm whites/cream with amber accents; minimal and readable.",
            stops=[
                ColorStop(hex="#FFFFFF", name="white"),
                ColorStop(hex="#F5F1E8", name="cream"),
                ColorStop(hex="#FFB300", name="amber_accent", weight=0.4),
            ],
            usage_hint="warm whites/cream with light amber accents",
            background_hex="#08070A",
        )
    )

    # -------------------------
    # Specialty palettes
    # -------------------------
    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="spec.cyber_green",
            title="Cyber Green",
            description="Green-on-dark cyber vibe; pairs well with grids and rays.",
            stops=[
                ColorStop(hex="#00E676", name="neon_green"),
                ColorStop(hex="#AEEA00", name="acid_lime", weight=0.6),
                ColorStop(hex="#FFFFFF", name="white", weight=0.4),
            ],
            usage_hint="neon green with acid lime and crisp white highlights",
            background_hex="#030B07",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="spec.fire_ice",
            title="Fire & Ice",
            description="Split warm/cool contrast for dramatic sections.",
            stops=[
                ColorStop(hex="#FF1744", name="hot_red"),
                ColorStop(hex="#FF9100", name="amber"),
                ColorStop(hex="#00E5FF", name="cyan"),
                ColorStop(hex="#2979FF", name="blue"),
                ColorStop(hex="#FFFFFF", name="white", weight=0.5),
            ],
            usage_hint="strong warm/cool contrast: red/orange vs cyan/blue with white pops",
            background_hex="#060612",
        )
    )


# Auto-register on import
_register_palettes()
