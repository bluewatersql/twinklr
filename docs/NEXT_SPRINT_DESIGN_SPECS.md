# Next Sprint Design Specs

Date: 2026-02-16 (updated 2026-02-17)  
Owner: Core Pipeline / Display Rendering

## 1) Sprint Scope

### In Scope
- Config standardization, optimization, and cleanup
  - Keep existing public interfaces/models unchanged
  - Simplify JSON + env config loading path
- Cache model invariance (always return typed model at call sites)
- **LLM Provider unification: embedding and image generation interfaces**
  - Add embedding methods to `LLMProvider` protocol and `OpenAIProvider`
  - Promote image generation from standalone client to provider-level interface
  - Eliminate private-attribute leaks (`provider._async_client`) at call sites
- Semantic asset dedup design (embedding-backed reuse, consuming new provider embeddings)
- Multi-layer rendering validation (procedural + Pictures overlay)
- Remaining Wave handlers for effect coverage (Fireworks, Butterfly, Shimmer standalone, Bars)

### Out of Scope (This Sprint)
- Wave 4 media handlers (Video, Faces, Shader) implementation
- Lip-sync pipeline or media file-management subsystem
- Breaking schema changes to config or planning models
- Non-OpenAI provider implementations (Anthropic embedding/image)

## 2) Current State Snapshot

- Config loading is split across JSON/YAML load + env overlay in `packages/twinklr/core/config/loader.py`.
- Cache backends already deserialize to Pydantic models (`FSCache.load`), but dict-vs-model handling still appears at stage/orchestrator boundaries.
- `CatalogEntry.embedding` exists but is not populated or queried.
- Procedural + Pictures overlay plumbing exists in composition and unit tests; end-to-end validation at pipeline output level is still limited.
- Handler set is broad, but Wave backlog still calls out remaining coverage and quality hardening.
- **`LLMProvider` protocol defines only text/JSON generation methods.** Image generation lives in `OpenAIImageClient` — a separate class that wraps `AsyncOpenAI` directly, bypassing the provider abstraction. `AssetCreationStage._build_image_client()` reaches into `provider._async_client` (a private attribute) to build the image client, creating a tight coupling to the OpenAI implementation.
- **No embedding support exists anywhere in the provider layer.** The `CatalogEntry.embedding` field is typed but never populated.

---

## 3) Design Specs

## A. Config Standardization, Optimization, Cleanup

### Goals
- Keep `AppConfig`, `JobConfig`, and fixture model interfaces unchanged.
- Reduce duplicated load/validate/env logic.
- Make env precedence explicit and testable.

### Design
- Introduce a single internal config pipeline:
  1. `read file -> raw dict`
  2. `validate raw dict -> pydantic model`
  3. `apply env overlays -> model_copy(update=...)`
- Keep existing public functions (`load_app_config`, `load_job_config`, `load_fixture_group`, `load_full_config`) intact.
- Add optional `.env` bootstrap support in loader init path (non-breaking):
  - If python-dotenv available, load once.
  - If unavailable, continue current `os.getenv` behavior.
- Add explicit env precedence rule:
  - If config field is set, do not overwrite from env.
  - If config field is `None`, use env if present.

### Proposed Files
- `packages/twinklr/core/config/loader.py` (refactor internals only)
- `tests/unit/config/test_loader.py` (precedence + env bootstrap tests)

### Acceptance Criteria
- No public config model or function signature changes.
- Existing config tests pass.
- New tests cover env precedence and optional `.env` bootstrap behavior.

---

## B. Cache Handling: Typed Model Invariance

### Problem
Some call paths still branch on `dict` vs model after cache/orchestrator boundaries, creating repetitive checks and inconsistent typing.

### Goals
- Cache consumers receive the same typed model consistently.
- Minimize repeated `isinstance(x, dict)` guards in pipeline stages.

### Design
- Add a normalization helper for boundary inputs:
  - `normalize_model(value, model_type) -> model_type`
  - Behavior:
    - model instance -> return as-is
    - dict -> `model_type.model_validate(dict)`
    - otherwise -> `TypeError`
- Apply helper at stage/orchestrator entry points where mixed payloads are currently tolerated.
- Keep cache backend contract unchanged (`Cache.load(key, model_cls) -> model | None`).

