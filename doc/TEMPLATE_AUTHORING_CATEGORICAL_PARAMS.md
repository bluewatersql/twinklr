# Template Authoring Guide: Categorical Parameters

## Overview

Twinklr's categorical parameter system provides automatic, curve-specific optimization for movement intensity while maintaining flexibility for fine-tuning. This guide explains how to use intensity levels and parameter overrides when authoring templates.

## Quick Start

### Basic Usage (Recommended)

Most templates only need to specify the intensity level:

```python
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.SMOOTH,  # System automatically uses optimized params
    cycles=1.0,
)
```

The system automatically:
1. Determines which curve this movement uses (e.g., `MOVEMENT_TRIANGLE` for `SWEEP_LR`)
2. Retrieves optimized parameters for that curve at `SMOOTH` intensity
3. Applies those parameters during rendering

**No manual tuning required!**

## Understanding Intensity Levels

### Available Intensities

| Intensity | Energy Ratio | Typical Use | Amplitude Range | Frequency Range |
|-----------|--------------|-------------|-----------------|-----------------|
| `SLOW` | 0.5x | Intro, ambient, chill sections | 0.20-0.40 | 0.35-0.65 |
| `SMOOTH` | 1.0x (baseline) | Verse, general movement | 0.40-0.60 | 0.85-1.15 |
| `FAST` | 1.25x | Pre-chorus, building energy | 0.60-0.80 | 1.05-1.65 |
| `DRAMATIC` | 1.5x | Chorus, high-energy moments | 0.70-0.90 | 1.05-1.75 |
| `INTENSE` | 2.0x | Climax, drop, finale | 0.90-1.00 | 2.00-3.00 |

### Choosing the Right Intensity

**SLOW** - Minimal movement, creates calm atmosphere:
```python
# Perfect for intro, breakdown, or ambient sections
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.SLOW,
)
```

**SMOOTH** - Default, balanced movement:
```python
# Good for verse, general choreography
Movement(
    movement_type=MovementType.WAVE_HORIZONTAL,
    intensity=Intensity.SMOOTH,
)
```

**FAST** - Energetic but controlled:
```python
# Pre-chorus, building excitement
Movement(
    movement_type=MovementType.CIRCLE,
    intensity=Intensity.FAST,
)
```

**DRAMATIC** - High impact, attention-grabbing:
```python
# Chorus, peak moments
Movement(
    movement_type=MovementType.BOUNCE,
    intensity=Intensity.DRAMATIC,
)
```

**INTENSE** - Maximum energy, climactic:
```python
# Drop, finale, climax
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.INTENSE,
    cycles=2.0,  # Multiple cycles for extended energy
)
```

## Curve-Specific Optimization

Different movement types use different curves, and each curve has optimized parameters:

### Common Curves and Their Movements

**MOVEMENT_SINE** (Smooth, flowing):
- `CIRCLE`, `INFINITY`, `FIGURE8`
- `WAVE_HORIZONTAL`, `WAVE_VERTICAL`
- `PENDULUM`, `GROOVE_SWAY`

**MOVEMENT_TRIANGLE** (Sharp, sweeping):
- `SWEEP_LR`, `SWEEP_UD`

**MOVEMENT_COSINE** (Phase-shifted sine):
- Similar to SINE but offset

**MOVEMENT_PULSE** (Rhythmic, stepped):
- Pulse-based movements

**MOVEMENT_HOLD** (Static):
- `HOLD`, `NONE`

### Example: Same Intensity, Different Curves

```python
# SMOOTH intensity with SINE curve (flowing circle)
Movement(
    movement_type=MovementType.CIRCLE,
    intensity=Intensity.SMOOTH,
)
# Uses: amplitude=0.60, frequency=1.00 (SINE-optimized)

# SMOOTH intensity with TRIANGLE curve (sweeping)
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.SMOOTH,
)
# Uses: amplitude=0.60, frequency=1.00 (TRIANGLE-optimized)
```

Both use the same values at SMOOTH, but the system can independently optimize each curve in the future.

## When to Use Overrides

### Override Fields

