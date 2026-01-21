# Section 2: Configuration & Rig Profiles

**Version**: 1.0  
**Date**: January 2026  
**Status**: Configuration Architecture

---

## Overview

This document defines **rig profiles**—the bridge between portable templates (role-based choreography) and physical hardware (fixture-specific DMX). Rig profiles are the dependency injection layer that makes templates truly reusable.

**Critical Separation**: Templates define **what** to do (choreography). Rig profiles define **who** does it (fixture mapping) and **how** to do it (calibration).

---

## 1. Rig Profile Philosophy

### Core Principles

1. **Templates are portable, rigs are specific**
   - Templates use roles (OUTER_LEFT, INNER_RIGHT)
   - Rig profiles map roles → fixture IDs
   - Same template works on 4-head, 6-head, 8-head rigs

2. **Rig profiles are configuration, not code**
   - JSON/YAML files, not Python classes
   - Loaded at runtime
   - Editable without code changes

3. **Calibration is per-fixture**
   - Each fixture has unique DMX ranges
   - Pan/tilt limits vary by mounting position
   - Dimmer floors handle minimum safe brightness

4. **Orders enable sequencing**
   - Define fixture sequences for phase offsets
   - Multiple orders for different patterns (LEFT_TO_RIGHT, OUTSIDE_IN)
   - Templates reference order names, not positions

---

## 2. Rig Profile Structure

### Complete Example

```json
{
  "rig_id": "rooftop_4",
  "name": "Rooftop 4-Head Configuration",
  "version": 1,
  
  "fixtures": [
    "mh1", "mh2", "mh3", "mh4"
  ],
  
  "role_bindings": {
    "mh1": "OUTER_LEFT",
    "mh2": "INNER_LEFT",
    "mh3": "INNER_RIGHT",
    "mh4": "OUTER_RIGHT"
  },
  
  "groups": {
    "ALL": ["mh1", "mh2", "mh3", "mh4"],
    "LEFT": ["mh1", "mh2"],
    "RIGHT": ["mh3", "mh4"],
    "INNER": ["mh2", "mh3"],
    "OUTER": ["mh1", "mh4"],
    "ODD": ["mh1", "mh3"],
    "EVEN": ["mh2", "mh4"]
  },
  
  "orders": {
    "LEFT_TO_RIGHT": ["mh1", "mh2", "mh3", "mh4"],
    "RIGHT_TO_LEFT": ["mh4", "mh3", "mh2", "mh1"],
    "OUTSIDE_IN": ["mh1", "mh4", "mh2", "mh3"],
    "INSIDE_OUT": ["mh2", "mh3", "mh1", "mh4"],
    "ODD_EVEN": ["mh1", "mh3", "mh2", "mh4"]
  },
  
  "calibration": {
    "global": {
      "pan_amplitude_dmx": 90,
      "tilt_amplitude_dmx": 60,
      "dimmer_floor_dmx": 30
    },
    "fixtures": {
      "mh1": {
        "pan_min": 0,
        "pan_max": 255,
        "pan_center": 128,
        "tilt_min": 0,
        "tilt_max": 200,
        "tilt_center": 100,
        "dimmer_floor_dmx": 35
      },
      "mh2": {
        "pan_min": 0,
        "pan_max": 255,
        "pan_center": 128,
        "tilt_min": 0,
        "tilt_max": 200,
        "tilt_center": 100,
        "dimmer_floor_dmx": 30
      },
      "mh3": {
        "pan_min": 0,
        "pan_max": 255,
        "pan_center": 128,
        "tilt_min": 0,
        "tilt_max": 200,
        "tilt_center": 100,
        "dimmer_floor_dmx": 30
      },
      "mh4": {
        "pan_min": 0,
        "pan_max": 255,
        "pan_center": 128,
        "tilt_min": 0,
        "tilt_max": 200,
        "tilt_center": 100,
        "dimmer_floor_dmx": 40
      }
    },
    "pose_tokens": {
      "CENTER": 0.50,
      "CENTER_SOFT": 0.50,
      "MID_LEFT": 0.35,
      "MID_RIGHT": 0.65,
      "WIDE_LEFT": 0.15,
      "WIDE_RIGHT": 0.85,
      "MAX_LEFT": 0.05,
      "MAX_RIGHT": 0.95
    },
    "aim_zones": {
      "SKY": 0.85,
      "HORIZON": 0.50,
      "CROWD": 0.35,
      "STAGE": 0.20
    }
  },
  
  "metadata": {
    "description": "Standard rooftop 4-head configuration",
    "venue": "outdoor_stage",
    "fixture_model": "Chauvet Intimidator Spot 375Z",
    "updated": "2026-01-20"
  }
}
```

---

## 3. Rig Profile Components

### 3.1 Fixtures

**Simple fixture list:**

```json
"fixtures": ["mh1", "mh2", "mh3", "mh4"]
```