### Proposed Files
- New: `packages/twinklr/core/pipeline/model_normalization.py`
- `packages/twinklr/core/pipeline/stage.py` (use helper in `resolve_typed_input` path)
- `packages/twinklr/core/pipeline/execution.py` and relevant stage modules (remove repetitive dict/model branching)
- Unit tests in `tests/unit/pipeline/`

### Acceptance Criteria
- Core stage boundaries normalize into typed models.
- Reduced direct dict/model branching in pipeline code paths.
- No changes to external pipeline stage interface signatures.

---

## C. LLM Provider Interface: Embedding and Image Generation

### Problem

The `LLMProvider` protocol currently exposes only text/JSON generation methods. Two critical capabilities sit outside the provider abstraction:

1. **Image generation** — `OpenAIImageClient` wraps `AsyncOpenAI` directly. The `AssetCreationStage` accesses the provider's private `_async_client` attribute via `hasattr(provider, "_async_client")` to construct the image client. This violates the provider abstraction, prevents non-OpenAI providers from supporting image generation, and makes the image path untraceable through the standard provider token-tracking and logging infrastructure.

2. **Embeddings** — No embedding support exists. The `CatalogEntry.embedding` field is typed `list[float] | None` but never populated. The upcoming semantic dedup feature (Spec D) requires embedding generation routed through the provider.

### Goals

- Add embedding and image generation as first-class capabilities on `LLMProvider`.
- Route all OpenAI API calls (text, embedding, image) through a single provider instance.
- Eliminate private-attribute access (`provider._async_client`) at call sites.
- Maintain provider-level token tracking, retry logic, and logging for all call types.
- Keep existing `OpenAIImageClient` as an internal implementation detail of `OpenAIProvider`.
- Introduce capability detection so callers degrade gracefully when a provider does not support a given capability.

### C.1 New Base Types (`providers/base.py`)

Add the following frozen dataclasses alongside existing `TokenUsage`, `ResponseMetadata`, `LLMResponse`:

```python
@dataclass(frozen=True)
class EmbeddingResponse:
    """Standardized embedding response.

    Attributes:
        embedding: Dense float vector.
        model: Model that produced the embedding.
        token_usage: Tokens consumed by the embedding request.
        dimensions: Length of the embedding vector.
    """
    embedding: list[float]
    model: str
    token_usage: TokenUsage
    dimensions: int


@dataclass(frozen=True)
class ImageGenerationResponse:
    """Standardized image generation response.

    Wraps the result from the underlying image API into
    a provider-agnostic format. File writing and post-processing
    remain the caller's responsibility (or a helper's).

    Attributes:
        image_bytes: Raw image bytes (PNG).
        content_hash: SHA-256 hex digest of image_bytes.
        model: Model that generated the image.
        token_usage: Tokens consumed (if applicable; zeros for image-only APIs).
        width: Generated image width in pixels.
        height: Generated image height in pixels.
    """
    image_bytes: bytes
    content_hash: str
    model: str
    token_usage: TokenUsage
    width: int
    height: int
```

### C.2 Provider Capability Enum (`providers/base.py`)

```python
class ProviderCapability(str, Enum):
    """Capabilities a provider may support.

    Used for runtime capability detection so callers can
    degrade gracefully without isinstance checks.
    """
    TEXT_GENERATION = "text_generation"
    EMBEDDING = "embedding"
    IMAGE_GENERATION = "image_generation"
```

### C.3 Updated `LLMProvider` Protocol (`providers/base.py`)

Extend the existing protocol with embedding, image, and capability methods. All new methods follow the existing async-first pattern (async is primary, sync is optional backward-compat wrapper).

