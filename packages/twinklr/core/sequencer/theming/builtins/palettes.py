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

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="core.christmas_traditional",
            title="Christmas Traditional",
            description="Classic red/green with warm white; high contrast and unmistakably Christmas.",
            stops=[
                ColorStop(hex="#E53935", name="christmas_red"),
                ColorStop(hex="#43A047", name="christmas_green"),
                ColorStop(hex="#F5F1E8", name="warm_white", weight=0.8),
                ColorStop(hex="#FFFFFF", name="white", weight=0.4),
            ],
            usage_hint="classic red/green with warm white highlights",
            background_hex="#070A12",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="core.peppermint",
            title="Peppermint",
            description="Candy cane red/white with subtle cool shadow.",
            stops=[
                ColorStop(hex="#FF1744", name="peppermint_red"),
                ColorStop(hex="#FFFFFF", name="white", weight=1.0),
                ColorStop(hex="#B3E5FC", name="cool_shadow", weight=0.35),
            ],
            usage_hint="red/white stripes with light cool shading",
            background_hex="#060814",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="spec.eerie_slime",
            title="Eerie Slime",
            description="Eerie neon green + purple on dark; spooky without gore.",
            stops=[
                ColorStop(hex="#00E676", name="neon_green"),
                ColorStop(hex="#AEEA00", name="acid_lime", weight=0.6),
                ColorStop(hex="#7C4DFF", name="deep_purple", weight=0.55),
                ColorStop(hex="#FFFFFF", name="white", weight=0.35),
            ],
            usage_hint="spooky green/purple contrast with crisp pops",
            background_hex="#04030B",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="spec.cosmic_night",
            title="Cosmic Night",
            description="Deep space blues with magenta/cyan glows; starfield-friendly.",
            stops=[
                ColorStop(hex="#0D47A1", name="deep_blue"),
                ColorStop(hex="#2979FF", name="neon_blue", weight=0.7),
                ColorStop(hex="#00E5FF", name="cyan_glow", weight=0.6),
                ColorStop(hex="#D500F9", name="magenta_pop", weight=0.45),
                ColorStop(hex="#FFFFFF", name="white", weight=0.35),
            ],
            usage_hint="deep space base with cyan/magenta glow accents",
            background_hex="#040516",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="spec.arcade_cabinet",
            title="Arcade Cabinet",
            description="Punchy arcade colors; high saturation, clean separations.",
            stops=[
                ColorStop(hex="#FF1744", name="hot_red"),
                ColorStop(hex="#FFD600", name="arcade_yellow"),
                ColorStop(hex="#00E676", name="arcade_green"),
                ColorStop(hex="#00E5FF", name="arcade_cyan"),
                ColorStop(hex="#D500F9", name="arcade_magenta"),
                ColorStop(hex="#FFFFFF", name="white", weight=0.35),
            ],
            usage_hint="bright arcade palette for pixel/block motifs",
            background_hex="#070312",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="spec.futuristic_teal",
            title="Futuristic Teal",
            description="Clean futuristic teal/blue with white; sleek and readable.",
            stops=[
                ColorStop(hex="#00E5FF", name="teal"),
                ColorStop(hex="#00B0FF", name="sky_blue", weight=0.75),
                ColorStop(hex="#2979FF", name="blue", weight=0.6),
                ColorStop(hex="#FFFFFF", name="white", weight=0.45),
            ],
            usage_hint="sleek teal/blue gradients with crisp white accents",
            background_hex="#030A12",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="spec.gritty_embers",
            title="Gritty Embers",
            description="Dark ember warmth; gritty without noisy textures.",
            stops=[
                ColorStop(hex="#B71C1C", name="deep_red"),
                ColorStop(hex="#FF3D00", name="ember_orange", weight=0.75),
                ColorStop(hex="#FF9100", name="amber", weight=0.6),
                ColorStop(hex="#F5F1E8", name="ash_white", weight=0.4),
            ],
            usage_hint="dark warm embers with restrained highlights",
            background_hex="#0B0608",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="spec.dreamy_pastel",
            title="Dreamy Pastel",
            description="Soft dreamy pastels with enough contrast to read on LEDs.",
            stops=[
                ColorStop(hex="#B39DDB", name="lavender"),
                ColorStop(hex="#80DEEA", name="aqua"),
                ColorStop(hex="#FFCCBC", name="peach", weight=0.7),
                ColorStop(hex="#FFFFFF", name="white", weight=0.5),
            ],
            usage_hint="dreamy pastel blend with white lift for readability",
            background_hex="#070A12",
        )
    )

    PALETTE_REGISTRY.register(
        PaletteDefinition(
            palette_id="spec.holo_prism",
            title="Holo Prism",
            description="Holographic-ish rainbow with controlled stops (not muddy).",
            stops=[
                ColorStop(hex="#00E5FF", name="cyan"),
                ColorStop(hex="#7C4DFF", name="violet"),
                ColorStop(hex="#D500F9", name="magenta"),
                ColorStop(hex="#FFD600", name="prism_yellow", weight=0.55),
                ColorStop(hex="#FFFFFF", name="white", weight=0.4),
            ],
            usage_hint="prismatic glow palette; keep shapes large and clean",
            background_hex="#050914",
        )
    )


# Auto-register on import
_register_palettes()
