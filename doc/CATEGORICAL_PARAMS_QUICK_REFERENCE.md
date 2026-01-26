# Categorical Parameters Quick Reference

## Intensity Levels (Choose One)

```python
from blinkb0t.core.sequencer.models.enum import Intensity

Intensity.SLOW       # 0.5x energy - Intro, ambient, chill
Intensity.SMOOTH     # 1.0x energy - Verse, baseline (DEFAULT)
Intensity.FAST       # 1.25x energy - Pre-chorus, building
Intensity.DRAMATIC   # 1.5x energy - Chorus, high-energy
Intensity.INTENSE    # 2.0x energy - Climax, drop, finale
```

## Basic Usage (90% of Cases)

```python
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.SMOOTH,  # System auto-optimizes!
)
```

## With Overrides (Advanced)

```python
Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.DRAMATIC,
    amplitude_override=0.95,      # [0.0, 1.0] - Movement range
    frequency_override=2.0,       # [0.0, 10.0] - Movement speed
    center_offset_override=0.6,   # [0.0, 1.0] - Center position
)
```

## Parameter Ranges by Intensity

| Intensity | Amplitude | Frequency | Typical Use |
|-----------|-----------|-----------|-------------|
| SLOW | 0.20-0.40 | 0.35-0.65 | Ambient, intro |
| SMOOTH | 0.40-0.60 | 0.85-1.15 | Verse, general |
| FAST | 0.60-0.80 | 1.05-1.65 | Pre-chorus |
| DRAMATIC | 0.70-0.90 | 1.05-1.75 | Chorus, peaks |
| INTENSE | 0.90-1.00 | 2.00-3.00 | Drop, finale |

## Common Patterns

### Energy Progression
```python
# Intro → Verse → Chorus → Drop
SLOW → SMOOTH → DRAMATIC → INTENSE
```

### Steady Energy
```python
# Consistent feel throughout
SMOOTH → SMOOTH → SMOOTH → SMOOTH
```

### Build and Release
```python
# Build tension, then release
SMOOTH → FAST → DRAMATIC → SMOOTH
```

## When to Use Overrides

✅ **YES** - Use overrides when:
- Specific artistic vision requires it
- Genre-specific adjustment (staccato/legato)
- Fixture-specific compensation needed
- Gradual transitions between steps

❌ **NO** - Don't override if:
- You just want different energy (use different intensity)
- You're unsure what values to use (trust defaults)
- You're copying same overrides everywhere (bad pattern)

## API Quick Reference

### Get Parameters Programmatically

```python
from blinkb0t.core.sequencer.moving_heads.libraries.movement import (
    get_curve_categorical_params,
)
from blinkb0t.core.curves.library import CurveLibrary

params = get_curve_categorical_params(
    CurveLibrary.MOVEMENT_SINE,
    Intensity.SMOOTH
)
print(f"Amplitude: {params.amplitude}")  # 0.6
print(f"Frequency: {params.frequency}")  # 1.0
```

### Get Parameters with Overrides

```python
movement = Movement(
    movement_type=MovementType.SWEEP_LR,
    intensity=Intensity.SMOOTH,
    amplitude_override=0.75,
)

# Get params for the curve this movement uses
params = movement.get_categorical_params(CurveLibrary.MOVEMENT_TRIANGLE)
print(f"Amplitude: {params.amplitude}")  # 0.75 (overridden)
print(f"Frequency: {params.frequency}")  # 1.0 (from defaults)
```

## Curve Types

| Curve | Movement Types | Character |
|-------|----------------|-----------|
| MOVEMENT_SINE | Circle, Wave, Pendulum | Smooth, flowing |
| MOVEMENT_TRIANGLE | Sweep LR/UD | Sharp, sweeping |
| MOVEMENT_PULSE | Pulse-based | Rhythmic, stepped |
| MOVEMENT_HOLD | Hold, None | Static |

## JSON Template Format

### Without Overrides
```json
{
  "movement": {
    "movement_type": "SWEEP_LR",
    "intensity": "SMOOTH"
  }
}
```

### With Overrides
```json
{
  "movement": {
    "movement_type": "SWEEP_LR",
    "intensity": "DRAMATIC",
    "amplitude_override": 0.85,
    "frequency_override": 1.8
  }
}
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Movement too fast | Lower intensity or reduce `frequency_override` |
| Movement too slow | Higher intensity or increase `frequency_override` |
| Range too large | Lower intensity or reduce `amplitude_override` |
| Range too small | Higher intensity or increase `amplitude_override` |
| Inconsistent feel | Use same intensity across movements |

## Best Practices

1. **Start Simple**: Use intensity only, no overrides
2. **Test First**: Validate defaults before overriding
3. **Override Sparingly**: Only when artistically necessary
4. **Document Why**: Comment override rationale
5. **Partial Overrides**: Only override what you need

## See Also

- [Full Template Authoring Guide](TEMPLATE_AUTHORING_CATEGORICAL_PARAMS.md)
- [Template Audit Report](../changes/vnext/optimization/TEMPLATE_AUDIT.md)
- [Optimization Results](../changes/vnext/optimization/curve_optimization_phase5_fixed.md)

---

**Quick Tip**: 80% of templates only need `intensity=Intensity.SMOOTH`. Start there!
