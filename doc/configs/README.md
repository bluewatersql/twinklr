# BlinkB0t Configuration Guide

This directory contains example configuration files for BlinkB0t. There are three main configuration files you need to set up:

1. **Application Config** (`config.json`) - Global settings shared across all jobs
2. **Job Config** (`job_config.json`) - Task-specific settings for each sequence generation
3. **Fixture Config** (`fixture_config.json`) - DMX fixture definitions and mappings

## Quick Start

1. Copy the example files to your project root:
   ```bash
   cp doc/configs/app_config.example.json config.json
   cp doc/configs/job_config.example.json job_config.json
   cp doc/configs/fixture_config.example.json fixture_config.json
   ```

2. Edit `fixture_config.json` to match your DMX fixtures (see [Fixture Configuration](#fixture-configuration))

3. Adjust `job_config.json` for your specific sequence (see [Job Configuration](#job-configuration))

4. Optionally customize `config.json` for performance tuning (see [Application Configuration](#application-configuration))

## Configuration Files

### Application Configuration

**File:** `config.json` (project root)  
**Model:** `AppConfig` in `packages/blinkb0t/core/config/models.py`  
**Purpose:** Global settings shared across all jobs

#### Key Settings

- **`output_dir`**: Where to save generated sequences (default: `artifacts`)
- **`cache_dir`**: Where to cache audio analysis (default: `data/audio_cache`)
- **`audio_processing`**: Audio analysis parameters
  - `hop_length`: Samples between frames (64-2048, default: 512)
  - `frame_length`: FFT window size (512-8192, default: 2048)
  - `cache_enabled`: Enable audio analysis caching (default: true)
- **`planning`**: LLM context building (token budget control)
  - `max_beats`: Max beat timestamps to include (100-2000, default: 600)
  - `max_energy_points`: Max energy envelope points (100-2000, default: 768)
  - `max_spectral_points`: Max spectral features (50-1000, default: 256)
  - `max_transients`: Max transient events (5-100, default: 20)
  - `max_sections`: Max structural sections (4-50, default: 12)
- **`logging`**: Python logging configuration
  - `level`: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
  - `format`: Python logging format string
- **`sequencing`**: Library version configuration
  - `movements`: Movement library version (default: "2.0.0")
  - `geometry`, `dimmer`, `curves`, `templates`: Other library versions

#### When to Modify

- **Performance tuning**: Adjust `audio_processing` parameters for speed vs. detail tradeoff
- **Token limits**: Reduce `planning` values if hitting LLM token limits
- **Long songs**: Increase `planning.max_beats` for songs > 5 minutes
- **Debugging**: Set `logging.level` to DEBUG for verbose output
- **Model changes**: Update `planner.model` to use different LLM

### Job Configuration

**File:** `job_config.json` (project root or custom path)  
**Model:** `JobConfig` in `packages/blinkb0t/core/config/models.py`  
**Purpose:** Task-specific settings for a single sequence generation

#### Key Settings

- **`schema_version`**: Config schema version (current: "3.0")
- **`fixture_config_path`**: Path to fixture configuration file
- **`assumptions`**: Music theory settings
  - `beats_per_bar`: Beats per measure (1-12, default: 4)
- **`agent`**: Multi-agent orchestration
  - `max_iterations`: Max judge/iterate loops (0 = skip judge, default: 3)
  - `success_threshold`: Min judge score to accept (0-100, default: 70)
  - `token_budget`: Total token budget for all agents (default: 75000)
  - `plan_agent`, `implementation_agent`, `judge_agent`, `refinement_agent`: Per-agent configs
- **`pose_config`**: Semantic pose definitions
  - `custom_poses`: User-defined poses (added to standard set)
  - `pose_overrides`: Override standard poses (e.g., adjust FORWARD for rig)
- **`planner_features`**: DMX channel control flags
  - `enable_shutter`: Allow shutter/strobe planning (default: true)
  - `enable_color`: Allow color wheel planning (default: true)
  - `enable_gobo`: Allow gobo pattern planning (default: true)
- **`channel_defaults`**: Default channel states
  - `shutter`: Default shutter state (default: "open")
  - `color`: Default color preset (default: "white")
  - `gobo`: Default gobo pattern (default: "open")
- **`include_notes_track`**: Include timing track in xLights (default: true)
- **`debug`**: Enable debug output (default: true)
- **`checkpoint`**: Save intermediate results (default: true)

#### When to Modify

- **Different time signature**: Change `assumptions.beats_per_bar` (e.g., 3 for waltz)
- **Simpler planning**: Disable `planner_features` to reduce complexity
- **Custom positions**: Add `custom_poses` for venue-specific positions
- **Default look**: Change `channel_defaults` for different base appearance
- **Iterative refinement**: Adjust `agent.max_iterations` and `success_threshold`
- **Token budget**: Increase `agent.token_budget` for complex songs

### Fixture Configuration

**File:** `fixture_config.json` (project root or custom path)  
**Model:** `FixtureGroup` in fixture models  
**Purpose:** DMX fixture definitions, capabilities, and mappings

#### Key Settings

- **`group_id`**: Fixture group identifier (e.g., "MOVING_HEADS")
- **`fixtures`**: Array of fixture definitions
  - `fixture_id`: Unique fixture identifier (e.g., "MH1")
  - `xlights_model_name`: xLights model name (must match exactly)
  - `config`: Fixture configuration
    - **`dmx_mapping`**: DMX channel assignments
      - `pan_channel`, `tilt_channel`, `dimmer_channel`: Core channels
      - `shutter_channel`, `color_channel`, `gobo_channel`: Effect channels
      - `shutter_map`, `color_map`, `gobo_map`: DMX value presets
    - **`inversions`**: Invert DMX for upside-down mounting
    - **`pan_tilt_range`**: Physical movement range (degrees)
    - **`orientation`**: Reference positions for calibration
      - `pan_front_dmx`: DMX value for forward-facing
      - `tilt_zero_dmx`: DMX value for horizon
      - `resting_position`: Default idle position
    - **`limits`**: DMX value limits to prevent unwanted positions
    - **`capabilities`**: Feature flags (color wheel, gobo, prism, etc.)
    - **`movement_speed`**: Speed characteristics for timing
    - **`position`**: Rig position for geometry calculations
- **`xlights_group`**: xLights group name for all fixtures
- **`xlights_semantic_groups`**: Semantic group mappings
  - `LEFT`, `RIGHT`, `ODD`, `EVEN`: xLights group names

#### When to Modify

**Always modify this file** - it's fixture-specific and must match your hardware!

1. **DMX Addressing**: Set `dmx_universe`, `dmx_start_address`, `channel_count`
2. **Channel Mapping**: Map DMX channels to fixture functions (check manual)
3. **Preset Values**: Define `shutter_map`, `color_map`, `gobo_map` (fixture-specific)
4. **Physical Range**: Set `pan_range_deg`, `tilt_range_deg` from fixture specs
5. **Calibration**: Test and adjust `orientation` values for accurate positioning
6. **Limits**: Set DMX limits to prevent hitting obstacles
7. **Capabilities**: Enable/disable features based on fixture
8. **Rig Position**: Measure and set `position` offsets for geometry effects

## Configuration Workflow

### Initial Setup

1. **Configure Fixtures** (most important!)
   - Start with `fixture_config.json`
   - Set DMX addressing (universe, start address)
   - Map DMX channels (pan, tilt, dimmer, shutter, color, gobo)
   - Define preset values (shutter_map, color_map, gobo_map)
   - Set physical ranges from fixture manual
   - Calibrate orientation (critical for positioning!)
   - Test with simple sequence

2. **Configure Job**
   - Copy `job_config.example.json` to `job_config.json`
   - Set `fixture_config_path` to your fixture config
   - Adjust `assumptions.beats_per_bar` for song time signature
   - Set `channel_defaults` for desired base look
   - Configure `agent` settings for quality vs. speed tradeoff

3. **Configure Application** (optional)
   - Copy `app_config.example.json` to `config.json`
   - Adjust `audio_processing` for performance tuning
   - Modify `planning` token budgets if needed
   - Set `logging.level` to DEBUG for troubleshooting

### Calibration Guide

#### Fixture Orientation Calibration

Critical for accurate positioning! Follow these steps:

1. **Find Forward Position**
   - Manually set fixture to point at audience center
   - Note the DMX value on pan channel
   - Set `orientation.pan_front_dmx` to this value

2. **Find Horizon Position**
   - Manually set fixture to point level (horizon)
   - Note the DMX value on tilt channel
   - Set `orientation.tilt_zero_dmx` to this value

3. **Find Up Position**
   - Manually set fixture to point straight up
   - Note the DMX value on tilt channel
   - Measure angle above horizon (protractor or estimate)
   - Set `orientation.tilt_up_dmx` to DMX value
   - Set `orientation.tilt_above_horizon_deg` to measured angle

4. **Test Positions**
   - Generate a test sequence with known poses (FORWARD, UP, DOWN)
   - Verify fixtures point where expected
   - Adjust calibration values if needed
   - Repeat until accurate

#### Preset Value Calibration

1. **Shutter Presets**
   - Test each shutter DMX range from fixture manual
   - Find DMX values for: closed, open, strobe_slow, strobe_medium, strobe_fast
   - Update `dmx_mapping.shutter_map`

2. **Color Presets**
   - Test each color wheel position
   - Find DMX values for each color
   - Update `dmx_mapping.color_map`
   - Use descriptive names (red, blue, green, etc.)

3. **Gobo Presets**
   - Test each gobo wheel position
   - Find DMX values for each pattern
   - Update `dmx_mapping.gobo_map`
   - Use descriptive names (open, stars, clouds, etc.)

## Advanced Configuration

### Custom Poses

Define venue-specific positions in `job_config.json`:

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
      },
      "STAGE_FRONT": {
        "pose_id": "STAGE_FRONT",
        "name": "Stage Front",
        "description": "Point at front edge of stage",
        "pan_deg": 0.0,
        "tilt_deg": -15.0
      }
    }
  }
}
```

### Override Standard Poses

Adjust standard poses for rig orientation:

```json
{
  "pose_config": {
    "pose_overrides": {
      "FORWARD": {
        "pose_id": "FORWARD",
        "name": "Forward",
        "description": "Adjusted for angled rig",
        "pan_deg": 15.0,
        "tilt_deg": 0.0
      }
    }
  }
}
```

### Multi-Agent Orchestration

Configure iterative plan refinement:

```json
{
  "agent": {
    "max_iterations": 3,
    "success_threshold": 70,
    "token_budget": 75000,
    "plan_agent": {
      "model": "gpt-5.2",
      "temperature": 0.7
    },
    "judge_agent": {
      "model": "gpt-5-mini",
      "temperature": 1.0
    }
  }
}
```

**Workflow:**
1. `plan_agent` generates initial choreography plan
2. `judge_agent` evaluates plan (scores 0-100)
3. If score < `success_threshold`, `refinement_agent` improves plan
4. Repeat until threshold met or `max_iterations` reached

**Tips:**
- Set `max_iterations: 0` to skip judge (faster, single-pass)
- Increase `success_threshold` for higher quality (more iterations)
- Use cheaper model for `judge_agent` to save tokens
- Increase `token_budget` for complex songs

### Channel Defaults

Set default DMX channel states:

```json
{
  "channel_defaults": {
    "shutter": "open",
    "color": "blue",
    "gobo": "stars"
  }
}
```

These are fallback values used when agent doesn't specify channel states. Agent plan can override per-section.

**Use cases:**
- Set base color scheme for entire show
- Default to strobe effect unless overridden
- Keep gobos closed unless specifically used

## Validation

All configuration files are validated using Pydantic models:

- **AppConfig**: `packages/blinkb0t/core/config/models.py`
- **JobConfig**: `packages/blinkb0t/core/config/models.py`
- **FixtureGroup**: Fixture models

Validation errors will show:
- Missing required fields
- Invalid value ranges
- Type mismatches
- Unknown fields (ignored for forward compatibility)

## Troubleshooting

### Common Issues

**"Fixture not found in xLights"**
- Check `xlights_model_name` matches xLights model name exactly (case-sensitive)
- Verify fixture exists in xLights setup

**"Fixtures pointing wrong direction"**
- Recalibrate `orientation` values (see [Calibration Guide](#calibration-guide))
- Check `inversions` if fixture is upside-down
- Verify `pan_range_deg` and `tilt_range_deg` match fixture specs

**"Token limit exceeded"**
- Reduce `planning` values in `config.json`
- Decrease `agent.token_budget` in `job_config.json`
- Disable unused `planner_features` in `job_config.json`

**"Invalid DMX values"**
- Check `dmx_mapping` channel numbers match fixture manual
- Verify `shutter_map`, `color_map`, `gobo_map` values are 0-255
- Ensure `dmx_start_address` + `channel_count` doesn't exceed 512

**"Fixtures hitting limits"**
- Adjust `limits` in fixture config
- Check `avoid_backward` setting
- Verify `pan_min`, `pan_max`, `tilt_min`, `tilt_max` values

### Debug Mode

Enable debug output in `job_config.json`:

```json
{
  "debug": true,
  "checkpoint": true
}
```

This will:
- Save intermediate results to `output_dir`
- Log detailed processing steps
- Include timing track in xLights sequence

Set logging level in `config.json`:

```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```

## Examples

See the example files in this directory:
- `app_config.example.json` - Full application config with comments
- `job_config.example.json` - Full job config with comments
- `fixture_config.example.json` - Full fixture config with comments

## Schema Versions

### Current Versions

- **Job Config Schema**: 3.0 (adds pose_config, planner_features, channel_defaults)
- **Sequencing Libraries**: movements 2.0.0, others 1.0.0

### Migration

When upgrading schema versions:
1. Check `schema_version` in `job_config.json`
2. Add new required fields (see model definitions)
3. Update `schema_version` to current version
4. Unknown fields are ignored (forward compatibility)

## Further Reading

- **User Guide**: `doc/` (user documentation)
- **Architecture**: `changes/` (design decisions)
- **Models**: `packages/blinkb0t/core/config/models.py` (Pydantic models)
- **Development Guidelines**: Repository rules (see repo_specific_rule)

## Support

For issues or questions:
1. Check this README and example configs
2. Review model definitions in `packages/blinkb0t/core/config/models.py`
3. Enable debug logging and check output
4. Test with minimal config (single fixture, simple song)