**Requirements:**
- Unique fixture IDs
- Match xLights model names exactly
- Consistent naming convention (mh1, mh2... recommended)

**Multi-rig example:**

```json
{
  "rig_id": "main_stage_8",
  "fixtures": [
    "mh_front_1", "mh_front_2", "mh_front_3", "mh_front_4",
    "mh_back_1", "mh_back_2", "mh_back_3", "mh_back_4"
  ]
}
```

### 3.2 Role Bindings

**Maps fixtures → roles:**

```json
"role_bindings": {
  "mh1": "OUTER_LEFT",
  "mh2": "INNER_LEFT",
  "mh3": "INNER_RIGHT",
  "mh4": "OUTER_RIGHT"
}
```

**Rules:**
1. Every fixture MUST have a role
2. Roles MUST match template requirements
3. Multiple fixtures CAN share roles (for larger rigs)

**Template compatibility check:**

```python
def check_template_compatibility(rig: RigProfile, template: Template) -> bool:
    """
    Verify rig can execute template.
    """
    rig_roles = set(rig.role_bindings.values())
    required_roles = set(template.roles)
    
    if not required_roles.issubset(rig_roles):
        missing = required_roles - rig_roles
        raise ValueError(f"Rig missing required roles: {missing}")
    
    return True
```

**Flexible role mapping:**

```json
// 6-head rig using 4-head template
"role_bindings": {
  "mh1": "OUTER_LEFT",
  "mh2": "INNER_LEFT",
  "mh3": "INNER_LEFT",    // Two fixtures share role
  "mh4": "INNER_RIGHT",
  "mh5": "INNER_RIGHT",   // Two fixtures share role
  "mh6": "OUTER_RIGHT"
}
```

This lets larger rigs run templates designed for smaller setups (with duplicated roles).

### 3.3 Groups

**Collections of fixtures for targeting:**

```json
"groups": {
  "ALL": ["mh1", "mh2", "mh3", "mh4"],
  "LEFT": ["mh1", "mh2"],
  "RIGHT": ["mh3", "mh4"],
  "INNER": ["mh2", "mh3"],
  "OUTER": ["mh1", "mh4"],
  "ODD": ["mh1", "mh3"],
  "EVEN": ["mh2", "mh4"]
}
```

**Group resolution in templates:**

When template specifies `"target": "INNER"`:

```python
def resolve_target_fixtures(target_group: str, rig: RigProfile) -> list[str]:
    """
    Map group name to fixture IDs.
    """
    if target_group not in rig.groups:
        raise ValueError(f"Unknown group: {target_group}")
    
    return list(rig.groups[target_group])
```

**Standard group conventions:**

| Group Name | Meaning                      | Typical Use                |
|-----------|------------------------------|----------------------------|
| ALL       | Every fixture                | Full rig choreography      |
| LEFT      | Left half of rig             | Split targeting            |
| RIGHT     | Right half of rig            | Split targeting            |
| INNER     | Center fixtures              | Focus attention            |
| OUTER     | Edge fixtures                | Frame/background           |
| ODD       | Alternating (1, 3, 5...)     | Checker patterns           |
| EVEN      | Alternating (2, 4, 6...)     | Checker patterns           |
| FRONT     | Downstage fixtures           | Audience-facing            |
| BACK      | Upstage fixtures             | Stage wash                 |

**Custom groups for special effects:**

```json
"groups": {
  "CORNERS": ["mh1", "mh4", "mh5", "mh8"],
  "CROSS_LEFT": ["mh1", "mh4"],
  "CROSS_RIGHT": ["mh5", "mh8"]
}
```

### 3.4 Orders

**Sequences for phase offsets and wave effects:**

```json
"orders": {
  "LEFT_TO_RIGHT": ["mh1", "mh2", "mh3", "mh4"],
  "RIGHT_TO_LEFT": ["mh4", "mh3", "mh2", "mh1"],
  "OUTSIDE_IN": ["mh1", "mh4", "mh2", "mh3"],
  "INSIDE_OUT": ["mh2", "mh3", "mh1", "mh4"],
  "ODD_EVEN": ["mh1", "mh3", "mh2", "mh4"],
  "EVEN_ODD": ["mh2", "mh4", "mh1", "mh3"]
}
```

**Phase offset computation:**

```python
def compute_phase_offsets(
    group_fixtures: list[str],
    order: str,
    rig: RigProfile,
    spread_bars: float
) -> dict[str, float]:
    """
    Compute per-fixture time offsets based on order.
    """
    if order not in rig.orders:
        raise ValueError(f"Unknown order: {order}")
    
    # Get full order, filter to group fixtures
    full_order = rig.orders[order]
    ordered = [fx for fx in full_order if fx in group_fixtures]
    
    n = len(ordered)
    if n <= 1:
        return {fx: 0.0 for fx in group_fixtures}
    
    # Linear distribution
    offsets = {}
    for i, fx in enumerate(ordered):
        offsets[fx] = (i / (n - 1)) * spread_bars
    
    return offsets
```