```python
class LLMProvider(Protocol):
    """Generic protocol for LLM providers.

    Implementations must handle:
    - Provider-level retries (network errors, rate limits, 5xx)
    - Conversation state management
    - Token usage tracking
    - JSON response parsing
    - Embedding generation (when supported)
    - Image generation (when supported)

    Capability Detection:
        Callers should check `supports(capability)` before invoking
        embedding or image methods. Text generation is always supported.
    """

    # --- Existing methods (unchanged) ---
    @property
    def provider_type(self) -> ProviderType: ...

    def generate_json(self, messages, model, temperature=None, **kwargs) -> LLMResponse: ...
    def generate_json_with_conversation(self, ...) -> LLMResponse: ...
    def add_message_to_conversation(self, ...) -> None: ...
    def get_conversation_history(self, ...) -> list[dict[str, str]]: ...
    def get_token_usage(self) -> TokenUsage: ...
    def reset_token_tracking(self) -> None: ...
    async def generate_json_async(self, ...) -> LLMResponse: ...
    async def generate_json_with_conversation_async(self, ...) -> LLMResponse: ...

    # --- NEW: Capability detection ---

    def supports(self, capability: ProviderCapability) -> bool:
        """Check whether this provider supports a given capability.

        All providers MUST support TEXT_GENERATION.
        EMBEDDING and IMAGE_GENERATION are optional.

        Args:
            capability: The capability to check.

        Returns:
            True if the provider supports the capability.
        """
        ...

    # --- NEW: Embedding methods ---

    async def generate_embedding_async(
        self,
        text: str,
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> EmbeddingResponse:
        """Generate an embedding vector for the given text.

        Provider handles retries for transient errors (same policy
        as generate_json_async).

        Args:
            text: Input text to embed.
            model: Embedding model identifier. If None, the provider
                   uses its configured default (e.g. "text-embedding-3-small").
            dimensions: Optional output dimensionality. If None, uses the
                        model's native dimensionality.

        Returns:
            EmbeddingResponse with float vector and metadata.

        Raises:
            LLMProviderError: On unrecoverable errors after retries.
            NotImplementedError: If provider does not support embeddings.
        """
        ...

    def generate_embedding(
        self,
        text: str,
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> EmbeddingResponse:
        """Sync wrapper for generate_embedding_async.

        Args:
            text: Input text to embed.
            model: Embedding model identifier (None -> provider default).
            dimensions: Optional output dimensionality.

        Returns:
            EmbeddingResponse with float vector and metadata.

        Raises:
            LLMProviderError: On unrecoverable errors after retries.
            NotImplementedError: If provider does not support embeddings.
        """
        ...

    async def generate_embedding_batch_async(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[EmbeddingResponse]:
        """Generate embeddings for multiple texts in a single API call.

        Providers that support native batching (e.g. OpenAI) should
        send all texts in one request. Others may iterate internally.

        Args:
            texts: List of input texts.
            model: Embedding model identifier (None -> provider default).
            dimensions: Optional output dimensionality.

        Returns:
            List of EmbeddingResponse, one per input text (order preserved).

        Raises:
            LLMProviderError: On unrecoverable errors after retries.
            NotImplementedError: If provider does not support embeddings.
        """
        ...

    # --- NEW: Image generation methods ---

    async def generate_image_async(
        self,
        prompt: str,
        *,
        model: str | None = None,
        width: int = 1024,
        height: int = 1024,
        background: str = "transparent",
        output_format: str = "png",
    ) -> ImageGenerationResponse:
        """Generate an image from a text prompt.

        Returns raw image bytes and metadata. File writing, resizing,
        and cataloging are the caller's responsibility.

        Provider handles retries for transient errors (same policy
        as generate_json_async).

        Args:
            prompt: Image generation prompt.
            model: Image model identifier. If None, the provider uses
                   its configured default (e.g. "gpt-image-1.5").
            width: Target image width in pixels.
            height: Target image height in pixels.
            background: Background mode ("transparent" or "opaque").
            output_format: Output format ("png", "webp", "jpeg").

        Returns:
            ImageGenerationResponse with raw bytes and metadata.

        Raises:
            LLMProviderError: On unrecoverable errors after retries.
            NotImplementedError: If provider does not support image generation.
        """
        ...

    def generate_image(
        self,
        prompt: str,
        *,
        model: str | None = None,
        width: int = 1024,
        height: int = 1024,
        background: str = "transparent",
        output_format: str = "png",
    ) -> ImageGenerationResponse:
        """Sync wrapper for generate_image_async.

        Args:
            prompt: Image generation prompt.
            model: Image model identifier (None -> provider default).
            width: Target image width in pixels.
            height: Target image height in pixels.
            background: Background mode.
            output_format: Output format.

        Returns:
            ImageGenerationResponse with raw bytes and metadata.

        Raises:
            LLMProviderError: On unrecoverable errors after retries.
            NotImplementedError: If provider does not support image generation.
        """
        ...

```

