"""Bootstrap template pack for GroupPlanner - Traditional Holiday (v1).

This module provides 12 group plan templates for traditional Christmas displays,
following the factory pattern with @register_template decorators.
"""

from __future__ import annotations

from twinklr.core.agents.taxonomy import (
    AssetSlotType,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    LayerRole,
    MotionVerb,
    ProjectionIntent,
    WarpHint,
)
from twinklr.core.sequencer.templates.group_templates.library import (
    register_template,
)
from twinklr.core.sequencer.templates.group_templates.models import (
    AssetSlot,
    AssetSlotDefaults,
    BackgroundMode,
    GroupConstraints,
    GroupPlanTemplate,
    LayerRecipe,
    MatrixAspect,
    ProjectionParams,
    ProjectionSpec,
)


@register_template(aliases=["Cozy Village", "cozy village bg"])
def gtpl_scene_cozy_village_bg() -> GroupPlanTemplate:
    """Scene background with cozy village and snowfall overlay."""
    return GroupPlanTemplate(
        template_id="gtpl_scene_cozy_village_bg",
        name="Scene Background — Cozy Village Night",
        description="Section background plate with subtle snowfall + window glow accents.",
        template_type=GroupTemplateType.SECTION_BACKGROUND,
        visual_intent=GroupVisualIntent.SCENE,
        tags=[
            "holiday_christmas_traditional",
            "scene",
            "background",
            "cozy",
            "winter_scene",
        ],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        constraints=GroupConstraints(),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BASE,
                motifs=["cozy village", "snowy rooftops", "decorated tree"],
                visual_intent=GroupVisualIntent.SCENE,
                motion=[MotionVerb.NONE],
                density=0.35,
                contrast=0.75,
                color_mode=ColorMode.WARM,
                notes="Keep large shapes; avoid fine brick detail.",
            ),
            LayerRecipe(
                layer=LayerRole.RHYTHM,
                motifs=["snowfall overlay"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.FALL, MotionVerb.DRIFT],
                density=0.25,
                contrast=0.65,
                color_mode=ColorMode.COOL,
                notes="Procedural snow overlay is ideal.",
            ),
        ],
        asset_slots=[
            AssetSlot(
                slot_id="bg_plate",
                slot_type=AssetSlotType.BACKGROUND_PLATE,
                required=True,
                preferred_tags=[
                    "holiday_christmas_traditional",
                    "winter_scene",
                    "background",
                    "storybook",
                    "matrix_safe",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.OPAQUE,
                    aspect=MatrixAspect.WIDE_2_1,
                    base_size=256,
                ),
            )
        ],
    )


@register_template(aliases=["Santa Center", "santa feature"])
def gtpl_feature_santa_center() -> GroupPlanTemplate:
    """Santa cutout hero moment with twinkle accents."""
    return GroupPlanTemplate(
        template_id="gtpl_feature_santa_center",
        name="Feature — Santa Center Moment",
        description="Santa cutout hero moment with gentle twinkle accents.",
        template_type=GroupTemplateType.SECTION_FEATURE,
        visual_intent=GroupVisualIntent.ICON,
        tags=["holiday_christmas_traditional", "santa", "feature", "icon"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        constraints=GroupConstraints(),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BASE,
                motifs=["night sky gradient"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.NONE],
                density=0.15,
                contrast=0.6,
                color_mode=ColorMode.COOL,
            ),
            LayerRecipe(
                layer=LayerRole.HIGHLIGHT,
                motifs=["santa cutout"],
                visual_intent=GroupVisualIntent.ICON,
                motion=[MotionVerb.NONE],
                density=0.5,
                contrast=0.9,
                color_mode=ColorMode.TRADITIONAL,
                notes="Big silhouette, minimal interior detail.",
            ),
            LayerRecipe(
                layer=LayerRole.RHYTHM,
                motifs=["twinkle edge accents"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.TWINKLE],
                density=0.2,
                contrast=0.85,
                color_mode=ColorMode.TRADITIONAL,
            ),
        ],
        asset_slots=[
            AssetSlot(
                slot_id="santa_cutout",
                slot_type=AssetSlotType.ICON_CUTOUT,
                required=True,
                preferred_tags=[
                    "holiday_christmas_traditional",
                    "santa",
                    "character",
                    "cutout",
                    "transparent_background",
                    "matrix_safe",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.TRANSPARENT,
                    aspect=MatrixAspect.SQUARE_1_1,
                    base_size=256,
                ),
            ),
            AssetSlot(
                slot_id="bg_plate",
                slot_type=AssetSlotType.BACKGROUND_PLATE,
                required=False,
                preferred_tags=[
                    "holiday_christmas_traditional",
                    "night_sky",
                    "background",
                    "matrix_safe",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.OPAQUE,
                    aspect=MatrixAspect.SQUARE_1_1,
                    base_size=256,
                ),
            ),
        ],
    )


