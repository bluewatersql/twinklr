# BlinkB0t Configuration Quick Reference

Quick lookup for common configuration tasks and values.

## File Locations

```
project_root/
├── config.json              # Application config (global settings)
├── job_config.json          # Job config (task-specific)
└── fixture_config.json      # Fixture definitions
```

## Common Tasks

### Change LLM Model

**In `job_config.json`:**
```json
{
  "planner": {
    "model": "gpt-5.2",
    "temperature": 0.7
  }
}
```

### Adjust Time Signature

**In `job_config.json`:**
```json
{
  "assumptions": {
    "beats_per_bar": 4  // 4=4/4 time, 3=3/4 waltz, 6=6/8
  }
}
```

### Change Default Colors/Effects

**In `job_config.json`:**
```json
{
  "channel_defaults": {
    "shutter": "open",        // or "strobe_fast", "strobe_medium", etc.
    "color": "white",         // or "red", "blue", "green", etc.
    "gobo": "open"           // or "gobo1", "gobo2", etc.
  }
}
```

### Disable Features

**In `job_config.json`:**
```json
{
  "planner_features": {
    "enable_shutter": false,  // Disable strobe effects
    "enable_color": false,    // Disable color changes
    "enable_gobo": false      // Disable gobo patterns
  }
}
```

### Add Custom Position

**In `job_config.json`:**
```json
{
  "pose_config": {
    "custom_poses": {
      "BALCONY": {
        "pose_id": "BALCONY",
        "name": "Balcony",
        "description": "Point at balcony seating",
        "pan_deg": 0.0,
        "tilt_deg": 45.0
      }
    }
  }
}
```

### Adjust Quality vs Speed

**In `job_config.json`:**
```json
{
  "agent": {
    "max_iterations": 0,      // 0=fast (no judge), 3=balanced, 5=high quality
    "success_threshold": 70   // Lower=faster, higher=better quality
  }
}
```

### Configure Fixture DMX

**In `fixture_config.json`:**
```json
{
  "fixtures": [
    {
      "fixture_id": "MH1",
      "config": {
        "dmx_universe": 1,
        "dmx_start_address": 1,
        "channel_count": 48,
        "dmx_mapping": {
          "pan_channel": 11,
          "tilt_channel": 13,
          "dimmer_channel": 3
        }
      }
    }
  ]
}
```

## Standard Poses

Built-in semantic positions (use in custom poses or overrides):

| Pose ID | Description | Default Pan | Default Tilt |
|---------|-------------|-------------|--------------|
| `FORWARD` | Forward-facing | 0° | 0° |
| `LEFT_45` | 45° left | -45° | 0° |
| `RIGHT_45` | 45° right | 45° | 0° |
| `LEFT_90` | 90° left | -90° | 0° |
| `RIGHT_90` | 90° right | 90° | 0° |
| `UP` | Pointing up | 0° | 45° |
| `DOWN` | Pointing down | 0° | -45° |
| `CEILING` | Straight up | 0° | 90° |
| `AUDIENCE_CENTER` | Audience center | 0° | -15° |
| `AUDIENCE_LEFT` | Audience left | -30° | -15° |
| `AUDIENCE_RIGHT` | Audience right | 30° | -15° |

## DMX Value Ranges

| Channel | Range | Description |
|---------|-------|-------------|
| Pan/Tilt | 0-255 | 8-bit position (or 0-65535 for 16-bit) |
| Dimmer | 0-255 | 0=off, 255=full brightness |
| Shutter | 0-255 | Fixture-specific (see manual) |
| Color | 0-255 | Fixture-specific (see manual) |
| Gobo | 0-255 | Fixture-specific (see manual) |

## Typical Shutter Values

Common DMX ranges (check your fixture manual!):

| State | Typical Range |
|-------|---------------|
| Closed | 0-10 |
| Open | 240-255 |
| Strobe Slow | 50-80 |
| Strobe Medium | 100-140 |
| Strobe Fast | 180-220 |

## Typical Color Values

Common color wheel positions (check your fixture manual!):

| Color | Typical Value |
|-------|---------------|
| Open/White | 0 |
| Red | 18-36 |
| Orange | 36-54 |
| Yellow | 54-72 |
| Green | 72-90 |
| Cyan | 90-108 |
| Blue | 108-126 |
| Magenta | 126-144 |

## Performance Tuning

### For Speed (Faster Generation)

**In `config.json`:**
```json
{
  "planning": {
    "max_beats": 300,
    "max_energy_points": 400,
    "max_spectral_points": 128
  }
}
```

**In `job_config.json`:**
```json
{
  "agent": {
    "max_iterations": 0
  },
  "planner_features": {
    "enable_shutter": false,
    "enable_color": false,
    "enable_gobo": false
  }
}
```

### For Quality (Better Results)

**In `config.json`:**
```json
{
  "planning": {
    "max_beats": 800,
    "max_energy_points": 1000,
    "max_spectral_points": 512
  }
}
```

