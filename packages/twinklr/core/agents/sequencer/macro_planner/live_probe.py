"""Fail-closed, owner-only P3-T4 macro contract live-probe harness.

This module never opts itself in.  The caller must supply the audited source SHA,
an owner-local evidence path, a dollar preauthorization, and an API key.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_UP, Decimal
import fcntl
import hashlib
import hmac
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import pwd
import secrets
import stat
import subprocess
import tempfile
from typing import Any, cast

from twinklr.core.agents._paths import AGENTS_BASE_PATH
from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.audio.profile.models import AudioProfileModel
from twinklr.core.agents.prompts import PromptPackLoader, spec_prompt_hash
from twinklr.core.agents.providers.base import (
    LLMProvider,
    LLMResponse,
    ProviderType,
    ResponseMetadata,
)
from twinklr.core.agents.providers.openai import SDK_MAX_RETRIES, OpenAIProvider
from twinklr.core.agents.schema_utils import (
    get_json_schema_example,
    response_schema_hash,
    strict_json_schema,
    strict_response_format,
)
from twinklr.core.agents.sequencer.macro_planner.context import PlanningContext
from twinklr.core.agents.sequencer.macro_planner.orchestrator import MacroPlannerOrchestrator
from twinklr.core.agents.sequencer.macro_planner.specs import get_planner_spec
from twinklr.core.agents.spec import AgentMode
from twinklr.core.agents.taxonomy_utils import (
    get_theming_catalog_dict,
    get_theming_ids,
    inject_taxonomy,
)
from twinklr.core.sequencer.planning import MacroPlan
from twinklr.core.sequencer.templates.group.store import TemplateStore

PROBE_ID = "P3-T4-owner-macro-probe-v1"
DEFAULT_ENDPOINT = "https://api.openai.com/v1"
EXPECTED_SCHEMA_HASH = "5f0f842f98d7a27dec1d0f5eebe9f6549bb9ddb95930e1b4e47960cbea7d18d8"
EXPECTED_RESPONSE_SCHEMA_HASH = "b814e8b70cbfbacdaa2e5752cefc001249f03bfcd111245bc2d6b2006641b012"
EXPECTED_PROMPT_HASH = "166a109923323ef7df0a62a0424677782a5033102e748f4007fa9cdfd0a9038e"
DEFAULT_FIXTURE = Path("tests/fixtures/p3_t4_macro_probe/context.json")
MAX_TASK_ATTEMPTS = 3
MAX_OUTPUT_TOKENS = 8_000
MAX_PROMPT_TOKENS = 70_000
MAX_SERIALIZED_REQUEST_BYTES = 70_000
HARD_USD_CAP = Decimal("1.75")
PRICE_INPUT_PER_M = Decimal("10.00")
PRICE_REASONING_PER_M = Decimal("60.00")
PRICE_COMPLETION_PER_M = Decimal("60.00")


class ProbePreflightError(RuntimeError):
    """The probe was rejected before a provider request."""


@dataclass(frozen=True)
class ProbeRequest:
    repo_root: Path
    fixture: Path
    expected_source_sha: str
    expected_source_tree_hash: str
    expected_input_hash: str
    expected_catalog_hash: str
    expected_request_hash: str
    preauthorize_usd: Decimal
    opt_in: bool
    api_key: str | None
    command: list[str]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _source_files(repo_root: Path, fixture: Path, audio_path: Path) -> dict[str, str]:
    paths = [
        fixture,
        audio_path,
        repo_root / "packages/twinklr/core/agents/async_runner.py",
        repo_root / "packages/twinklr/cli/p3_t4_macro_probe.py",
        repo_root / "packages/twinklr/core/agents/sequencer/macro_planner/live_probe.py",
        repo_root / "packages/twinklr/core/agents/sequencer/macro_planner/heuristics.py",
        repo_root / "packages/twinklr/core/agents/sequencer/macro_planner/orchestrator.py",
        repo_root / "packages/twinklr/core/agents/sequencer/macro_planner/specs.py",
        repo_root / "packages/twinklr/core/sequencer/planning/models.py",
    ]
    transitive_roots = [
        repo_root / "packages/twinklr/core/agents/prompts",
        repo_root / "packages/twinklr/core/agents/providers",
        repo_root / "packages/twinklr/core/agents/sequencer/macro_planner",
        repo_root / "packages/twinklr/core/sequencer/planning",
        repo_root / "packages/twinklr/core/sequencer/theming",
        repo_root / "packages/twinklr/core/sequencer/vocabulary",
        repo_root / "packages/twinklr/core/config",
        repo_root / "packages/twinklr/core/agents/audio/profile",
        repo_root / "packages/twinklr/core/sequencer/templates/group/models",
        repo_root / "packages/twinklr/core/sequencer/templates",
        repo_root / "catalog/templates",
    ]
    for root in transitive_roots:
        paths.extend(
            sorted(
                path
                for path in root.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
            )
        )
    paths.extend(
        repo_root / relative
        for relative in (
            "packages/twinklr/core/agents/schema_utils.py",
            "packages/twinklr/core/agents/spec.py",
            "packages/twinklr/core/agents/taxonomy_utils.py",
            "packages/twinklr/core/agents/issues.py",
            "packages/twinklr/core/agents/result.py",
            "packages/twinklr/core/agents/state.py",
            "uv.lock",
        )
    )
    paths = list(dict.fromkeys(paths))
    return {str(path.relative_to(repo_root)): _sha(path.read_bytes()) for path in paths}


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(tmp_name).replace(path)
        _assert_regular_owner_file(path, 0o600, "probe ledger")
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if Path(tmp_name).exists():
            Path(tmp_name).unlink()


def _canonical_state_paths() -> tuple[Path, Path, Path]:
    passwd_home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
    env_home = os.environ.get("HOME")
    if env_home is None or Path(env_home).resolve() != passwd_home:
        raise ProbePreflightError("HOME must match the owner home from the passwd database")
    root = passwd_home / ".local/state/twinklr/owner-probes" / PROBE_ID
    return root, root / "ledger.json", root / "integrity.key"


def _assert_safe_state_path(root: Path) -> None:
    if root.is_symlink():
        raise ProbePreflightError("canonical owner-state directory must not be a symlink")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root_stat = root.stat()
    if not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_uid != os.getuid():
        raise ProbePreflightError("canonical owner-state directory has an unsafe owner/type")
    if stat.S_IMODE(root_stat.st_mode) != 0o700:
        raise ProbePreflightError("canonical owner-state directory permissions must be 0700")
    current = root
    while current != current.parent:
        if current.is_symlink():
            raise ProbePreflightError(f"unsafe symlink in owner-state path: {current}")
        current = current.parent


def _integrity_key(path: Path) -> bytes:
    if path.is_symlink():
        raise ProbePreflightError("integrity key must not be a symlink")
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(secrets.token_bytes(32))
            handle.flush()
            os.fsync(handle.fileno())
    _assert_regular_owner_file(path, 0o600, "integrity key")
    key = path.read_bytes()
    if len(key) < 32:
        raise ProbePreflightError("integrity key has an invalid length")
    return key


def _assert_regular_owner_file(path: Path, mode: int, label: str) -> None:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise ProbePreflightError(f"{label} must be a regular owner-owned file")
    if stat.S_IMODE(info.st_mode) != mode:
        raise ProbePreflightError(f"{label} permissions must be {mode:04o}")


def _seal(document: dict[str, Any], key: bytes) -> dict[str, Any]:
    unsigned = {k: v for k, v in document.items() if k != "integrity_hmac_sha256"}
    document["integrity_hmac_sha256"] = hmac.new(
        key, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    return document


def _verify_seal(document: dict[str, Any], key: bytes) -> None:
    actual = document.get("integrity_hmac_sha256")
    expected = hmac.new(
        key,
        _canonical({k: v for k, v in document.items() if k != "integrity_hmac_sha256"}),
        hashlib.sha256,
    ).hexdigest()
    if not isinstance(actual, str) or not hmac.compare_digest(actual, expected):
        raise ProbePreflightError("owner probe ledger integrity check failed")


def _cost(usage: dict[str, int]) -> Decimal:
    million = Decimal(1_000_000)
    amount = (
        Decimal(usage["prompt_tokens"]) * PRICE_INPUT_PER_M
        + Decimal(usage["reasoning_tokens"]) * PRICE_REASONING_PER_M
        + Decimal(usage["completion_tokens"]) * PRICE_COMPLETION_PER_M
    ) / million
    return amount.quantize(Decimal("0.000001"), rounding=ROUND_UP)


def _preauthorized_worst_cost() -> Decimal:
    return _cost(
        {
            "prompt_tokens": MAX_PROMPT_TOKENS,
            "reasoning_tokens": MAX_OUTPUT_TOKENS,
            "completion_tokens": MAX_OUTPUT_TOKENS,
        }
    )


def _template_catalog_identity(repo_root: Path) -> dict[str, Any]:
    catalog_dir = repo_root / "catalog/templates"
    if _local_template_extensions_present(repo_root):
        raise ProbePreflightError(
            "local data/templates overlay extensions are disabled for this probe"
        )
    TemplateStore.from_catalog_with_local_extensions_strict(catalog_dir, None)
    files = {
        str(path.relative_to(repo_root)): _sha(path.read_bytes())
        for path in sorted(catalog_dir.rglob("*"))
        if path.is_file()
    }
    return {"local_extensions": False, "files": files}


def _local_template_extensions_present(repo_root: Path) -> bool:
    return (repo_root / "data/templates").exists()  # local-extensions overlay


def _spend_summary(document: dict[str, Any]) -> dict[str, str]:
    actual = sum(
        (Decimal(str(item.get("actual_cost_usd", "0"))) for item in document["attempts"]),
        Decimal("0"),
    )
    reserved = sum(
        (Decimal(str(item.get("reserved_cost_usd", "0"))) for item in document["attempts"]),
        Decimal("0"),
    )
    return {
        "actual_usd": str(actual),
        "reserved_usd": str(reserved),
        "committed_usd": str(actual + reserved),
        "task_cap_usd": str(HARD_USD_CAP),
    }


def _trustworthy_usage(
    metadata: ResponseMetadata | None,
    *,
    serialized_request_bytes: int,
    runner_usage: dict[str, int],
) -> tuple[dict[str, int], str | None]:
    if metadata is None:
        return runner_usage, "provider response metadata/usage is absent"
    if not metadata.token_usage_is_explicit:
        return runner_usage, "provider usage fields were not explicitly reported"
    raw = metadata.token_usage
    usage = {
        "prompt_tokens": raw.prompt_tokens,
        "reasoning_tokens": raw.reasoning_tokens,
        "completion_tokens": raw.completion_tokens,
        "total_tokens": raw.total_tokens,
    }
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in usage.values()
    ):
        return usage, "usage fields must be explicit nonnegative integers"
    if usage != runner_usage:
        return usage, "provider and runner usage attribution disagree"
    if usage["prompt_tokens"] == 0 or (usage["reasoning_tokens"] + usage["completion_tokens"] == 0):
        return usage, "usage is absent/zero-default or incomplete"
    if usage["total_tokens"] != (
        usage["prompt_tokens"] + usage["reasoning_tokens"] + usage["completion_tokens"]
    ):
        return usage, "usage total is internally inconsistent"
    if usage["prompt_tokens"] > serialized_request_bytes:
        return usage, "prompt usage exceeds the conservative serialized-request bound"
    if (
        usage["reasoning_tokens"] > MAX_OUTPUT_TOKENS
        or usage["completion_tokens"] > MAX_OUTPUT_TOKENS
    ):
        return usage, "reasoning/completion usage exceeds the frozen per-class bound"
    return usage, None


class _AuditedProvider:
    """Count provider entry before await and retain response metadata."""

    def __init__(self, inner: Any, *, on_entry: Callable[[], None]) -> None:
        self.inner = inner
        self.on_entry = on_entry
        self.entry_count = 0
        self.response_metadata: ResponseMetadata | None = None

    @property
    def provider_type(self) -> ProviderType:
        return cast("ProviderType", self.inner.provider_type)

    async def generate_json_async(self, *args: Any, **kwargs: Any) -> LLMResponse:
        self.entry_count += 1
        self.on_entry()
        response = cast("LLMResponse", await self.inner.generate_json_async(*args, **kwargs))
        self.response_metadata = response.metadata
        return response


def _probe_spec() -> Any:
    return get_planner_spec().model_copy(
        update={
            "mode": AgentMode.ONESHOT,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "provider_max_attempts": 1,
            "allow_json_object_fallback": False,
            "max_schema_repair_attempts": 0,
        }
    )


def _serialized_request(
    orchestrator: MacroPlannerOrchestrator, context: PlanningContext
) -> tuple[bytes, dict[str, Any]]:
    spec = _probe_spec()
    variables = {**spec.default_variables, **orchestrator.build_planner_variables(context)}
    variables["response_schema"] = get_json_schema_example(MacroPlan)
    variables = inject_taxonomy(variables)
    prompts = PromptPackLoader(AGENTS_BASE_PATH).load_and_render(spec.prompt_pack, variables)
    messages: list[dict[str, str]] = []
    if prompts.get("developer"):
        messages.append({"role": "developer", "content": prompts["developer"]})
    if prompts.get("system"):
        messages.append({"role": "system", "content": prompts["system"]})
    messages.extend(prompts.get("examples") or [])
    if prompts.get("user"):
        messages.append({"role": "user", "content": prompts["user"]})
    request_config = {
        "model": spec.model,
        "temperature": spec.temperature,
        "reasoning_effort": spec.reasoning_effort,
        "max_output_tokens": spec.max_tokens,
        "timeout_seconds": spec.timeout_seconds,
        "provider_max_attempts": spec.provider_max_attempts,
        "sdk_retries": SDK_MAX_RETRIES,
        "allow_json_object_fallback": spec.allow_json_object_fallback,
        "max_schema_repair_attempts": spec.max_schema_repair_attempts,
        "endpoint": DEFAULT_ENDPOINT,
        "response_schema_hash": response_schema_hash(MacroPlan),
        "response_format": strict_response_format(MacroPlan),
    }
    return _canonical({"messages": messages, "config": request_config}), request_config


def _identity(repo_root: Path, fixture: Path) -> tuple[dict[str, Any], PlanningContext]:
    source_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout.strip()
    frozen_fixture = (repo_root / DEFAULT_FIXTURE).resolve()
    if fixture.resolve() != frozen_fixture or fixture.is_symlink():
        raise ProbePreflightError("probe must use the frozen tracked planning fixture")
    descriptor = json.loads(fixture.read_text(encoding="utf-8"))
    audio_candidate = repo_root / descriptor["audio_profile_path"]
    audio_path = audio_candidate.resolve()
    if not audio_path.is_relative_to(repo_root.resolve()) or audio_candidate.is_symlink():
        raise ProbePreflightError("frozen audio-profile input path is unsafe")
    audio_data = json.loads(audio_path.read_text(encoding="utf-8"))
    context = PlanningContext(
        audio_profile=AudioProfileModel.model_validate(audio_data),
        lyric_context=descriptor["lyric_context"],
        display_groups=descriptor["display_groups"],
    )
    base_spec = get_planner_spec()
    probe_spec = _probe_spec()
    schema_hash = _sha(_canonical(strict_json_schema(MacroPlan)))
    prompt_hash = spec_prompt_hash(AGENTS_BASE_PATH, probe_spec)
    frozen_identity = descriptor["probe_identity"]
    if base_spec.model != frozen_identity["model"]:
        raise ProbePreflightError("shipped planner model identity changed")
    if frozen_identity["endpoint"] != DEFAULT_ENDPOINT:
        raise ProbePreflightError("default provider endpoint identity changed")
    runtime = {
        "python": platform.python_version(),
        "openai": version("openai"),
        "pydantic": version("pydantic"),
    }
    for name, actual in runtime.items():
        if actual != frozen_identity[name]:
            raise ProbePreflightError(f"frozen {name} runtime identity changed")
    if schema_hash != EXPECTED_SCHEMA_HASH:
        raise ProbePreflightError("macro response schema identity changed")
    if response_schema_hash(MacroPlan) != EXPECTED_RESPONSE_SCHEMA_HASH:
        raise ProbePreflightError("provider response-schema identity changed")
    if prompt_hash != EXPECTED_PROMPT_HASH:
        raise ProbePreflightError("shipped macro prompt identity changed")
    source_files = _source_files(repo_root, fixture, audio_path)
    catalog_identity = {
        "theming": {"catalog": get_theming_catalog_dict(), "ids": get_theming_ids()},
        "templates": _template_catalog_identity(repo_root),
    }
    identity = {
        "probe_id": PROBE_ID,
        "source_sha": source_sha,
        "source_tree_hash": _sha(_canonical(source_files)),
        "source_files": source_files,
        "input_hash": _sha(_canonical(context.model_dump(mode="json"))),
        "catalog_hash": _sha(_canonical(catalog_identity)),
        "catalog_identity": catalog_identity,
        "schema_hash": schema_hash,
        "response_schema_hash": response_schema_hash(MacroPlan),
        "prompt_hash": prompt_hash,
        "model": probe_spec.model,
        "endpoint": DEFAULT_ENDPOINT,
        "runtime": runtime,
        "budget": {
            "mode": probe_spec.mode.value,
            "reasoning_effort": probe_spec.reasoning_effort,
            "temperature": probe_spec.temperature,
            "timeout_seconds": probe_spec.timeout_seconds,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "max_prompt_tokens_for_preauthorization": MAX_PROMPT_TOKENS,
            "provider_max_attempts": 1,
            "sdk_retries": SDK_MAX_RETRIES,
            "json_fallback": False,
            "schema_repairs": 0,
            "max_task_attempts": MAX_TASK_ATTEMPTS,
        },
        "pricing": {
            "pricing_id": "p3-t4-frozen-conservative-2026-08-16",
            "input_per_million_usd": str(PRICE_INPUT_PER_M),
            "reasoning_per_million_usd": str(PRICE_REASONING_PER_M),
            "completion_per_million_usd": str(PRICE_COMPLETION_PER_M),
            "hard_total_task_usd": str(HARD_USD_CAP),
            "worst_case_usd": str(_preauthorized_worst_cost()),
        },
    }
    return identity, context


async def run_probe(
    request: ProbeRequest,
    *,
    provider_factory: Callable[[str, str], Any] = lambda key, endpoint: OpenAIProvider(
        api_key=key, base_url=endpoint
    ),
) -> dict[str, Any]:
    """Execute under an owner-local lock so the three-attempt cap cannot race."""
    if not request.opt_in:
        raise ProbePreflightError("explicit --live opt-in is required")
    if not request.api_key:
        raise ProbePreflightError("OPENAI_API_KEY is required")
    state_root, evidence, key_path = _canonical_state_paths()
    if state_root.resolve().is_relative_to(request.repo_root.resolve()):
        raise ProbePreflightError("canonical owner-state directory must be outside the repository")
    _assert_safe_state_path(state_root)
    lock_path = state_root / "probe.lock"
    if lock_path.is_symlink() or evidence.is_symlink():
        raise ProbePreflightError("owner-state lock and ledger must not be symlinks")
    if lock_path.exists():
        _assert_regular_owner_file(lock_path, 0o600, "probe lock")
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(lock_fd, "a+", encoding="utf-8") as lock:
        _assert_regular_owner_file(lock_path, 0o600, "probe lock")
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ProbePreflightError("another owner probe invocation holds the lock") from exc
        key = _integrity_key(key_path)
        return await _run_probe_locked(
            request,
            evidence=evidence,
            integrity_key=key,
            provider_factory=provider_factory,
        )


async def _run_probe_locked(
    request: ProbeRequest,
    *,
    evidence: Path,
    integrity_key: bytes,
    provider_factory: Callable[[str, str], Any],
) -> dict[str, Any]:
    """Execute at most one strict request and atomically persist its evidence."""
    root = request.repo_root.resolve()
    fixture = request.fixture.resolve()
    identity, context = _identity(root, fixture)
    assert request.api_key is not None  # established by the outer fail-closed preflight
    if request.expected_source_sha != identity["source_sha"]:
        raise ProbePreflightError("audited source SHA does not match HEAD")
    if request.expected_source_tree_hash != identity["source_tree_hash"]:
        raise ProbePreflightError("audited source-tree hash does not match probe inputs")
    if request.expected_input_hash != identity["input_hash"]:
        raise ProbePreflightError("independently audited input hash does not match")
    if request.expected_catalog_hash != identity["catalog_hash"]:
        raise ProbePreflightError("independently audited catalog hash does not match")
    if SDK_MAX_RETRIES != 0:
        raise ProbePreflightError("SDK retries must remain zero")
    preflight_orchestrator = MacroPlannerOrchestrator(provider=object())  # type: ignore[arg-type]
    serialized_request, request_config = _serialized_request(preflight_orchestrator, context)
    serialized_size = len(serialized_request)
    serialized_hash = _sha(serialized_request)
    if request.expected_request_hash != serialized_hash:
        raise ProbePreflightError("independently audited serialized-request hash does not match")
    if serialized_size > MAX_SERIALIZED_REQUEST_BYTES:
        raise ProbePreflightError(
            f"serialized request bound {serialized_size} exceeds {MAX_SERIALIZED_REQUEST_BYTES}"
        )
    request_worst = _cost(
        {
            "prompt_tokens": serialized_size,
            "reasoning_tokens": MAX_OUTPUT_TOKENS,
            "completion_tokens": MAX_OUTPUT_TOKENS,
        }
    )
    worst = _preauthorized_worst_cost()
    if (
        worst > HARD_USD_CAP
        or request.preauthorize_usd < worst
        or request.preauthorize_usd > HARD_USD_CAP
    ):
        raise ProbePreflightError(
            f"preauthorization must cover ${worst} without exceeding hard cap ${HARD_USD_CAP}"
        )

    document: dict[str, Any]
    if evidence.exists():
        _assert_regular_owner_file(evidence, 0o600, "probe ledger")
        document = json.loads(evidence.read_text(encoding="utf-8"))
        _verify_seal(document, integrity_key)
    else:
        document = {"probe_id": PROBE_ID, "attempts": []}
    if any(item.get("outcome") == "passed" for item in document["attempts"]):
        raise ProbePreflightError("terminal successful probe already recorded")
    if len(document["attempts"]) >= MAX_TASK_ATTEMPTS:
        raise ProbePreflightError("hard task-attempt cap of 3 is exhausted")
    prior_spend = _spend_summary(document)
    if Decimal(prior_spend["committed_usd"]) + worst > HARD_USD_CAP:
        raise ProbePreflightError(
            "total P3-T4 task budget cannot reserve the next worst-case attempt"
        )

    attempt: dict[str, Any] = {
        "attempt": len(document["attempts"]) + 1,
        "command": request.command,
        "identity": identity,
        "started_at": datetime.now(UTC).isoformat(),
        "preauthorized_usd": str(request.preauthorize_usd),
        "reserved_cost_usd": str(worst),
        "request": {
            "sha256": serialized_hash,
            "serialized_bytes": serialized_size,
            "conservative_prompt_token_bound": serialized_size,
            "worst_case_usd": str(request_worst),
            "config": request_config,
        },
        "outcome": "in_progress",
        "provider_request_count": 0,
        "logical_request_count": 0,
    }
    document["attempts"].append(attempt)
    document["spend"] = _spend_summary(document)
    _atomic_write(evidence, _seal(document, integrity_key))  # a crash still consumes the attempt

    provider: _AuditedProvider | None = None

    def reserve_provider_entry() -> None:
        attempt["provider_request_count"] = 1
        document["spend"] = _spend_summary(document)
        _atomic_write(evidence, _seal(document, integrity_key))

    try:
        provider = _AuditedProvider(
            provider_factory(request.api_key, DEFAULT_ENDPOINT),
            on_entry=reserve_provider_entry,
        )
        typed_provider = cast("LLMProvider", provider)
        orchestrator = MacroPlannerOrchestrator(provider=typed_provider)
        spec = _probe_spec()
        result = await AsyncAgentRunner(
            provider=typed_provider, prompt_base_path=AGENTS_BASE_PATH
        ).run(spec=spec, variables=orchestrator.build_planner_variables(context))
        logical_count = int(result.metadata.get("logical_request_count", 0))
        attempt["provider_request_count"] = provider.entry_count
        attempt["logical_request_count"] = logical_count
        attempt["schema_repair_count"] = int(result.metadata.get("schema_repair_attempts", 0))
        runner_usage = {
            "prompt_tokens": result.prompt_tokens,
            "reasoning_tokens": result.reasoning_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.tokens_used,
        }
        metadata = provider.response_metadata
        usage, usage_error = _trustworthy_usage(
            metadata,
            serialized_request_bytes=serialized_size,
            runner_usage=runner_usage,
        )
        attempt["usage"] = usage
        if usage != runner_usage:
            attempt["runner_usage"] = runner_usage
        if usage_error is None:
            attempt["actual_cost_usd"] = str(_cost(usage))
            attempt["reserved_cost_usd"] = "0"
        else:
            attempt["usage_unavailable"] = usage_error
        attempt["response"] = {
            "id": metadata.response_id if metadata else None,
            "model": metadata.model if metadata else None,
            "actual_model_present": metadata.actual_model_present if metadata else False,
            "mode": metadata.structured_output_mode if metadata else None,
            "schema_hash": metadata.response_schema_hash if metadata else None,
            "finish_reason": metadata.finish_reason if metadata else None,
            "fallback_reason": metadata.structured_output_fallback_reason if metadata else None,
        }
        errors: list[str] = []
        if result.success and isinstance(result.data, MacroPlan):
            errors = orchestrator.validate_external_contract(result.data, context)
            validated_output = result.data.model_dump(mode="json")
            attempt["validated_output"] = validated_output
            attempt["validated_plan_sha256"] = _sha(_canonical(validated_output))
        elif result.error_message:
            errors = [result.error_message]
        if usage_error is not None:
            errors.append(f"usage_unavailable: {usage_error}")
        response = attempt["response"]
        required_response = {
            "id": bool(response["id"]),
            "model": response["model"] == identity["model"],
            "actual_model_present": response["actual_model_present"] is True,
            "mode": response["mode"] == "json_schema",
            "schema_hash": response["schema_hash"] == EXPECTED_RESPONSE_SCHEMA_HASH,
            "finish_reason": response["finish_reason"] == "completed",
            "fallback_reason": response["fallback_reason"] is None,
        }
        errors.extend(name for name, valid in required_response.items() if not valid)
        if provider.entry_count != 1:
            errors.append(f"expected exactly one provider entry, got {provider.entry_count}")
        if logical_count != 1:
            errors.append(f"expected exactly one logical request, got {logical_count}")
        if Decimal(str(attempt.get("actual_cost_usd", "0"))) > HARD_USD_CAP:
            errors.append("actual priced cost exceeded the hard cap")
        attempt["validation"] = {"passed": not errors, "errors": errors}
        attempt["outcome"] = "passed" if result.success and not errors else "failed"
    except BaseException as exc:
        if provider is not None:
            attempt["provider_request_count"] = provider.entry_count
        attempt["outcome"] = "failed"
        attempt["validation"] = {"passed": False, "errors": [f"{type(exc).__name__}: {exc}"]}
        if provider is None or provider.entry_count == 0:
            attempt["reserved_cost_usd"] = "0"
        if not isinstance(exc, Exception):
            raise
    finally:
        attempt["finished_at"] = datetime.now(UTC).isoformat()
        document["spend"] = _spend_summary(document)
        _atomic_write(evidence, _seal(document, integrity_key))
    return attempt