```python
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.SMOOTH,
    amplitude_override=0.85,        # Optional: [0.0, 1.0]
    frequency_override=1.5,         # Optional: [0.0, 10.0]
    center_offset_override=0.6,     # Optional: [0.0, 1.0]
)
```

### When Overrides Are Useful

**1. Artistic Intent** - You have a specific vision that differs from defaults:
```python
# Extra-dramatic finale sweep
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.INTENSE,
    amplitude_override=1.0,  # Maximum amplitude
    frequency_override=3.5,  # Even faster than default
)
```

**2. Musical Style** - Genre-specific adjustments:
```python
# Staccato movement for electronic music
Movement(
    movement_type=MovementType.BOUNCE,
    intensity=Intensity.FAST,
    frequency_override=2.5,  # Faster bounces for rapid hits
)

# Legato movement for ambient music
Movement(
    movement_type=MovementType.WAVE_HORIZONTAL,
    intensity=Intensity.SMOOTH,
    frequency_override=0.6,  # Slower waves for flow
)
```

**3. Fixture-Specific Tuning** - Compensate for hardware:
```python
# Slower fixtures need more time
Movement(
    movement_type=MovementType.CIRCLE,
    intensity=Intensity.FAST,
    frequency_override=1.0,  # Reduce frequency for slower motors
)
```

**4. Step-Specific Context** - This step needs different feel:
```python
# Build section with gradually increasing energy
TemplateStep(
    step_id="build_1",
    movement=Movement(
        movement_type=MovementType.SWEEP_LR,
        intensity=Intensity.SMOOTH,
        amplitude_override=0.5,  # Start smaller
    ),
),
TemplateStep(
    step_id="build_2",
    movement=Movement(
        movement_type=MovementType.SWEEP_LR,
        intensity=Intensity.SMOOTH,
        amplitude_override=0.7,  # Increase
    ),
),
TemplateStep(
    step_id="build_3",
    movement=Movement(
        movement_type=MovementType.SWEEP_LR,
        intensity=Intensity.DRAMATIC,  # Jump to DRAMATIC
    ),
),
```

### When NOT to Use Overrides

**Don't override if**:
- ❌ You just want a different intensity → Use a different intensity level instead
- ❌ You're not sure what values to use → Trust the optimized defaults
- ❌ You're copying the same overrides everywhere → Consider if you need a new intensity level
- ❌ You haven't tested the defaults first → Start with defaults, only override if needed

## Complete Examples

### Example 1: Simple Template (No Overrides)

```python
from twinklr.core.sequencer.models.template import Movement, TemplateStep
from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementType

TemplateStep(
    step_id="verse",
    movement=Movement(
        movement_type=MovementType.SWEEP_LR,
        intensity=Intensity.SMOOTH,
        cycles=1.0,
    ),
    # ... geometry, dimmer, timing ...
)
```

**Result**: Uses optimized SWEEP_LR parameters for SMOOTH intensity.

### Example 2: Intensity Progression

```python
# Intro - Calm
TemplateStep(
    step_id="intro",
    movement=Movement(
        movement_type=MovementType.WAVE_HORIZONTAL,
        intensity=Intensity.SLOW,
        cycles=2.0,
    ),
),

# Verse - Normal
TemplateStep(
    step_id="verse",
    movement=Movement(
        movement_type=MovementType.SWEEP_LR,
        intensity=Intensity.SMOOTH,
        cycles=1.0,
    ),
),

# Pre-Chorus - Building
TemplateStep(
    step_id="pre_chorus",
    movement=Movement(
        movement_type=MovementType.CIRCLE,
        intensity=Intensity.FAST,
        cycles=1.0,
    ),
),

# Chorus - Peak
TemplateStep(
    step_id="chorus",
    movement=Movement(
        movement_type=MovementType.BOUNCE,
        intensity=Intensity.DRAMATIC,
        cycles=4.0,
    ),
),

# Drop - Maximum
TemplateStep(
    step_id="drop",
    movement=Movement(
        movement_type=MovementType.SWEEP_LR,
        intensity=Intensity.INTENSE,
        cycles=2.0,
    ),
),
```

### Example 3: With Overrides (Advanced)