**Example offsets:**

```python
# Given:
# order = "LEFT_TO_RIGHT": ["mh1", "mh2", "mh3", "mh4"]
# spread_bars = 1.0
#
# Result:
offsets = {
    "mh1": 0.0,      # First (leftmost)
    "mh2": 0.333,    # Second
    "mh3": 0.667,    # Third
    "mh4": 1.0       # Last (rightmost)
}
```

**Standard order patterns:**

| Order Name    | Pattern                  | Visual Effect              |
|--------------|--------------------------|----------------------------|
| LEFT_TO_RIGHT | Sequential left → right  | Wave sweep                 |
| RIGHT_TO_LEFT | Sequential right → left  | Reverse wave               |
| OUTSIDE_IN   | Edges → center           | Converging focus           |
| INSIDE_OUT   | Center → edges           | Expanding reveal           |
| ODD_EVEN     | Alternating 1,3,5→2,4,6  | Staggered checkerboard     |
| EVEN_ODD     | Alternating 2,4,6→1,3,5  | Reverse checkerboard       |
| RANDOM       | Pseudorandom sequence    | Scattered, chaotic         |

---

## 4. Calibration

### 4.1 Global Calibration

**Applies to all fixtures as defaults:**

```json
"calibration": {
  "global": {
    "pan_amplitude_dmx": 90,
    "tilt_amplitude_dmx": 60,
    "dimmer_floor_dmx": 30
  }
}
```

**Fields:**

- **pan_amplitude_dmx**: Maximum delta for pan movement (DMX units)
  - Represents physical range (e.g., 90 DMX = 90° sweep)
  - Used to scale movement intensity
  
- **tilt_amplitude_dmx**: Maximum delta for tilt movement (DMX units)
  - Typically smaller than pan (limited vertical range)
  
- **dimmer_floor_dmx**: Minimum safe dimmer value
  - Hardware limitation (bulb requires minimum power)
  - Venue preference (never fully dark)

### 4.2 Per-Fixture Calibration

**Overrides for specific fixtures:**

```json
"fixtures": {
  "mh1": {
    "pan_min": 0,
    "pan_max": 255,
    "pan_center": 128,
    "tilt_min": 0,
    "tilt_max": 200,
    "tilt_center": 100,
    "dimmer_floor_dmx": 35
  }
}
```

**Pan/Tilt Calibration:**

- **pan_min / pan_max**: Safe DMX range (avoid mechanical limits)
- **pan_center**: DMX value for "straight ahead" pose
- **tilt_min / tilt_max**: Safe tilt range
- **tilt_center**: DMX value for "horizon" aim

**Why per-fixture?**
- Different mounting angles
- Mechanical wear (one fixture may have tighter limits)
- Beam interference (prevent light collision)

**Example: Edge fixtures with restricted pan:**

```json
"mh1": {
  "pan_min": 40,    // Don't pan too far left (off stage)
  "pan_max": 200,   // Full right range OK
  "pan_center": 120
},
"mh4": {
  "pan_min": 55,    // Full left range OK
  "pan_max": 215,   // Don't pan too far right (off stage)
  "pan_center": 135
}
```

### 4.3 Pose Token Mapping

**Semantic positions → normalized values:**

```json
"pose_tokens": {
  "CENTER": 0.50,
  "CENTER_SOFT": 0.50,
  "MID_LEFT": 0.35,
  "MID_RIGHT": 0.65,
  "WIDE_LEFT": 0.15,
  "WIDE_RIGHT": 0.85,
  "MAX_LEFT": 0.05,
  "MAX_RIGHT": 0.95
}
```

**Token resolution:**

```python
def resolve_pan_token(
    token: str,
    fixture_id: str,
    rig: RigProfile
) -> int:
    """
    Map pose token to fixture-specific DMX value.
    """
    # Get normalized position [0, 1]
    norm_position = rig.calibration.pose_tokens[token]
    
    # Get fixture calibration
    cal = rig.calibration.fixtures[fixture_id]
    
    # Map to DMX range
    pan_range = cal.pan_max - cal.pan_min
    pan_dmx = cal.pan_min + int(pan_range * norm_position)
    
    # Clamp to safe limits
    return clamp(pan_dmx, cal.pan_min, cal.pan_max)
```

**Example:**

```python
# Token: "WIDE_LEFT" = 0.15
# Fixture: mh1
# Calibration: pan_min=0, pan_max=255

pan_dmx = 0 + int(255 * 0.15) = 38

# Result: mh1 points to position 38 (wide left)
```

**Benefits:**
- Consistent semantics across rigs
- Per-fixture calibration adjustments
- Easy to tweak feel without changing templates

### 4.4 Aim Zone Mapping

**Vertical targets → normalized tilt:**

```json
"aim_zones": {
  "SKY": 0.85,
  "HORIZON": 0.50,
  "CROWD": 0.35,
  "STAGE": 0.20
}
```

