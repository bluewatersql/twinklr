# Legacy Curve Inventory (Task 0.1)

## Source of truth
- Legacy enums: `packages/blinkb0t/core/domains/sequencing/infrastructure/curves/enums.py`.
- Legacy generator implementations: `packages/blinkb0t/core/domains/sequencing/infrastructure/curves/generator.py`.

## Native curve types (xLights)
- FLAT
- RAMP
- SINE
- ABS_SINE
- PARABOLIC
- LOGARITHMIC
- EXPONENTIAL
- SAW_TOOTH

## Custom curve types (legacy catalog)
### Native equivalents (custom)
- FLAT_X
- RAMP_X
- SINE_X
- ABS_SINE_X
- PARABOLIC_X
- LOGARITHMIC_X
- EXPONENTIAL_X
- SAW_TOOTH_X

### Fundamental waves
- COSINE
- TRIANGLE
- SQUARE

### Smooth transitions
- S_CURVE
- SMOOTH_STEP
- SMOOTHER_STEP

### Easing (sine)
- EASE_IN_SINE
- EASE_OUT_SINE
- EASE_IN_OUT_SINE

### Easing (quadratic)
- EASE_IN_QUAD
- EASE_OUT_QUAD
- EASE_IN_OUT_QUAD

### Easing (cubic)
- EASE_IN_CUBIC
- EASE_OUT_CUBIC
- EASE_IN_OUT_CUBIC

### Easing (exponential)
- EASE_IN_EXPO
- EASE_OUT_EXPO
- EASE_IN_OUT_EXPO

### Easing (back)
- EASE_IN_BACK
- EASE_OUT_BACK
- EASE_IN_OUT_BACK

### Dynamic effects
- BOUNCE_IN
- BOUNCE_OUT
- ELASTIC_IN
- ELASTIC_OUT

### Musical curves
- MUSICAL_ACCENT
- MUSICAL_SWELL
- BEAT_PULSE

### Natural motion (noise)
- PERLIN_NOISE
- SIMPLEX_NOISE

### Parametric
- BEZIER
- LISS_AJOUS

### Advanced easing
- ANTICIPATE
- OVERSHOOT

## Notes for rewrite alignment
- The rewrite must prioritize points-first curves and treat these curve IDs as catalog targets.
- Movement-oriented curves should be offset-centered around `0.5` and loop-ready by default.
- Dimmer curves should remain absolute `[0,1]` with export-time mapping.
