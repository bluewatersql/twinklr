# Next Sprint Design Specs

Date: 2026-02-17  
Owner: Core Pipeline / Display Rendering / Asset System

## 1) Sprint Scope

### In Scope
- Config standardization, optimization, and cleanup
  - No public interface/model changes for existing config models
  - Simplify JSON/env loading path and precedence behavior
- Cache handling standardization
  - Ensure typed model invariance at stage boundaries
- Asset catalog lifecycle contract (global environment-scoped source of truth)
- Renderer integration against catalog-referenced assets
- Packaging contract for xLights import format (`.xsqz`)
- Remaining Wave handlers (Fireworks, Butterfly, Shimmer standalone, Bars)
- Media effects wave (Wave 4) in scope:
  - Video handler path
  - Faces handler path via phoneme timing track resolution
  - Shader handler path with catalog/manual registration integration

### Out of Scope (This Sprint)
- Breaking schema changes to existing config/planning/public models
- Full lip-sync synthesis pipeline beyond phoneme timing track mapping
- Distributed/shared remote catalog service (this sprint is local environment scoped)

## 2) Lifecycle Decisions (Approved)

1. Asset catalog captures and tracks stable IDs and media metadata.
2. Asset catalog is the basis for file/media tracking.
3. Renderer uses local paths for validation/dev; packaging handles portability/export.
4. Catalog is populated by:
   - Creator agent (PNGs now; videos/GIFs future)
   - Manual registration flow (shader/video/etc) with required metadata/taxonomy
5. Renderer builds sequence from plan references to catalog instances (`asset_id`).
6. Packaging produces xLights sequence import package (`.xsqz`) with required structure.
7. Cleanup is minimal: no temp-heavy lifecycle; local catalog assets persist; package is self-contained.
8. Faces/lip-sync dependency is phoneme timing track resolution (no extra special pipeline required this sprint).

## 3) Design Specs

## A. Config Standardization, Optimization, Cleanup

### Goals
- Preserve existing config model interfaces.
- Consolidate loader flow and env overlay behavior.
- Make precedence deterministic and testable.

### Design
- Internal pipeline:
  1. Read file (`json`/`yaml`) -> raw dict
  2. Validate -> typed model
  3. Apply env overlay only for `None` fields
- Keep public entrypoints stable (`load_app_config`, `load_job_config`, `load_fixture_group`, `load_full_config`).
- Optional `.env` bootstrap if supported by installed deps; fallback remains `os.getenv`.

### Acceptance Criteria
- No public signature/model changes.
- Existing tests remain green.
- New tests cover env precedence and env bootstrap behavior.

## B. Cache Handling: Typed Model Invariance

### Goals
- Remove repetitive dict-vs-model branching at stage boundaries.
- Guarantee downstream code receives typed models.

### Design
- Add shared normalization helper:
  - model -> pass through
  - dict -> `model_validate`
  - otherwise -> typed error
- Apply helper in stage/orchestration boundaries where mixed payloads are currently accepted.
- Keep cache backend contract unchanged (`load -> model | None`).

### Acceptance Criteria
- Boundary code normalizes to typed models.
- Reduced `isinstance(..., dict)` branching in pipeline paths.

## C. Asset Catalog: Source-of-Truth Contract

### Identity and Tracking
- `asset_id` is stable identity (global within local environment).
- Plans reference `asset_id`; they do not directly own raw file paths.

### Minimum Metadata Contract
- Identity/provenance:
  - `asset_id`, `source` (`creator_agent` | `manual_registration`), `created_at`, `source_plan_id` (if applicable)
- Media description:
  - `asset_type` (image/video/gif/shader/text), `category`, taxonomy tags
- File tracking:
  - `file_path`, `content_hash`, `file_size_bytes`
- Runtime/export hints:
  - `status`, `has_alpha` (if image), dimensions/duration where relevant
- Optional future optimization fields:
  - `embedding`, semantic lookup fields

### Population Paths
- Creator agent:
  - Current: PNG assets
  - Future in this wave: video/GIF capable entries
- Manual registration (new):
  - For shader/video/externally produced assets
  - Requires taxonomy + metadata capture policy