```python
# Special finale with custom tuning
TemplateStep(
    step_id="finale",
    movement=Movement(
        movement_type=MovementType.SWEEP_LR,
        intensity=Intensity.INTENSE,
        cycles=3.0,
        
        # Override for extra-dramatic finale
        amplitude_override=1.0,      # Maximum sweep range
        frequency_override=4.0,      # Ultra-fast (faster than default 2.6)
        center_offset_override=0.5,  # Keep centered
    ),
    # ... rest of step ...
)
```

### Example 4: JSON Template Format

```json
{
  "template_id": "custom_sweep",
  "version": 1,
  "name": "Custom Sweep Pattern",
  "steps": [
    {
      "step_id": "main",
      "movement": {
        "movement_type": "SWEEP_LR",
        "intensity": "SMOOTH",
        "cycles": 1.0
      }
    }
  ]
}
```

**With overrides**:
```json
{
  "step_id": "special",
  "movement": {
    "movement_type": "SWEEP_LR",
    "intensity": "DRAMATIC",
    "cycles": 2.0,
    "amplitude_override": 0.95,
    "frequency_override": 2.0
  }
}
```

## API Reference

### Movement Model

```python
class Movement(BaseModel):
    """Movement specification for a template step."""
    
    movement_type: MovementType = MovementType.NONE
    intensity: Intensity = Intensity.SMOOTH
    cycles: float = 1.0
    params: dict[str, Any] = Field(default_factory=dict)
    
    # Categorical parameter overrides (optional)
    amplitude_override: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_override: float | None = Field(default=None, ge=0.0, le=10.0)
    center_offset_override: float | None = Field(default=None, ge=0.0, le=1.0)
    
    def get_categorical_params(self, curve_id: CurveLibrary) -> MovementCategoricalParams:
        """Get categorical parameters with overrides applied."""
        ...
```

### Helper Functions

```python
def get_curve_categorical_params(
    curve_id: CurveLibrary,
    intensity: Intensity,
) -> MovementCategoricalParams:
    """Get optimized parameters for a curve at a given intensity.
    
    Args:
        curve_id: Curve identifier (e.g., CurveLibrary.MOVEMENT_SINE)
        intensity: Intensity level (e.g., Intensity.SMOOTH)
        
    Returns:
        Categorical parameters (amplitude, frequency, center_offset)
        
    Example:
        >>> params = get_curve_categorical_params(
        ...     CurveLibrary.MOVEMENT_SINE,
        ...     Intensity.SMOOTH
        ... )
        >>> params.amplitude
        0.6
        >>> params.frequency
        1.0
    """
```

### MovementCategoricalParams

```python
class MovementCategoricalParams(BaseModel):
    """Categorical parameters for movement intensity levels."""
    
    amplitude: float = Field(ge=0.0, le=1.0)
    frequency: float = Field(ge=0.0, le=10.0)
    center_offset: float = Field(default=0.5, ge=0.0, le=1.0)
```

## Best Practices

### 1. Start with Intensity Levels

✅ **Good**: Let the system optimize
```python
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.DRAMATIC,
)
```

❌ **Avoid**: Jumping straight to overrides
```python
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.SMOOTH,
    amplitude_override=0.9,  # Why not use DRAMATIC instead?
    frequency_override=1.5,
)
```

### 2. Document Override Rationale

✅ **Good**: Clear intent
```python
Movement(
    movement_type=MovementType.BOUNCE,
    intensity=Intensity.FAST,
    frequency_override=2.8,  # Match 140 BPM double-time feel
)
```

❌ **Avoid**: Mysterious values
```python
Movement(
    movement_type=MovementType.BOUNCE,
    intensity=Intensity.FAST,
    frequency_override=2.8,  # Why?
)
```

### 3. Test Before Overriding

**Process**:
1. Create template with intensity only
2. Test with actual music
3. If defaults don't work, add specific override
4. Document why override is needed

### 4. Use Partial Overrides

✅ **Good**: Only override what you need
```python
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.SMOOTH,
    amplitude_override=0.75,  # Only adjust amplitude
)
```