**Resolution (similar to pan tokens):**

```python
def resolve_tilt_aim(
    zone: str,
    fixture_id: str,
    rig: RigProfile
) -> int:
    """
    Map aim zone to fixture-specific tilt DMX.
    """
    norm_tilt = rig.calibration.aim_zones[zone]
    cal = rig.calibration.fixtures[fixture_id]
    
    tilt_range = cal.tilt_max - cal.tilt_min
    tilt_dmx = cal.tilt_min + int(tilt_range * norm_tilt)
    
    return clamp(tilt_dmx, cal.tilt_min, cal.tilt_max)
```

**Typical zones:**

| Zone      | Normalized | Physical Target       |
|-----------|------------|-----------------------|
| SKY       | 0.85       | Upward, atmospheric   |
| HORIZON   | 0.50       | Straight out, crowd   |
| CROWD     | 0.35       | Downward, floor wash  |
| STAGE     | 0.20       | Steep down, spotlight |

---

## 5. Rig Profile Discovery & Loading

### 5.1 File Organization

```
config/rigs/
├── rooftop_4.json
├── stage_left_6.json
├── stage_right_6.json
├── main_stage_8.json
└── full_venue_16.json
```

### 5.2 Loading Pattern

```python
from pathlib import Path
from pydantic import TypeAdapter
from blinkb0t.core.config.models import RigProfile

rig_adapter = TypeAdapter(RigProfile)

def load_rig_profile(path: Path) -> RigProfile:
    """
    Load and validate rig profile JSON.
    """
    with open(path) as f:
        data = json.load(f)
    return rig_adapter.validate_python(data)

# Registry
rig_registry: dict[str, RigProfile] = {}

for rig_file in Path("config/rigs").glob("*.json"):
    rig = load_rig_profile(rig_file)
    rig_registry[rig.rig_id] = rig
```

### 5.3 Runtime Selection

```python
def resolve_rig(rig_id: str, registry: dict[str, RigProfile]) -> RigProfile:
    """
    Get rig profile by ID with validation.
    """
    if rig_id not in registry:
        raise ValueError(f"Unknown rig_id: {rig_id}")
    return registry[rig_id]

# Usage
rig = resolve_rig("rooftop_4", rig_registry)
```

---

## 6. Rig → Template Mapping

### 6.1 Compatibility Validation

```python
def validate_template_rig_compatibility(
    template: Template,
    rig: RigProfile
) -> list[str]:
    """
    Check if rig can execute template.
    Returns list of errors (empty if compatible).
    """
    errors = []
    
    # Check roles
    rig_roles = set(rig.role_bindings.values())
    required_roles = set(template.roles)
    missing_roles = required_roles - rig_roles
    if missing_roles:
        errors.append(f"Missing roles: {missing_roles}")
    
    # Check groups
    for group_name, role_list in template.groups.items():
        if group_name not in rig.groups:
            errors.append(f"Missing group: {group_name}")
        else:
            # Verify group contains fixtures with required roles
            group_fixtures = rig.groups[group_name]
            group_roles = {rig.role_bindings[fx] for fx in group_fixtures}
            template_roles = set(role_list)
            if not template_roles.issubset(group_roles):
                missing = template_roles - group_roles
                errors.append(
                    f"Group '{group_name}' missing roles: {missing}"
                )
    
    # Check orders
    for step in template.steps:
        phase = step.timing.phase_offset
        if phase and phase.mode == PhaseOffsetMode.GROUP_ORDER:
            if phase.order not in rig.orders:
                errors.append(
                    f"Step '{step.step_id}' requires order '{phase.order}'"
                )
    
    return errors
```

### 6.2 Fixture Resolution

```python
def resolve_step_fixtures(
    step: Step,
    rig: RigProfile
) -> list[str]:
    """
    Map step target group to fixture IDs.
    """
    target_group = step.target
    
    if target_group not in rig.groups:
        raise ValueError(f"Unknown group: {target_group}")
    
    return list(rig.groups[target_group])
```

### 6.3 Geometry Resolution with Rig

**Example: Role-based geometry:**

```python
def resolve_geometry_role_pose(
    step: Step,
    fixtures: list[str],
    rig: RigProfile
) -> dict[str, tuple[int, int]]:
    """
    Resolve base pose using role mappings.
    """
    geometry = step.geometry  # RolePoseGeometry
    base_pose = {}
    
    for fixture_id in fixtures:
        # Get role for this fixture
        role = rig.role_bindings[fixture_id]
        
        # Get pan token for this role
        pan_token = geometry.pan_pose_by_role[role]
        pan_dmx = resolve_pan_token(pan_token, fixture_id, rig)
        
        # Get tilt from aim zone
        tilt_zone = geometry.tilt_pose
        tilt_dmx = resolve_tilt_aim(tilt_zone, fixture_id, rig)
        
        base_pose[fixture_id] = (pan_dmx, tilt_dmx)
    
    return base_pose
```

