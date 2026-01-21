# BlinkB0t Configuration Documentation Index

This directory contains comprehensive configuration documentation and examples for BlinkB0t.

## 📚 Documentation Files

### 🚀 [README.md](README.md)
**Start here!** Complete configuration guide covering all three config files.

**Contents:**
- Quick start guide
- Detailed configuration reference
- Calibration procedures
- Advanced configuration
- Troubleshooting

**Best for:** First-time setup, understanding configuration system, detailed reference

---

### ⚡ [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
Fast lookup for common tasks and values.

**Contents:**
- Common configuration tasks
- Standard poses and DMX ranges
- Performance tuning presets
- Calibration quick guide
- Default values summary
- Troubleshooting quick fixes

**Best for:** Quick lookups, common adjustments, experienced users

---

## 📄 Example Configuration Files

### 🔧 [app_config.example.json](app_config.example.json)
Application-level configuration (global settings).

**Key Settings:**
- Audio processing parameters
- LLM context building (token budgets)
- Logging configuration
- Library versions
- Default LLM model

**Copy to:** `config.json` in project root

---

### 🎯 [job_config.example.json](job_config.example.json)
Job-specific configuration (per-sequence settings).

**Key Settings:**
- Music theory assumptions (time signature)
- Multi-agent orchestration
- Semantic poses (custom positions)
- Planner features (channel control)
- Channel defaults (base appearance)
- Fixture config reference

**Copy to:** `job_config.json` in project root

---

### 🎛️ [fixture_config.example.json](fixture_config.example.json)
Fixture definitions and DMX mappings.

**Key Settings:**
- DMX addressing (universe, channels)
- Channel mappings (pan, tilt, dimmer, effects)
- Preset values (shutter, color, gobo)
- Physical ranges and limits
- Orientation calibration
- Capabilities and speed
- xLights integration

**Copy to:** `fixture_config.json` in project root

---

## 🎯 Quick Navigation

### By User Type

**First-Time User:**
1. Read [README.md](README.md) - Quick Start section
2. Copy example files to project root
3. Configure fixtures using [fixture_config.example.json](fixture_config.example.json)
4. Follow calibration guide in [README.md](README.md)

**Experienced User:**
1. Use [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for quick lookups
2. Adjust settings as needed
3. Refer to [README.md](README.md) for detailed explanations

**Troubleshooting:**
1. Check [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Troubleshooting Quick Fixes
2. See [README.md](README.md) - Troubleshooting section
3. Enable debug logging and check output

---

### By Task

**Setting up fixtures:**
→ [fixture_config.example.json](fixture_config.example.json)  
→ [README.md](README.md) - Fixture Configuration section  
→ [README.md](README.md) - Calibration Guide

**Adjusting quality/speed:**
→ [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Performance Tuning  
→ [job_config.example.json](job_config.example.json) - agent section

**Changing LLM model:**
→ [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Change LLM Model  

**Adding custom positions:**
→ [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Add Custom Position  
→ [README.md](README.md) - Custom Poses section

**Configuring colors/effects:**
→ [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Change Default Colors/Effects  
→ [job_config.example.json](job_config.example.json) - channel_defaults section

**Performance tuning:**
→ [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Performance Tuning  
→ [app_config.example.json](app_config.example.json) - planning section

**Calibrating fixtures:**
→ [README.md](README.md) - Calibration Guide  
→ [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Calibration Values

---

## 📋 File Summary

| File | Size | Lines | Purpose |
|------|------|-------|---------|
| README.md | 15 KB | 433 | Complete reference guide |
| QUICK_REFERENCE.md | 8.4 KB | 394 | Quick lookup reference |
| app_config.example.json | 3.3 KB | 85 | Application config example |
| job_config.example.json | 6.1 KB | 164 | Job config example |
| fixture_config.example.json | 12 KB | 336 | Fixture config example |

**Total Documentation:** ~45 KB, ~1,400 lines

---

## 🔗 Related Resources

### In Repository

- **User Documentation:** `doc/` directory
- **Architecture Decisions:** `changes/` directory
- **Pydantic Models:** `packages/blinkb0t/core/config/models.py`
- **Development Guidelines:** Repository rules (repo_specific_rule)

### Configuration Models

- **AppConfig:** `packages/blinkb0t/core/config/models.py` (lines 125-147)
- **JobConfig:** `packages/blinkb0t/core/config/models.py` (lines 149-233)
- **FixtureGroup:** Fixture models in core package

---

## ✅ Configuration Checklist

### Initial Setup

- [ ] Copy `app_config.example.json` → `config.json`
- [ ] Copy `job_config.example.json` → `job_config.json`
- [ ] Copy `fixture_config.example.json` → `fixture_config.json`
- [ ] Configure DMX addressing in `fixture_config.json`
- [ ] Map DMX channels in `fixture_config.json`
- [ ] Define preset values (shutter, color, gobo)
- [ ] Set physical ranges from fixture manual
- [ ] Calibrate orientation values
- [ ] Configure limits to prevent unwanted positions
- [ ] Set capabilities based on fixture specs
- [ ] Define rig positions for geometry
- [ ] Create xLights groups (LEFT, RIGHT, ODD, EVEN)
- [ ] Test with simple sequence
- [ ] Adjust `job_config.json` for your needs
- [ ] Optionally tune `config.json` for performance

### Before Each Job

- [ ] Verify `fixture_config_path` in `job_config.json`
- [ ] Set `assumptions.beats_per_bar` for song time signature
- [ ] Configure `channel_defaults` for desired base look
- [ ] Adjust `agent` settings for quality vs. speed
- [ ] Enable/disable `planner_features` as needed
- [ ] Add any custom poses for venue
- [ ] Review token budgets for song length

---

## 💡 Tips

1. **Start Simple:** Begin with minimal config, add complexity as needed
2. **Test Incrementally:** Test each fixture individually before full rig
3. **Calibrate Carefully:** Accurate orientation values are critical for positioning
4. **Use Debug Mode:** Enable debug logging when troubleshooting
5. **Save Presets:** Keep multiple job configs for different styles/venues
6. **Document Changes:** Note any custom values for future reference
7. **Version Control:** Track config files in git (except sensitive data)

---

## 🆘 Getting Help

1. **Check Documentation:**
   - [README.md](README.md) for detailed explanations
   - [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for quick fixes

2. **Enable Debug Mode:**
   - Set `logging.level: "DEBUG"` in `config.json`
   - Set `debug: true` in `job_config.json`

3. **Test with Minimal Config:**
   - Single fixture
   - Short song (< 2 minutes)
   - `max_iterations: 0` (skip judge)
   - All `planner_features` disabled

4. **Validate JSON:**
   ```bash
   python3 -c "import json; json.load(open('config.json'))"
   ```

5. **Check Models:**
   - Review Pydantic models in `packages/blinkb0t/core/config/models.py`
   - Validation errors show required fields and valid ranges

---

## 📝 Notes

- All example files include inline comments (prefixed with `_comments` or `description`)
- Comments are ignored by Pydantic validation (forward compatibility)
- Unknown fields are ignored (forward compatibility)
- All DMX values are 0-255 (8-bit) unless using 16-bit mode
- Angles are in degrees (pan: -180 to 180, tilt: -90 to 90)
- Times are in milliseconds
- Token budgets are approximate (actual usage varies)

---

**Last Updated:** 2026-01-14  
**Schema Version:** 3.0  
**Movement Library Version:** 2.0.0