### C.4 `OpenAIProvider` Implementation (`providers/openai.py`)

#### Constructor Changes

```python
class OpenAIProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        session_id: str | None = None,
        timeout: float = 300.0,
        base_url: str | None = None,
        # NEW defaults (overridable via AppConfig)
        default_embedding_model: str = "text-embedding-3-small",
        default_image_model: str = "gpt-image-1.5",
    ):
        # ... existing init ...
        self._default_embedding_model = default_embedding_model
        self._default_image_model = default_image_model
```

#### `supports()` Implementation

```python
    def supports(self, capability: ProviderCapability) -> bool:
        """OpenAI supports all three capabilities."""
        return capability in {
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.EMBEDDING,
            ProviderCapability.IMAGE_GENERATION,
        }
```

#### Embedding Methods

```python
    async def generate_embedding_async(
        self,
        text: str,
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> EmbeddingResponse:
        """Generate embedding via OpenAI Embeddings API.

        Uses self._async_client.embeddings.create() with retry logic
        consistent with generate_json_async.

        Args:
            text: Input text to embed.
            model: Model name (default: self._default_embedding_model).
            dimensions: Output dimensions (None -> model native).

        Returns:
            EmbeddingResponse.

        Raises:
            LLMProviderError: After retries exhausted.
        """
        resolved_model = model or self._default_embedding_model
        params: dict[str, Any] = {
            "input": text,
            "model": resolved_model,
        }
        if dimensions is not None:
            params["dimensions"] = dimensions

        response = None
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = await self._async_client.embeddings.create(**params)
                break
            except Exception as error:
                if not self._should_retry_async_error(error, attempt, max_attempts):
                    raise LLMProviderError(f"Embedding error: {error}") from error
                await asyncio.sleep(0.5 * (2 ** attempt))

        if response is None:
            raise LLMProviderError("No response from OpenAI Embeddings API")

        data = response.data[0]
        token_usage = TokenUsage(
            prompt_tokens=getattr(response.usage, "prompt_tokens", 0),
            completion_tokens=0,
            total_tokens=getattr(response.usage, "total_tokens", 0),
        )
        self._update_token_usage(
            prompt_tokens=token_usage.prompt_tokens,
            completion_tokens=0,
            total_tokens=token_usage.total_tokens,
        )

        return EmbeddingResponse(
            embedding=data.embedding,
            model=resolved_model,
            token_usage=token_usage,
            dimensions=len(data.embedding),
        )

    def generate_embedding(self, text, *, model=None, dimensions=None) -> EmbeddingResponse:
        """Sync wrapper using asyncio.run()."""
        return asyncio.run(
            self.generate_embedding_async(text, model=model, dimensions=dimensions)
        )

    async def generate_embedding_batch_async(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> list[EmbeddingResponse]:
        """Batch embedding via single OpenAI API call.

        OpenAI natively supports list[str] input, returning one
        embedding per input in order.

        Args:
            texts: List of input texts.
            model: Model name (default: self._default_embedding_model).
            dimensions: Output dimensions (None -> model native).

        Returns:
            List of EmbeddingResponse (order matches input).
        """
        resolved_model = model or self._default_embedding_model
        params: dict[str, Any] = {
            "input": texts,
            "model": resolved_model,
        }
        if dimensions is not None:
            params["dimensions"] = dimensions

        response = None
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = await self._async_client.embeddings.create(**params)
                break
            except Exception as error:
                if not self._should_retry_async_error(error, attempt, max_attempts):
                    raise LLMProviderError(f"Batch embedding error: {error}") from error
                await asyncio.sleep(0.5 * (2 ** attempt))

        if response is None:
            raise LLMProviderError("No response from OpenAI Embeddings API (batch)")

        token_usage = TokenUsage(
            prompt_tokens=getattr(response.usage, "prompt_tokens", 0),
            completion_tokens=0,
            total_tokens=getattr(response.usage, "total_tokens", 0),
        )
        self._update_token_usage(
            prompt_tokens=token_usage.prompt_tokens,
            completion_tokens=0,
            total_tokens=token_usage.total_tokens,
        )

        results: list[EmbeddingResponse] = []
        for item in sorted(response.data, key=lambda d: d.index):
            results.append(EmbeddingResponse(
                embedding=item.embedding,
                model=resolved_model,
                token_usage=token_usage,  # shared across batch
                dimensions=len(item.embedding),
            ))
        return results
```