---

## 7. Migration from Current System

### 7.1 Current System Problems

**Existing FixtureGroup model:**
- Embedded in templates
- Mix of configuration and choreography
- Not reusable across templates
- Hardcoded fixture assumptions

**Example current pattern:**

```python
# Embedded in template code
fixture_group = FixtureGroup(
    fixtures=["mh1", "mh2", "mh3", "mh4"],
    semantic_map={"LEFT": ["mh1", "mh2"], ...}
)
```

### 7.2 Migration Strategy

#### Extract Rig Data

```python
def rig_profile_from_fixture_group(
    group: FixtureGroup,
    *,
    rig_id: str | None = None,
    infer_semantic_groups: bool = True,
    infer_orders: bool = True,
    infer_roles: bool = True,
    dimmer_floor_dmx: int | None = None,
) -> RigProfile:
    """Create a RigProfile from a FixtureGroup.

    Assumptions (MVP):
    - ordering is based on FixturePosition.position_index when available
    - rooftop 4-head common groups/orders can be inferred

    You can turn off inference and provide groups/orders/roles explicitly.

    Example Usage:
    from rig_adapters import rig_profile_from_fixture_group

    rig = rig_profile_from_fixture_group(
        moving_heads_group,
        rig_id="rooftop_4",
        dimmer_floor_dmx=60,  # set your real floor here
    )
    """

    fixtures = group.expand_fixtures()

    # Order left->right using position_index when present, otherwise fixture_id.
    def _sort_key(fx):
        pos = getattr(fx.config, "position", None)
        if pos is not None and getattr(pos, "position_index", None) is not None:
            return (int(pos.position_index), fx.fixture_id)
        return (10_000, fx.fixture_id)

    fixtures_sorted = sorted(fixtures, key=_sort_key)
    fixture_ids = [f.fixture_id for f in fixtures_sorted]

    groups: dict[SemanticGroup, list[str]] = {}
    orders: dict[OrderMode, list[str]] = {}
    role_bindings: dict[str, TemplateRole] = {}

    if infer_orders:
        orders[OrderMode.LEFT_TO_RIGHT] = list(fixture_ids)
        orders[OrderMode.RIGHT_TO_LEFT] = list(reversed(fixture_ids))

        # Outside-in / inside-out require at least 4 fixtures to be meaningful.
        if len(fixture_ids) >= 4:
            # OUTSIDE_IN: [1, N, 2, N-1, ...]
            outside_in: list[str] = []
            left = 0
            right = len(fixture_ids) - 1
            while left <= right:
                if left == right:
                    outside_in.append(fixture_ids[left])
                else:
                    outside_in.append(fixture_ids[left])
                    outside_in.append(fixture_ids[right])
                left += 1
                right -= 1
            orders[OrderMode.OUTSIDE_IN] = outside_in
            orders[OrderMode.INSIDE_OUT] = list(reversed(outside_in))

            odds = fixture_ids[::2]
            evens = fixture_ids[1::2]
            orders[OrderMode.ODD_EVEN] = odds + evens

    if infer_semantic_groups:
        groups[SemanticGroup.ALL] = list(fixture_ids)
        mid = len(fixture_ids) // 2
        groups[SemanticGroup.LEFT] = fixture_ids[:mid]
        groups[SemanticGroup.RIGHT] = fixture_ids[mid:]

        if len(fixture_ids) >= 4:
            groups[SemanticGroup.OUTER] = [fixture_ids[0], fixture_ids[-1]]
            groups[SemanticGroup.INNER] = fixture_ids[1:-1]

        groups[SemanticGroup.ODD] = fixture_ids[::2]
        groups[SemanticGroup.EVEN] = fixture_ids[1::2]

    if infer_roles:
        role_bindings = _resolve_role_bindings(fixture_ids)

    calib_kwargs = {}
    if dimmer_floor_dmx is not None:
        calib_kwargs["dimmer_floor_dmx"] = dimmer_floor_dmx

    return RigProfile(
        rig_id=rig_id or group.group_id,
        fixtures=fixture_ids,
        groups=groups,
        orders=orders,
        role_bindings=role_bindings,
        calibration=calib_kwargs or {},
    )


def _resolve_role_bindings(fixture_ids: list[str]) -> dict[str, TemplateRole]:
    """
    Deterministically bind each fixture (ordered left->right) to a TemplateRole.

    Contract (matches the semantics we discussed):
    - N=4 special-case maps to OUTER/INNER/INNER/OUTER (your POC layout)
    - Even N>=6:
        1 FAR_LEFT, 2 OUTER_LEFT, 3 INNER_LEFT (if N>=8), mids, CENTER_LEFT, CENTER_RIGHT, mids, INNER_RIGHT, OUTER_RIGHT, FAR_RIGHT
      where MID_* can be a multi-fixture band for larger rigs (e.g., N=12).
    - Odd N is handled sensibly (CENTER is the single middle fixture), but your
      main targets (4/6/8/12) are even.
    """
    n = len(fixture_ids)
    if n == 0:
        return {}

    # --- Exactly 4 fixtures ---
    if n == 4:
        return {
            fixture_ids[0]: TemplateRole.OUTER_LEFT,
            fixture_ids[1]: TemplateRole.INNER_LEFT,
            fixture_ids[2]: TemplateRole.INNER_RIGHT,
            fixture_ids[3]: TemplateRole.OUTER_RIGHT,
        }

    role_bindings: dict[str, TemplateRole] = {}

    def bind(idx: int, role: TemplateRole) -> None:
        # deterministic: first bind wins (avoid overwriting if logic overlaps)
        if 0 <= idx < n and fixture_ids[idx] not in role_bindings:
            role_bindings[fixture_ids[idx]] = role

    # --- Anchors ---
    bind(0, TemplateRole.FAR_LEFT)
    bind(n - 1, TemplateRole.FAR_RIGHT)

    # --- Outer band (only distinct once there are at least 6 fixtures) ---
    if n >= 6:
        bind(1, TemplateRole.OUTER_LEFT)
        bind(n - 2, TemplateRole.OUTER_RIGHT)

    # --- Centers ---
    if n % 2 == 0:
        # even: center pair
        cl = (n // 2) - 1
        cr = n // 2
        bind(cl, TemplateRole.CENTER_LEFT)
        bind(cr, TemplateRole.CENTER_RIGHT)

        # --- Inner band (distinct once there is room between outer and center => N>=8) ---
        if n >= 8:
            il = 2
            ir = n - 3
            bind(il, TemplateRole.INNER_LEFT)
            bind(ir, TemplateRole.INNER_RIGHT)

            # --- Mid bands: anything between INNER and CENTER on each side ---
            for i in range(il + 1, cl):
                bind(i, TemplateRole.MID_LEFT)
            for i in range(cr + 1, ir):
                bind(i, TemplateRole.MID_RIGHT)

        # For N=6, INNER/MID conceptually alias to center roles; fixture->role is already covered.
        # For N=8, MID aliases to center roles; fixture->role is already covered.

    else:
        # odd: single center
        c = n // 2
        bind(c, TemplateRole.CENTER)

        # nearest neighbors get CENTER_LEFT / CENTER_RIGHT if present
        bind(c - 1, TemplateRole.CENTER_LEFT)
        bind(c + 1, TemplateRole.CENTER_RIGHT)

        # make OUTER distinct once there are enough fixtures
        if n >= 7:
            bind(1, TemplateRole.OUTER_LEFT)
            bind(n - 2, TemplateRole.OUTER_RIGHT)

        # make INNER distinct once there's room (odd analogue of N>=8 => N>=9)
        if n >= 9:
            il = 2
            ir = n - 3
            bind(il, TemplateRole.INNER_LEFT)
            bind(ir, TemplateRole.INNER_RIGHT)

            # mid bands between inner and center-neighbor
            for i in range(il + 1, c - 1):
                bind(i, TemplateRole.MID_LEFT)
            for i in range(c + 2, ir):
                bind(i, TemplateRole.MID_RIGHT)

    # --- Fill any remaining unbound fixtures deterministically (rare edge cases) ---
    # Prefer to classify by side and proximity so nothing is left unassigned.
    if len(role_bindings) < n:
        # Compute a "center" index for side classification
        center_pos = (n - 1) / 2.0
        for i, fid in enumerate(fixture_ids):
            if fid in role_bindings:
                continue
            if i < center_pos:
                role_bindings[fid] = TemplateRole.MID_LEFT
            elif i > center_pos:
                role_bindings[fid] = TemplateRole.MID_RIGHT
            else:
                role_bindings[fid] = TemplateRole.CENTER

    return role_bindings
```