@register_template(aliases=["Tree Radial Burst", "polar radial"])
def gtpl_tree_polar_radial_burst() -> GroupPlanTemplate:
    """Seam-safe radial burst tile for cone mega-tree polar mapping."""
    return GroupPlanTemplate(
        template_id="gtpl_tree_polar_radial_burst",
        name="Tree Polar Pattern Loop — Radial Burst",
        description="Seam-safe radial burst tile for cone mega-tree polar mapping.",
        template_type=GroupTemplateType.PATTERN_LOOP,
        visual_intent=GroupVisualIntent.PATTERN,
        tags=[
            "holiday_christmas_traditional",
            "tree_polar",
            "radial",
            "pattern",
            "seam_safe",
        ],
        projection=ProjectionSpec(
            intent=ProjectionIntent.TREE_POLAR,
            params=ProjectionParams(seam_safe=True, center_x=0.5, center_y=0.5),
            warp_hints=[WarpHint.RADIAL_WARP_OK, WarpHint.CENTER_ANCHOR],
        ),
        constraints=GroupConstraints(seam_safe_required=True, avoid_edges_for_subject=True),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BASE,
                motifs=["radial starburst", "ornament accents"],
                visual_intent=GroupVisualIntent.PATTERN,
                motion=[MotionVerb.NONE],
                density=0.5,
                contrast=0.9,
                color_mode=ColorMode.TRADITIONAL,
                notes="Seam safe tile. No critical elements on left/right edges.",
            ),
            LayerRecipe(
                layer=LayerRole.RHYTHM,
                motifs=["phase shimmer", "spoke twinkles"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.TWINKLE, MotionVerb.PULSE],
                density=0.25,
                contrast=0.85,
                color_mode=ColorMode.TRADITIONAL,
            ),
        ],
        asset_slots=[
            AssetSlot(
                slot_id="pattern_tile",
                slot_type=AssetSlotType.PATTERN_TILE,
                required=True,
                preferred_tags=[
                    "holiday_christmas_traditional",
                    "tree_polar",
                    "radial",
                    "pattern",
                    "seam_safe",
                    "matrix_safe",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.OPAQUE,
                    aspect=MatrixAspect.WIDE_2_1,
                    base_size=256,
                    seam_safe=True,
                ),
            )
        ],
        extras={"tile_mode": "seamless_horizontal", "preferred_animation": "rotate_or_phase"},
    )


@register_template(aliases=["Candy Cane Spiral", "tree spiral candy"])
def gtpl_tree_spiral_candy_cane() -> GroupPlanTemplate:
    """Seam-safe candy cane spiral for tree spiral bias mapping."""
    return GroupPlanTemplate(
        template_id="gtpl_tree_spiral_candy_cane",
        name="Tree Spiral Pattern Loop — Candy Cane",
        description="Seam-safe spiral candy cane tile designed for spiral bias mapping.",
        template_type=GroupTemplateType.PATTERN_LOOP,
        visual_intent=GroupVisualIntent.PATTERN,
        tags=[
            "holiday_christmas_traditional",
            "tree_spiral",
            "candy_cane",
            "pattern",
            "seam_safe",
        ],
        projection=ProjectionSpec(
            intent=ProjectionIntent.TREE_SPIRAL_BIAS,
            params=ProjectionParams(seam_safe=True, center_x=0.5, center_y=0.5),
            warp_hints=[WarpHint.RADIAL_WARP_OK],
        ),
        constraints=GroupConstraints(seam_safe_required=True),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BASE,
                motifs=["candy cane spiral stripes"],
                visual_intent=GroupVisualIntent.PATTERN,
                motion=[MotionVerb.SPIRAL],
                density=0.6,
                contrast=0.95,
                color_mode=ColorMode.TRADITIONAL,
                notes="Crisp stripes. No noisy textures.",
            ),
            LayerRecipe(
                layer=LayerRole.HIGHLIGHT,
                motifs=["beat pulse on stripes"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.2,
                contrast=0.9,
                color_mode=ColorMode.TRADITIONAL,
            ),
        ],
        asset_slots=[
            AssetSlot(
                slot_id="pattern_tile",
                slot_type=AssetSlotType.PATTERN_TILE,
                required=True,
                preferred_tags=[
                    "holiday_christmas_traditional",
                    "candy_cane",
                    "tree_spiral",
                    "pattern",
                    "seam_safe",
                    "high_contrast",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.OPAQUE,
                    aspect=MatrixAspect.WIDE_2_1,
                    base_size=256,
                    seam_safe=True,
                ),
            )
        ],
        extras={"tile_mode": "seamless_horizontal"},
    )