#### Image Generation Methods

Internally delegates to the existing `OpenAIImageClient` logic (retry, base64 decode, size selection) but returns raw bytes instead of writing to disk. The existing `_process_image_bytes` helper moves to a standalone utility; `OpenAIImageClient` is retained as an internal implementation detail.

```python
    async def generate_image_async(
        self,
        prompt: str,
        *,
        model: str | None = None,
        width: int = 1024,
        height: int = 1024,
        background: str = "transparent",
        output_format: str = "png",
    ) -> ImageGenerationResponse:
        """Generate image via OpenAI Images API.

        Handles API-size selection, retry, base64 decode, and hashing.
        Does NOT write to disk or resize -- those are caller responsibilities.

        Args:
            prompt: Image generation prompt.
            model: Model name (default: self._default_image_model).
            width: Target width for API size selection.
            height: Target height for API size selection.
            background: "transparent" or "opaque".
            output_format: "png", "webp", or "jpeg".

        Returns:
            ImageGenerationResponse with raw PNG bytes.

        Raises:
            LLMProviderError: After retries exhausted.
        """
        resolved_model = model or self._default_image_model
        api_size = _select_api_size(width, height)

        last_error: Exception | None = None
        max_attempts = 3
        delay = 2.0

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._async_client.images.generate(
                    model=resolved_model,
                    prompt=prompt,
                    n=1,
                    size=api_size,
                    output_format=output_format,
                    background=background,
                )

                if not response.data:
                    raise LLMProviderError("Images API returned empty data list")
                b64_data = response.data[0].b64_json
                if not b64_data:
                    raise LLMProviderError("Images API returned empty b64_json")

                raw_bytes = base64.b64decode(b64_data)
                content_hash = hashlib.sha256(raw_bytes).hexdigest()

                # Parse actual dimensions from returned image
                img = Image.open(BytesIO(raw_bytes))
                actual_w, actual_h = img.size

                return ImageGenerationResponse(
                    image_bytes=raw_bytes,
                    content_hash=content_hash,
                    model=resolved_model,
                    token_usage=TokenUsage(),  # Images API does not report tokens
                    width=actual_w,
                    height=actual_h,
                )

            except _RETRYABLE_ERRORS as e:
                last_error = e
                if attempt < max_attempts:
                    await asyncio.sleep(delay)
                    delay *= 2.0

            except LLMProviderError:
                raise
            except Exception as e:
                raise LLMProviderError(
                    f"Image generation failed (non-retryable): {e}"
                ) from e

        raise LLMProviderError(
            f"Image generation failed after {max_attempts} retries: {last_error}"
        )

    def generate_image(self, prompt, **kwargs) -> ImageGenerationResponse:
        """Sync wrapper using asyncio.run()."""
        return asyncio.run(self.generate_image_async(prompt, **kwargs))
```

### C.5 Configuration Additions (`config/models.py`)

Add default model names to `AppConfig` so they are configurable without code changes:

```python
class AppConfig(ConfigBase):
    # ... existing fields ...

    # NEW: default model identifiers for non-text capabilities
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Default embedding model for semantic similarity",
    )
    image_model: str = Field(
        default="gpt-image-1.5",
        description="Default image generation model",
    )
```

Update the provider factory to forward these to `OpenAIProvider`:

```python
def create_llm_provider(app_config: AppConfig, session_id: str) -> LLMProvider:
    provider_name = app_config.llm_provider.lower().strip()
    if provider_name == "openai":
        return OpenAIProvider(
            api_key=app_config.llm_api_key,
            session_id=session_id,
            base_url=app_config.llm_base_url,
            default_embedding_model=app_config.embedding_model,
            default_image_model=app_config.image_model,
        )
    raise ValueError(f"Unknown LLM provider: {app_config.llm_provider}")
```

### C.6 `AssetCreationStage` Migration

Replace the private-attribute access pattern with the provider-level image method:

**Before (current):**
```python
def _build_image_client(self, context: PipelineContext) -> OpenAIImageClient | None:
    provider = context.provider
    if hasattr(provider, "_async_client"):
        client = provider._async_client  # abstraction leak
    else:
        client = _create_openai_client()
    return OpenAIImageClient(client)
```