---

## 8. Rig Profile Pydantic Models

### Constrained Values 

```python
class OrderMode(str, Enum):
    LEFT_TO_RIGHT = "LEFT_TO_RIGHT"
    RIGHT_TO_LEFT = "RIGHT_TO_LEFT"
    OUTSIDE_IN = "OUTSIDE_IN"
    INSIDE_OUT = "INSIDE_OUT"
    ODD_EVEN = "ODD_EVEN"
    EVEN_ODD = "EVEN_ODD"


class SemanticGroup(str, Enum):
    ALL = "ALL"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    INNER = "INNER"
    OUTER = "OUTER"
    ODD = "ODD"
    EVEN = "EVEN"

class TemplateRole(str, Enum):
    OUTER_LEFT = "OUTER_LEFT"
    INNER_LEFT = "INNER_LEFT"
    INNER_RIGHT = "INNER_RIGHT"
    OUTER_RIGHT = "OUTER_RIGHT"
    FAR_LEFT = "FAR_LEFT"
    FAR_RIGHT = "FAR_RIGHT"
    MID_LEFT = "MID_LEFT"
    MID_RIGHT = "MID_RIGHT"
    CENTER_LEFT = "CENTER_LEFT"
    CENTER_RIGHT = "CENTER_RIGHT"
    CENTER = "CENTER"


class PoseID(str, Enum):
    CENTER = "CENTER"
    CENTER_SOFT = "CENTER_SOFT"
    MID_LEFT = "MID_LEFT"
    MID_RIGHT = "MID_RIGHT"
    WIDE_LEFT = "WIDE_LEFT"
    WIDE_RIGHT = "WIDE_RIGHT"
    MAX_LEFT = "MAX_LEFT"
    MAX_RIGHT = "MAX_RIGHT"
    CURRENT = "CURRENT"
    FORWARD = "FORWARD"
    UP = "UP"
    DOWN = "DOWN"
    CEILING = "CEILING"
    SOFT_HOME = "SOFT_HOME"
```