### Manual Registration Metadata (Initial)
- Required:
  - `asset_id` (or deterministic generated id)
  - `asset_type`
  - `file_path`
  - `content_hash`
  - `title`/`description`
  - `tags` (taxonomy)
  - `license_mode` + attribution fields
- Optional:
  - motif/theme linkage
  - palette hints
  - usage constraints

### Acceptance Criteria
- Catalog supports both creator and manual-registration sources.
- Renderer can resolve all planned asset references via catalog ID.

## D. Renderer Contract (Catalog-Backed)

### Design
- Group plan contains asset references by `asset_id`.
- Renderer resolves `asset_id -> catalog entry -> local file_path`.
- Renderer writes effects using resolved local paths for validation and local run behavior.

### Pathing Rule
- Local path correctness is primary in renderer.
- Portable/exported path translation is packaging responsibility.

### Acceptance Criteria
- Missing catalog entries surface deterministic warnings/errors.
- Render output shows correct effect params derived from resolved local path.

## E. Packaging Contract (`.xsqz`)

### Format
`<sequence_name>.xsqz` (zip) containing:
- `_lost/` -> all non-shader media assets required by sequence
- `Shaders/` -> `*.fs` shader files (if any)
- `<sequence_name>.xsq` -> rendered sequence
- `xlights_networks.xml` -> placeholder this sprint
- `xlights_rgbeffects.xml` -> placeholder this sprint
- `license.txt` -> generated plain-text license + provenance/legal metadata

### Packaging Flow
1. Collect all referenced catalog assets from rendered sequence.
2. Copy assets:
   - non-shader -> `_lost/`
   - shader -> `Shaders/`
3. Place renderer output `.xsq` and placeholder xml files.
4. Emit `license.txt` with generation metadata (agent/source/date/usage restrictions).
5. Zip to `.xsqz`.

### Acceptance Criteria
- Package is self-contained for sequence import.
- All referenced assets are present in expected folders.
- License file generated with required metadata fields.

## F. Cleanup Policy

### Design
- Avoid temporary artifact sprawl by default.
- Persist local catalog-backed assets.
- Treat package output as immutable self-contained export artifact.

### Acceptance Criteria
- No mandatory temp cleanup phase required for normal operation.
- Repeated runs can reuse catalog assets safely.

## G. Media Effects Wave (Wave 4) - In Scope

### Scope for this sprint
- Implement media-effect integration using the lifecycle above.
- Include initial support paths for:
  - `Video`
  - `Faces` (resolved to phoneme timing track)
  - `Shader`

### Design Constraints
- Effects resolve via catalog IDs and local file paths.
- Faces uses existing phoneme timing track data; no additional special subsystem required now.
- Shader files can be provided by creator path or manual registration.

### Acceptance Criteria
- End-to-end tests demonstrate:
  - Catalog-referenced media can be rendered into sequence settings.
  - Faces effect receives/uses phoneme timing references.
  - Packaging includes media/shader assets in required directories.

## H. Remaining Handler Coverage (Wave 3B)

### In-Scope Handlers
- Fireworks
- Butterfly
- Shimmer (standalone)
- Bars

### Acceptance Criteria
- Resolver maps relevant motifs/templates to these handlers.
- Handler tests cover parameter serialization and fallback/warning behavior.

## 4) Implementation Plan (Order)

1. Config + typed boundary normalization
2. Catalog contract and manual registration schema/flow
3. Renderer catalog dereference hardening
4. `.xsqz` packager implementation
5. Wave 3B handlers
6. Wave 4 media handlers (Video/Faces/Shader) wired to catalog + packaging
7. E2E validation across render + package

## 5) Risks and Mitigations

- Risk: Catalog metadata too weak for manual assets.
  - Mitigation: enforce required registration fields with validation errors.
- Risk: Path mismatch between local render and packaged export.
  - Mitigation: explicit packaging rewrite/copy policy and tests.
- Risk: Faces timing mismatch.
  - Mitigation: validate phoneme track availability at compile time with explicit diagnostics.

## 6) Definition of Done

- Lifecycle contract implemented and documented.
- Renderer and packaging use catalog references as the canonical source.
- `.xsqz` export structure produced exactly as specified.
- Wave 3B handlers shipped with tests.
- Wave 4 media effects included in sprint deliverables with E2E coverage.