**After (proposed):**
```python
async def _generate_image(
    self,
    context: PipelineContext,
    spec: AssetSpec,
    output_path: Path,
) -> ImageResult:
    """Generate an image asset via the provider's image API.

    Falls back gracefully if the provider does not support image generation.

    Args:
        context: Pipeline context with provider.
        spec: Asset spec with enriched prompt.
        output_path: Path to write the generated file.

    Returns:
        ImageResult with file metadata.

    Raises:
        RuntimeError: If provider lacks image capability and no fallback.
    """
    provider = context.provider
    if not provider.supports(ProviderCapability.IMAGE_GENERATION):
        raise RuntimeError("Provider does not support image generation")

    response = await provider.generate_image_async(
        prompt=spec.prompt,
        width=spec.width,
        height=spec.height,
        background=spec.background.value,
    )

    # Post-process: resize if API dimensions differ from target, write to disk
    result = _process_and_write(
        response.image_bytes, spec.width, spec.height, output_path
    )
    return result
```

The `_process_and_write` helper is extracted from the existing `_process_image_bytes` in `image_client.py` into a shared utility (or kept inline in the stage).

### C.7 Image Client Retention and Deprecation Path

`OpenAIImageClient` is **not deleted** this sprint. It is retained as an internal implementation detail within `OpenAIProvider.generate_image_async()` if desired, or can remain as a standalone utility for any code paths that need file-write-included convenience. The public-facing contract for pipeline stages moves to `provider.generate_image_async()`.

Direct construction of `OpenAIImageClient` from `provider._async_client` at call sites is **deprecated** and will be removed in the following sprint.

### Proposed Files
- `packages/twinklr/core/agents/providers/base.py` (new types + protocol methods)
- `packages/twinklr/core/agents/providers/openai.py` (embedding + image implementation)
- `packages/twinklr/core/agents/providers/factory.py` (forward new config fields)
- `packages/twinklr/core/config/models.py` (add `embedding_model`, `image_model` to `AppConfig`)
- `packages/twinklr/core/agents/assets/stage.py` (migrate to `provider.generate_image_async`)
- `packages/twinklr/core/agents/assets/image_client.py` (extract `_process_image_bytes` to shared util)
- `tests/unit/agents/providers/test_openai_embedding.py` (embedding unit tests)
- `tests/unit/agents/providers/test_openai_image.py` (image unit tests)
- `tests/unit/agents/providers/test_capability.py` (capability detection tests)
- `tests/unit/agents/assets/test_stage_image_provider.py` (stage migration tests)

### Acceptance Criteria
- `LLMProvider` protocol includes `supports()`, embedding, and image methods.
- `OpenAIProvider` implements all new methods with retry logic and token tracking.
- `AssetCreationStage` uses `provider.generate_image_async()` — zero `hasattr` / private attribute access.
- Existing image generation behavior (retry, resize, hash) is preserved.
- Embedding responses include vector, model name, token usage, and dimensions.
- Batch embedding uses a single OpenAI API call (not N sequential calls).
- Provider factory forwards `embedding_model` and `image_model` from `AppConfig`.
- All new methods have unit tests with mocked OpenAI client.
- Capability detection returns correct values for OpenAI provider.
- Callers that attempt unsupported capabilities receive `NotImplementedError`.

---

## D. Semantic Asset Dedup (Embedding-backed)

### Goals
- Populate `CatalogEntry.embedding` for generated/reused assets.
- Add similarity-based reuse in addition to exact prompt hash reuse.
- **Consume the new `LLMProvider.generate_embedding_async` / `generate_embedding_batch_async` methods from Spec C.**

### Design
- Create deterministic embedding input text from `AssetSpec`:
  - `theme_id`, `motif_id`, `narrative_subject`, `narrative_description`, `style_tags`, `content_tags`, palette hints.
- Generate embedding at catalog write time for non-failed entries **via `provider.generate_embedding_async()`**.
- Embedding model is resolved from `AppConfig.embedding_model` (default: `text-embedding-3-small`).
- Add approximate nearest-neighbor matching policy:
  - Candidate filter by category + key context (theme/motif when available)
  - Cosine similarity threshold gate (initial default conservative, e.g. 0.92)
  - Keep exact hash match as first-pass fast path