### Complete Schema

```python
class FixtureCalibration(BaseModel):
    """Per-fixture calibration limits."""

    model_config = ConfigDict(extra="forbid")

    pan_min: int = Field(..., ge=0, le=255)
    pan_max: int = Field(..., ge=0, le=255)
    pan_center: int = Field(..., ge=0, le=255)

    tilt_min: int = Field(..., ge=0, le=255)
    tilt_max: int = Field(..., ge=0, le=255)
    tilt_center: int = Field(..., ge=0, le=255)

    dimmer_floor_dmx: int = Field(default=0, ge=0, le=255)


class GlobalCalibration(BaseModel):
    """Rig-wide calibration defaults."""

    model_config = ConfigDict(extra="forbid")

    pan_amplitude_dmx: int = Field(90, ge=0, le=255)
    tilt_amplitude_dmx: int = Field(60, ge=0, le=255)
    dimmer_floor_dmx: int = Field(0, ge=0, le=255)


class RigCalibration(BaseModel):
    """Complete calibration settings."""

    model_config = ConfigDict(extra="forbid")

    global_: GlobalCalibration = Field(alias="global")
    fixtures: dict[str, FixtureCalibration] = Field(default_factory=dict)
    pose_tokens: dict[PoseID, float]  # token -> normalized [0,1]
    aim_zones: dict[AimZone, float]  # zone -> normalized [0,1]


class RigProfile(BaseModel):
    """Rig configuration (fixtures + semantics).

    - `fixtures` are the physical units.
    - `groups` define semantic targeting (ALL/LEFT/RIGHT/INNER/OUTER/...)
    - `orders` define chase orderings (LEFT_TO_RIGHT/OUTSIDE_IN/...)
    - `role_bindings` define optional roles per fixture (OUTER_LEFT/INNER_LEFT/...)

    This is intentionally separate from templates so templates remain portable.
    """

    model_config = ConfigDict(extra="forbid")

    rig_id: str = Field(..., min_length=1)

    # Fixtures are referenced by ID (e.g., "mh1", "mh2").
    # You can attach your existing FixtureInstance/FixtureConfig elsewhere.
    fixtures: list[str] = Field(..., min_length=1)

    # Optional role semantics (fixture_id -> role). Roles are strings on purpose
    # so you can evolve without a global enum.
    role_bindings: dict[str, TemplateRole] = Field(default_factory=dict)

    # groups: name -> list of fixture_ids
    groups: dict[SemanticGroup, list[str]] = Field(default_factory=dict)

    # orders: name -> list of fixture_ids (must be permutation/subset)
    orders: dict[OrderMode, list[str]] = Field(default_factory=dict)

    calibration: RigCalibration = Field(default_factory=RigCalibration)  # type: ignore

    @field_validator("fixtures")
    @classmethod
    def _fixtures_unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("RigProfile.fixtures must be unique")
        return v

    @model_validator(mode="after")
    def _validate_groups_orders(self) -> RigProfile:
        fixture_set = set(self.fixtures)

        # Validate groups reference known fixtures
        for gname, members in self.groups.items():
            unknown = [m for m in members if m not in fixture_set]
            if unknown:
                raise ValueError(f"Group '{gname}' references unknown fixtures: {unknown}")

        # Validate orders reference known fixtures and contain no duplicates
        for oname, members in self.orders.items():
            unknown = [m for m in members if m not in fixture_set]
            if unknown:
                raise ValueError(f"Order '{oname}' references unknown fixtures: {unknown}")
            if len(set(members)) != len(members):
                raise ValueError(f"Order '{oname}' contains duplicates: {members}")

        # Validate role bindings reference known fixtures
        for fx in self.role_bindings.keys():
            if fx not in fixture_set:
                raise ValueError(f"role_bindings references unknown fixture '{fx}'")

        # Convenience: default ALL group if omitted
        if SemanticGroup.ALL not in self.groups:
            self.groups[SemanticGroup.ALL] = list(self.fixtures)

        return self

    # Lightweight helpers (no side effects)
    def resolve_group(self, group: SemanticGroup) -> list[str]:
        """Return fixture ids for a semantic group."""
        if group not in self.groups:
            raise KeyError(f"Unknown group '{group}'")
        return list(self.groups[group])

    def resolve_order(self, order: OrderMode, fixtures: list[str] | None = None) -> list[str]:
        """Return fixture ids for an order.

        If `fixtures` is provided, returns the order filtered to that subset.
        """
        if order not in self.orders:
            raise KeyError(f"Unknown order '{order}'")
        ordered = list(self.orders[order])
        if fixtures is None:
            return ordered
        fixture_set = set(fixtures)
        return [fx for fx in ordered if fx in fixture_set]
```