@register_template(aliases=["Wreath Twinkle", "wreath accent"])
def gtpl_accent_wreath_twinkle() -> GroupPlanTemplate:
    """Accent moment with wreath cutout and twinkle overlay."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_wreath_twinkle",
        name="Accent — Wreath + Twinkle",
        description="Accent moment: wreath cutout with twinkle overlay.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ICON,
        tags=["holiday_christmas_traditional", "wreath", "accent", "twinkle"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        constraints=GroupConstraints(),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.HIGHLIGHT,
                motifs=["wreath cutout", "red bow"],
                visual_intent=GroupVisualIntent.ICON,
                motion=[MotionVerb.NONE],
                density=0.4,
                contrast=0.9,
                color_mode=ColorMode.TRADITIONAL,
            ),
            LayerRecipe(
                layer=LayerRole.RHYTHM,
                motifs=["twinkle overlay"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.TWINKLE],
                density=0.2,
                contrast=0.85,
                color_mode=ColorMode.TRADITIONAL,
            ),
        ],
        asset_slots=[
            AssetSlot(
                slot_id="wreath_cutout",
                slot_type=AssetSlotType.ICON_CUTOUT,
                required=True,
                preferred_tags=[
                    "holiday_christmas_traditional",
                    "wreath",
                    "cutout",
                    "transparent_background",
                    "matrix_safe",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.TRANSPARENT,
                    aspect=MatrixAspect.SQUARE_1_1,
                    base_size=256,
                ),
            )
        ],
    )


@register_template(aliases=["Snowflake Drift", "snowflake transition"])
def gtpl_transition_snowflake_drift() -> GroupPlanTemplate:
    """Simple snowflake drift transition with directional wipe."""
    return GroupPlanTemplate(
        template_id="gtpl_transition_snowflake_drift",
        name="Transition — Snowflake Drift Wipe",
        description="Simple transition: snowflake drift with directional wipe/sweep.",
        template_type=GroupTemplateType.TRANSITION,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["holiday_winter_generic", "snowflakes", "transition", "drift", "wipe"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        constraints=GroupConstraints(),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BASE,
                motifs=["dark winter sky"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.NONE],
                density=0.1,
                contrast=0.6,
                color_mode=ColorMode.COOL,
            ),
            LayerRecipe(
                layer=LayerRole.RHYTHM,
                motifs=["snowflakes"],
                visual_intent=GroupVisualIntent.PATTERN,
                motion=[MotionVerb.DRIFT, MotionVerb.WIPE],
                density=0.3,
                contrast=0.8,
                color_mode=ColorMode.COOL,
                notes="Prefer procedural overlay; optional pattern tile if needed.",
            ),
        ],
        asset_slots=[
            AssetSlot(
                slot_id="snowflake_tile_optional",
                slot_type=AssetSlotType.PATTERN_TILE,
                required=False,
                preferred_tags=[
                    "holiday_winter_generic",
                    "snowflakes",
                    "pattern",
                    "matrix_safe",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.TRANSPARENT,
                    aspect=MatrixAspect.SQUARE_1_1,
                    base_size=256,
                    seam_safe=False,
                ),
            )
        ],
        extras={"transition_style": "wipe_lr", "duration_bars": 2},
    )


@register_template(aliases=["Ornament Scatter", "ornaments pattern"])
def gtpl_pattern_ornament_scatter() -> GroupPlanTemplate:
    """Scattered ornament pattern with twinkling highlights."""
    return GroupPlanTemplate(
        template_id="gtpl_pattern_ornament_scatter",
        name="Pattern Loop — Ornament Scatter",
        description="Scattered ornaments with gentle twinkle accents.",
        template_type=GroupTemplateType.PATTERN_LOOP,
        visual_intent=GroupVisualIntent.PATTERN,
        tags=[
            "holiday_christmas_traditional",
            "ornaments",
            "pattern",
            "scattered",
        ],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        constraints=GroupConstraints(),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BASE,
                motifs=["scattered ornaments", "varied sizes"],
                visual_intent=GroupVisualIntent.PATTERN,
                motion=[MotionVerb.NONE],
                density=0.4,
                contrast=0.85,
                color_mode=ColorMode.TRADITIONAL,
                notes="Mix of red, green, gold ornaments.",
            ),
            LayerRecipe(
                layer=LayerRole.RHYTHM,
                motifs=["sparkle highlights"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.TWINKLE],
                density=0.15,
                contrast=0.9,
                color_mode=ColorMode.TRADITIONAL,
            ),
        ],
        asset_slots=[
            AssetSlot(
                slot_id="ornament_pattern",
                slot_type=AssetSlotType.PATTERN_TILE,
                required=False,
                preferred_tags=[
                    "holiday_christmas_traditional",
                    "ornaments",
                    "pattern",
                    "matrix_safe",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.OPAQUE,
                    aspect=MatrixAspect.SQUARE_1_1,
                    base_size=256,
                ),
            )
        ],
    )


@register_template(aliases=["Reindeer Scene", "reindeer feature"])
def gtpl_feature_reindeer_silhouette() -> GroupPlanTemplate:
    """Reindeer silhouette feature with moon backdrop."""
    return GroupPlanTemplate(
        template_id="gtpl_feature_reindeer_silhouette",
        name="Feature — Reindeer Silhouette",
        description="Reindeer silhouette against moon backdrop.",
        template_type=GroupTemplateType.SECTION_FEATURE,
        visual_intent=GroupVisualIntent.ICON,
        tags=["holiday_christmas_traditional", "reindeer", "feature", "silhouette"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        constraints=GroupConstraints(),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BASE,
                motifs=["moon backdrop", "night sky"],
                visual_intent=GroupVisualIntent.SCENE,
                motion=[MotionVerb.NONE],
                density=0.3,
                contrast=0.7,
                color_mode=ColorMode.COOL,
            ),
            LayerRecipe(
                layer=LayerRole.HIGHLIGHT,
                motifs=["reindeer silhouette"],
                visual_intent=GroupVisualIntent.ICON,
                motion=[MotionVerb.NONE],
                density=0.5,
                contrast=0.95,
                color_mode=ColorMode.MONO,
                notes="Strong silhouette, minimal detail.",
            ),
        ],
        asset_slots=[
            AssetSlot(
                slot_id="reindeer_cutout",
                slot_type=AssetSlotType.ICON_CUTOUT,
                required=True,
                preferred_tags=[
                    "holiday_christmas_traditional",
                    "reindeer",
                    "silhouette",
                    "cutout",
                    "matrix_safe",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.TRANSPARENT,
                    aspect=MatrixAspect.SQUARE_1_1,
                    base_size=256,
                ),
            )
        ],
    )


@register_template(aliases=["Star Burst", "star accent"])
def gtpl_accent_star_burst() -> GroupPlanTemplate:
    """Star burst accent with radial rays."""
    return GroupPlanTemplate(
        template_id="gtpl_accent_star_burst",
        name="Accent — Star Burst",
        description="Star burst with radial rays accent moment.",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ICON,
        tags=["holiday_christmas_traditional", "star", "accent", "burst"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        constraints=GroupConstraints(),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.HIGHLIGHT,
                motifs=["star center", "radial rays"],
                visual_intent=GroupVisualIntent.ICON,
                motion=[MotionVerb.NONE],
                density=0.6,
                contrast=0.95,
                color_mode=ColorMode.WARM,
                notes="Bright center with radiating rays.",
            ),
            LayerRecipe(
                layer=LayerRole.RHYTHM,
                motifs=["pulse glow"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE],
                density=0.3,
                contrast=0.85,
                color_mode=ColorMode.WARM,
            ),
        ],
        asset_slots=[
            AssetSlot(
                slot_id="star_icon",
                slot_type=AssetSlotType.ICON_CUTOUT,
                required=False,
                preferred_tags=[
                    "holiday_christmas_traditional",
                    "star",
                    "icon",
                    "matrix_safe",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.TRANSPARENT,
                    aspect=MatrixAspect.SQUARE_1_1,
                    base_size=256,
                ),
            )
        ],
    )


@register_template(aliases=["Holly Border", "holly pattern"])
def gtpl_pattern_holly_border() -> GroupPlanTemplate:
    """Holly leaves and berries border pattern."""
    return GroupPlanTemplate(
        template_id="gtpl_pattern_holly_border",
        name="Pattern Loop — Holly Border",
        description="Holly leaves and berries border/frame pattern.",
        template_type=GroupTemplateType.PATTERN_LOOP,
        visual_intent=GroupVisualIntent.PATTERN,
        tags=["holiday_christmas_traditional", "holly", "pattern", "border"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        constraints=GroupConstraints(),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BASE,
                motifs=["holly leaves", "red berries"],
                visual_intent=GroupVisualIntent.PATTERN,
                motion=[MotionVerb.NONE],
                density=0.5,
                contrast=0.9,
                color_mode=ColorMode.TRADITIONAL,
                notes="Frame/border style arrangement.",
            ),
        ],
        asset_slots=[
            AssetSlot(
                slot_id="holly_pattern",
                slot_type=AssetSlotType.PATTERN_TILE,
                required=False,
                preferred_tags=[
                    "holiday_christmas_traditional",
                    "holly",
                    "pattern",
                    "border",
                    "matrix_safe",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.TRANSPARENT,
                    aspect=MatrixAspect.SQUARE_1_1,
                    base_size=256,
                ),
            )
        ],
    )


@register_template(aliases=["Gingerbread House", "gingerbread scene"])
def gtpl_scene_gingerbread_house() -> GroupPlanTemplate:
    """Gingerbread house scene background."""
    return GroupPlanTemplate(
        template_id="gtpl_scene_gingerbread_house",
        name="Scene Background — Gingerbread House",
        description="Whimsical gingerbread house scene with candy details.",
        template_type=GroupTemplateType.SECTION_BACKGROUND,
        visual_intent=GroupVisualIntent.SCENE,
        tags=[
            "holiday_christmas_traditional",
            "gingerbread",
            "scene",
            "background",
            "whimsical",
        ],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        constraints=GroupConstraints(),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BASE,
                motifs=["gingerbread house", "candy decorations"],
                visual_intent=GroupVisualIntent.SCENE,
                motion=[MotionVerb.NONE],
                density=0.5,
                contrast=0.85,
                color_mode=ColorMode.WARM,
                notes="Bold shapes, avoid tiny candy detail.",
            ),
            LayerRecipe(
                layer=LayerRole.RHYTHM,
                motifs=["twinkle lights"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.TWINKLE],
                density=0.2,
                contrast=0.9,
                color_mode=ColorMode.WARM,
            ),
        ],
        asset_slots=[
            AssetSlot(
                slot_id="gingerbread_bg",
                slot_type=AssetSlotType.BACKGROUND_PLATE,
                required=True,
                preferred_tags=[
                    "holiday_christmas_traditional",
                    "gingerbread",
                    "scene",
                    "whimsical",
                    "matrix_safe",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.OPAQUE,
                    aspect=MatrixAspect.WIDE_2_1,
                    base_size=256,
                ),
            )
        ],
    )


@register_template(aliases=["Present Stack", "presents feature"])
def gtpl_feature_present_stack() -> GroupPlanTemplate:
    """Stacked presents feature with ribbon accents."""
    return GroupPlanTemplate(
        template_id="gtpl_feature_present_stack",
        name="Feature — Present Stack",
        description="Stacked wrapped presents with ribbon and bow accents.",
        template_type=GroupTemplateType.SECTION_FEATURE,
        visual_intent=GroupVisualIntent.ICON,
        tags=["holiday_christmas_traditional", "presents", "feature", "gifts"],
        projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        constraints=GroupConstraints(),
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.HIGHLIGHT,
                motifs=["stacked presents", "ribbons", "bows"],
                visual_intent=GroupVisualIntent.ICON,
                motion=[MotionVerb.NONE],
                density=0.6,
                contrast=0.9,
                color_mode=ColorMode.TRADITIONAL,
                notes="Bold present shapes, clean ribbons.",
            ),
            LayerRecipe(
                layer=LayerRole.RHYTHM,
                motifs=["sparkle accents"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.TWINKLE],
                density=0.15,
                contrast=0.85,
                color_mode=ColorMode.TRADITIONAL,
            ),
        ],
        asset_slots=[
            AssetSlot(
                slot_id="presents_icon",
                slot_type=AssetSlotType.ICON_CUTOUT,
                required=True,
                preferred_tags=[
                    "holiday_christmas_traditional",
                    "presents",
                    "gifts",
                    "cutout",
                    "matrix_safe",
                ],
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.TRANSPARENT,
                    aspect=MatrixAspect.SQUARE_1_1,
                    base_size=256,
                ),
            )
        ],
    )