- Fail-open behavior:
  - Check `provider.supports(ProviderCapability.EMBEDDING)` before attempting.
  - Embedding generation/search failures do not block asset creation.
  - If embedding fails, `CatalogEntry.embedding` remains `None`; dedup falls back to exact hash only.

### Embedding Integration Flow

```
AssetCreationStage.execute()
  |-- Step 2: check_reuse (exact hash) -- unchanged
  |-- Step 2b (NEW): check_semantic_reuse (embedding similarity)
  |   +-- provider.generate_embedding_async(spec_embedding_text)
  |       +-- cosine_similarity(candidate.embedding, new_embedding)
  |           +-- threshold gate -> reuse or generate
  |-- Step 3: enrich + generate -- unchanged
  +-- Step 5b (NEW): populate embeddings for new entries
      +-- provider.generate_embedding_batch_async(
      |       [spec_embedding_text for entry in new_entries]
      |   )
      +-- entry.embedding = response.embedding
```

### Proposed Helper: `dedup.py`

```python
def build_embedding_text(spec: AssetSpec) -> str:
    """Build deterministic text for embedding generation.

    Concatenates semantic fields in stable order.

    Args:
        spec: Asset specification.

    Returns:
        Embedding input string.
    """
    ...

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    ...

async def find_semantic_match(
    catalog: AssetCatalog,
    spec: AssetSpec,
    provider: LLMProvider,
    *,
    threshold: float = 0.92,
) -> CatalogEntry | None:
    """Find a semantically similar catalog entry.

    Args:
        catalog: Existing catalog.
        spec: Spec to match.
        provider: LLM provider for embedding generation.
        threshold: Minimum cosine similarity for match.

    Returns:
        Best matching CatalogEntry above threshold, or None.
    """
    ...

async def populate_embeddings(
    entries: list[CatalogEntry],
    provider: LLMProvider,
) -> list[CatalogEntry]:
    """Populate embedding field on catalog entries.

    Uses batch embedding for efficiency. Fail-open: entries
    that fail embedding keep embedding=None.

    Args:
        entries: Entries to enrich.
        provider: LLM provider.

    Returns:
        Updated entries (same list, embeddings populated where possible).
    """
    ...
```

### Proposed Files
- `packages/twinklr/core/agents/assets/catalog.py`
- `packages/twinklr/core/agents/assets/stage.py`
- `packages/twinklr/core/agents/assets/models.py` (no schema change required)
- New: `packages/twinklr/core/agents/assets/dedup.py`
- Tests: `tests/unit/agents/assets/test_dedup.py`, `tests/unit/agents/assets/test_catalog.py`, `tests/unit/agents/assets/test_stage.py`

### Acceptance Criteria
- New catalog entries include embeddings when provider supports `EMBEDDING` capability.
- Reuse path attempts semantic match before generating new assets (after exact hash check).
- Batch embedding uses `provider.generate_embedding_batch_async()` (single API call).
- Fallback behavior is deterministic and non-blocking (graceful degradation if embedding fails).
- Cosine similarity threshold is configurable (default conservative at 0.92).
- `CatalogEntry.embedding` field type unchanged (`list[float] | None`).

---

## E. Multi-layer Rendering Validation (Procedural + Asset Overlay)

### Current State
Composition and renderer already support overlay emission when `catalog_index` and `resolved_asset_ids` are present.

### Sprint Goal
Add explicit end-to-end validation from plan input to written XSQ effect output.

### Design
- Add integration test that verifies:
  - Procedural effect + Pictures overlay are both written
  - Same timing window for both events
  - Expected layer indices/blend behavior
  - Asset path is resolved into settings string for Pictures effect
- Keep rendering architecture unchanged.

### Proposed Files
- `tests/integration/test_transitions_multi_layer.py` (extend or add new scenario)
- `tests/unit/sequencer/display/test_renderer_overlay.py` (retain fast checks)

### Acceptance Criteria
- Integration test validates dual-layer output in generated sequence structure.
- No regressions to existing renderer/unit tests.

---

## F. Remaining Wave Handlers (Fireworks, Butterfly, Shimmer, Bars)

### Goals
- Raise effect coverage for planned templates and reduce fallback-to-On behavior.
- Keep handler API consistent with existing effect handler pattern.