---

## 9. Best Practices

### 9.1 Naming Conventions

**Rig IDs:**
- Use snake_case
- Include fixture count
- Include location/purpose
- Examples: `rooftop_4`, `stage_left_6`, `full_venue_16`

**Fixture IDs:**
- Prefix with type: `mh_` (moving head), `par_` (par can)
- Number sequentially: `mh1`, `mh2`, `mh3`
- Or location-based: `mh_front_left`, `mh_back_center`

**Group Names:**
- Use UPPER_CASE - Defined by SemanticGroup

### 9.2 Calibration Workflow

1. **Measure physical ranges:**
   - Pan full sweep (note min/max DMX where mechanical stops occur)
   - Tilt full range (avoid hitting floor/ceiling)
   - Center positions (straight ahead = ?)

2. **Set conservative limits:**
   - Leave 5-10% margin from mechanical limits
   - Better to have smaller range than fixture damage

3. **Test pose tokens:**
   - Set all fixtures to "CENTER" → should point straight ahead
   - Set to "WIDE_LEFT" / "WIDE_RIGHT" → should fan evenly
   - Adjust token values if feel is wrong

4. **Validate dimmer floor:**
   - Set to 0 and observe (some fixtures flicker/cut out)
   - Find minimum stable value (usually 20-40 DMX)
   - Account for venue ambient light

---

## 10. Testing & Validation

### 10.1 Rig Profile Validation

```python
import pytest
from pydantic import ValidationError

def test_rig_profile_valid():
    """Valid rig profile loads successfully."""
    rig = RigProfile(
        rig_id="test_rig",
        name="Test Rig",
        fixtures=["mh1", "mh2"],
        role_bindings={"mh1": "LEFT", "mh2": "RIGHT"},
        groups={"ALL": ["mh1", "mh2"]},
        orders={"LEFT_TO_RIGHT": ["mh1", "mh2"]},
        calibration={...}
    )
    assert rig.rig_id == "test_rig"

def test_rig_profile_invalid_fixture_reference():
    """Rig profile rejects unknown fixture in groups."""
    with pytest.raises(ValidationError, match="unknown fixtures"):
        RigProfile(
            fixtures=["mh1"],
            groups={"ALL": ["mh1", "mh2"]},  # mh2 not in fixtures
            ...
        )

def test_template_rig_compatibility():
    """Template requires roles that rig provides."""
    template = Template(roles=["LEFT", "RIGHT"], ...)
    rig = RigProfile(
        role_bindings={"mh1": "LEFT", "mh2": "RIGHT"},
        ...
    )
    
    errors = validate_template_rig_compatibility(template, rig)
    assert len(errors) == 0
```

### 10.2 Calibration Tests

```python
def test_pose_token_resolution():
    """Pose tokens map to correct DMX ranges."""
    rig = load_rig_profile("test_rig.json")
    
    # CENTER should map to fixture pan_center
    center_dmx = resolve_pan_token("CENTER", "mh1", rig)
    assert center_dmx == rig.calibration.fixtures["mh1"].pan_center
    
    # WIDE_LEFT should map to low end of range
    wide_left_dmx = resolve_pan_token("WIDE_LEFT", "mh1", rig)
    assert wide_left_dmx < center_dmx

def test_phase_offset_computation():
    """Phase offsets distribute correctly across order."""
    rig = load_rig_profile("rooftop_4.json")
    
    offsets = compute_phase_offsets(
        group_fixtures=["mh1", "mh2", "mh3", "mh4"],
        order="LEFT_TO_RIGHT",
        rig=rig,
        spread_bars=1.0
    )
    
    assert offsets["mh1"] == 0.0      # First
    assert offsets["mh4"] == 1.0      # Last
    assert offsets["mh2"] < offsets["mh3"]  # Sequential
```

---

## Summary

Rig profiles provide:

✅ **Separation of Concerns**: Choreography (templates) vs. hardware (rigs)  
✅ **Portability**: Same template on different rigs  
✅ **Calibration**: Per-fixture limits and safety  
✅ **Flexibility**: Multiple groups/orders for varied targeting  
✅ **Type Safety**: Pydantic validation at load time  
✅ **Maintainability**: JSON config, no code changes

**Next Section**: Logical Architecture & Process (how templates + rigs compile to output)