**In `job_config.json`:**
```json
{
  "agent": {
    "max_iterations": 5,
    "success_threshold": 80
  }
}
```

## Calibration Values

### Finding Forward Position

1. Manually set fixture to point at audience center
2. Read DMX value from pan channel
3. Set in `fixture_config.json`:
```json
{
  "orientation": {
    "pan_front_dmx": 128  // Your measured value
  }
}
```

### Finding Horizon Position

1. Manually set fixture to point level (horizon)
2. Read DMX value from tilt channel
3. Set in `fixture_config.json`:
```json
{
  "orientation": {
    "tilt_zero_dmx": 22  // Your measured value
  }
}
```

### Finding Up Position

1. Manually set fixture to point straight up
2. Read DMX value from tilt channel
3. Measure angle above horizon (degrees)
4. Set in `fixture_config.json`:
```json
{
  "orientation": {
    "tilt_up_dmx": 112,           // Your measured DMX value
    "tilt_above_horizon_deg": 25.0  // Your measured angle
  }
}
```

## Logging Levels

| Level | When to Use |
|-------|-------------|
| `DEBUG` | Troubleshooting, verbose output |
| `INFO` | Normal operation (default) |
| `WARNING` | Only warnings and errors |
| `ERROR` | Only errors |
| `CRITICAL` | Only critical errors |

**In `config.json`:**
```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```

## Token Budgets

Typical token usage by song length:

| Song Length | Recommended max_beats | Recommended token_budget |
|-------------|----------------------|--------------------------|
| < 3 min | 400 | 50000 |
| 3-5 min | 600 | 75000 |
| 5-7 min | 800 | 100000 |
| > 7 min | 1000 | 150000 |

## Agent Iteration Guidelines

| max_iterations | Use Case | Speed | Quality |
|----------------|----------|-------|---------|
| 0 | Quick test, preview | Fastest | Basic |
| 1 | Single refinement pass | Fast | Good |
| 3 | Balanced (default) | Medium | Very Good |
| 5 | High quality | Slow | Excellent |

## Common Fixture Ranges

Typical pan/tilt ranges (check your fixture manual!):

| Fixture Type | Pan Range | Tilt Range |
|--------------|-----------|------------|
| Small Moving Head | 540° | 270° |
| Medium Moving Head | 540° | 270° |
| Large Moving Head | 630° | 270° |
| LED Moving Head | 540° | 180° |

## xLights Integration

Required xLights groups in `fixture_config.json`:

```json
{
  "xlights_group": "GROUP - MOVING HEADS",
  "xlights_semantic_groups": {
    "LEFT": "GROUP - MH LEFT",
    "RIGHT": "GROUP - MH RIGHT",
    "ODD": "GROUP - MH ODD",
    "EVEN": "GROUP - MH EVEN"
  }
}
```

**Create these groups in xLights:**
1. Open xLights
2. Go to Layout tab
3. Create groups with exact names above
4. Add appropriate fixtures to each group

## Validation Commands

Check JSON syntax:
```bash
python3 -c "import json; json.load(open('config.json'))"
python3 -c "import json; json.load(open('job_config.json'))"
python3 -c "import json; json.load(open('fixture_config.json'))"
```

## Default Values Summary

### AppConfig Defaults
- `output_dir`: "artifacts"
- `cache_dir`: "data/audio_cache"
- `audio_processing.hop_length`: 512
- `audio_processing.frame_length`: 2048
- `planning.max_beats`: 600
- `logging.level`: "INFO"
- `planner.model`: "gpt-5.2"
- `planner.temperature`: 0.7

### JobConfig Defaults
- `schema_version`: "3.0"
- `assumptions.beats_per_bar`: 4
- `agent.max_iterations`: 3
- `agent.success_threshold`: 70
- `agent.token_budget`: 75000
- `planner_features.enable_shutter`: true
- `planner_features.enable_color`: true
- `planner_features.enable_gobo`: true
- `channel_defaults.shutter`: "open"
- `channel_defaults.color`: "white"
- `channel_defaults.gobo`: "open"
- `include_notes_track`: true
- `debug`: true
- `checkpoint`: true

## Troubleshooting Quick Fixes

| Problem | Quick Fix |
|---------|-----------|
| Token limit exceeded | Reduce `planning.max_beats` in config.json |
| Fixtures point wrong way | Recalibrate `orientation` values |
| No color changes | Check `planner_features.enable_color` is true |
| Strobe not working | Check `shutter_map` in fixture config |
| Slow generation | Set `agent.max_iterations: 0` |
| Low quality output | Increase `agent.success_threshold` |
| xLights model not found | Check `xlights_model_name` matches exactly |

## See Also

- **Full Documentation**: `README.md` in this directory
- **Example Configs**: `*.example.json` files in this directory
- **Model Definitions**: `packages/blinkb0t/core/config/models.py`