### Design
- Implement missing handlers under `display/effects/handlers/` with:
  - Typed parameter parsing with defaults
  - Settings builder serialization
  - Stable handler versioning
  - Warning paths for unsupported/invalid params
- Register handlers in builtin registry and add resolver map coverage.

### Proposed Files
- `packages/twinklr/core/sequencer/display/effects/handlers/fireworks.py`
- `packages/twinklr/core/sequencer/display/effects/handlers/butterfly.py`
- `packages/twinklr/core/sequencer/display/effects/handlers/shimmer.py`
- `packages/twinklr/core/sequencer/display/effects/handlers/bars.py`
- `packages/twinklr/core/sequencer/display/effects/handlers/__init__.py`
- `packages/twinklr/core/sequencer/display/composition/effect_resolver.py`
- Unit tests under `tests/unit/sequencer/display/effects/handlers/`

### Acceptance Criteria
- Effect resolver maps relevant motifs/templates to these handlers without On fallback.
- Each handler has parameter serialization tests and at least one composition-level integration assertion.

---

## G. Wave 4 Media Handlers (Deferred)

### Decision
Defer implementation this sprint.

### Blocking Prerequisites
- Shared media asset file-management lifecycle (copy, reference, cleanup, export)
- Lip-sync/timing alignment contract for Faces
- Shader execution/translation path and safety constraints

### Exit Criteria to Unblock
- Approved media asset storage + export contract
- Timing/phoneme interface finalized for Faces
- Shader runtime target defined (native xLights shader support vs pre-render strategy)

---

## 4) Sprint Plan (Proposed Order)

1. **Config standardization** + tests (low-risk foundational cleanup)
2. **Typed model normalization** at stage boundaries (remove dict/model ambiguity)
3. **LLM Provider interface expansion** (Spec C) — embedding + image methods on protocol and OpenAI provider
4. **AssetCreationStage migration** — consume provider image/embedding APIs, remove `_async_client` access
5. **Multi-layer E2E validation** hardening (lock existing behavior)
6. **Wave handler implementation** + mapping updates
7. **Semantic dedup scaffolding** and guarded rollout (consuming Spec C embeddings)
8. Wave 4 prerequisites tracked only

### Dependency Graph

```
A (Config) ----+
B (Cache)  ----+-- C (Provider Interface) -- D (Semantic Dedup)
               |        |
               |        +-- AssetCreationStage migration
               |
E (Multi-layer Validation)
F (Wave Handlers)
G (Deferred)
```

## 5) Risks and Mitigations

- **Risk:** Hidden call sites rely on dict payloads.
  - Mitigation: Introduce normalization helper first, migrate incrementally, keep strict tests.
- **Risk:** Embedding similarity false positives.
  - Mitigation: Conservative threshold (0.92) + category/theme filters + exact hash first.
- **Risk:** Handler parameter mismatches with xLights expectations.
  - Mitigation: Use settings-builder tests and fixture-based golden assertions.
- **Risk:** Provider protocol expansion breaks existing code that only implements text methods.
  - Mitigation: `supports()` capability check at call sites; `NotImplementedError` default for unsupported capabilities. Existing call sites (agent runner) are unchanged — they only use text methods.
- **Risk:** Image generation behavior changes during provider migration.
  - Mitigation: Retain `OpenAIImageClient` as internal helper during transition. Add integration tests comparing old and new paths with identical prompts. `_process_image_bytes` logic is extracted, not rewritten.
- **Risk:** Embedding API costs are unbounded during catalog writes.
  - Mitigation: Batch API reduces call count. Embedding is opt-in (fail-open). Add per-job token budget tracking for embedding calls via existing provider token tracking.

## 6) Definition of Done

- Sprint doc approved.
- Config and cache/model invariance changes shipped with tests.
- **`LLMProvider` protocol updated with embedding + image + capability methods.**
- **`OpenAIProvider` implements all new methods with retry, token tracking, and batch support.**
- **`AssetCreationStage` uses provider-level image API (no private attribute access).**
- **Provider factory forwards `embedding_model` and `image_model` from `AppConfig`.**
- Multi-layer E2E validation added and green.
- Wave handlers implemented and wired with tests.
- Semantic dedup shipped behind safe fallback behavior, consuming provider embedding API.
- Wave 4 explicitly deferred with tracked prerequisites.