❌ **Avoid**: Overriding everything
```python
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.SMOOTH,
    amplitude_override=0.6,    # Same as default
    frequency_override=1.0,     # Same as default
    center_offset_override=0.5, # Same as default
)
```

### 5. Keep Templates Portable

Avoid fixture-specific overrides in shared templates:

✅ **Good**: Create fixture-specific variants
```python
# templates/sweep_lr_smooth.py - General template
Movement(intensity=Intensity.SMOOTH)

# templates/sweep_lr_smooth_slow_fixtures.py - Variant
Movement(intensity=Intensity.SMOOTH, frequency_override=0.8)
```

❌ **Avoid**: Hard-coding fixture assumptions
```python
# templates/sweep_lr_smooth.py
Movement(
    intensity=Intensity.SMOOTH,
    frequency_override=0.8,  # Only works for slow fixtures!
)
```

## Troubleshooting

### Movement Too Fast/Slow

**Problem**: Movement doesn't match musical timing.

**Solution**: Try different intensity first, then override frequency:
```python
# If SMOOTH is too slow, try FAST
Movement(intensity=Intensity.FAST)

# If FAST is still not right, override
Movement(
    intensity=Intensity.FAST,
    frequency_override=1.8,  # Fine-tune
)
```

### Movement Too Large/Small

**Problem**: Sweep range is too wide or narrow.

**Solution**: Adjust intensity or amplitude:
```python
# If range is too large, reduce intensity
Movement(intensity=Intensity.SMOOTH)  # Instead of DRAMATIC

# Or override amplitude
Movement(
    intensity=Intensity.DRAMATIC,
    amplitude_override=0.7,  # Reduce from default 0.9
)
```

### Inconsistent Feel Across Curves

**Problem**: Different movements don't feel cohesive.

**Solution**: Use same intensity across movements:
```python
# Consistent SMOOTH feel
Movement(movement_type=MovementType.SWEEP_LR, intensity=Intensity.SMOOTH)
Movement(movement_type=MovementType.CIRCLE, intensity=Intensity.SMOOTH)
Movement(movement_type=MovementType.WAVE_HORIZONTAL, intensity=Intensity.SMOOTH)
```

## Migration from Old Templates

### Before (Manual Parameters)

```python
Movement(
    movement_type=MovementType.SWEEP_LR,
    params={
        "amplitude": 0.6,
        "frequency": 1.0,
    }
)
```

### After (Categorical Parameters)

```python
# Option 1: Use intensity (recommended)
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.SMOOTH,
)

# Option 2: Use overrides if you need exact values
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.SMOOTH,
    amplitude_override=0.6,
    frequency_override=1.0,
)
```

**Recommendation**: Start with Option 1, only use Option 2 if defaults don't work.

## Summary

### Quick Reference

| Goal | Solution |
|------|----------|
| Normal movement | Use `intensity=Intensity.SMOOTH` |
| Slow/calm section | Use `intensity=Intensity.SLOW` |
| High energy | Use `intensity=Intensity.DRAMATIC` or `INTENSE` |
| Fine-tune amplitude | Add `amplitude_override` |
| Fine-tune speed | Add `frequency_override` |
| Test defaults first | Always start without overrides |

### Key Principles

1. **Trust the Defaults** - Optimized parameters work for 90% of cases
2. **Intensity First** - Choose the right intensity level before considering overrides
3. **Override Sparingly** - Only when defaults don't achieve your artistic intent
4. **Document Why** - Always comment why you're overriding
5. **Test Thoroughly** - Validate with actual music before committing

## Additional Resources

- [Curve Optimization Report](../vnext/optimization/curve_optimization_phase5_fixed.md) - Detailed parameter values
- [Template Audit Report](../vnext/optimization/TEMPLATE_AUDIT.md) - Real-world template analysis
- [Movement Library Reference](../../packages/twinklr/core/sequencer/moving_heads/libraries/movement.py) - Available movement types
- [Phase 6 Documentation](../vnext/optimization/curve_movement_params/PHASE6_PROGRESS.md) - System design and implementation

---

**Version**: 1.0  
**Last Updated**: 2026-01-26  
**Status**: Production Ready
