"""Offline safety tests for the owner-only P3-T4 live-probe harness."""

from __future__ import annotations

from dataclasses import fields
from decimal import Decimal
import fcntl
import json
from pathlib import Path
import subprocess
from typing import Any

import pytest

from twinklr.core.agents.providers.base import (
    LLMResponse,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
)
import twinklr.core.agents.sequencer.macro_planner.live_probe as probe_module
from twinklr.core.agents.sequencer.macro_planner.live_probe import (
    AUTHORIZATION_ID,
    DEFAULT_FIXTURE,
    EXPECTED_PRIOR_ATTEMPT_HASH,
    EXPECTED_PRIOR_LEDGER_HASH,
    EXPECTED_RESPONSE_SCHEMA_HASH,
    HARD_USD_CAP,
    MAX_TASK_ATTEMPTS,
    ProbePreflightError,
    ProbeRequest,
    _identity,
    _preauthorized_worst_cost,
    run_probe,
)
from twinklr.core.agents.sequencer.macro_planner.orchestrator import MacroPlannerOrchestrator

REAL_CANONICAL_STATE_PATHS = probe_module._canonical_state_paths
REAL_ASSERT_CLEAN_COMMITTED_MANIFEST = probe_module._assert_clean_committed_manifest


class FakeProvider:
    provider_type = ProviderType.OPENAI

    def __init__(
        self,
        content: dict[str, Any],
        *,
        metadata: ResponseMetadata | None = None,
        error: Exception | None = None,
    ) -> None:
        self.content = content
        self.metadata = metadata
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def generate_json_async(self, messages, model, temperature=None, **kwargs):
        self.calls.append({"messages": messages, "model": model, **kwargs})
        if self.error:
            raise self.error
        return LLMResponse(
            content=self.content,
            metadata=self.metadata
            or ResponseMetadata(
                response_id="resp_offline_fixture",
                model=model,
                actual_model_present=True,
                token_usage_is_explicit=True,
                finish_reason="completed",
                structured_output_mode="json_schema",
                response_schema_hash=EXPECTED_RESPONSE_SCHEMA_HASH,
                token_usage=TokenUsage(1200, 200, 400, 1800),
            ),
        )


def _sha(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _request(root: Path, **changes: Any) -> ProbeRequest:
    identity, context = _identity(root, root / DEFAULT_FIXTURE)
    serialized, _ = probe_module._serialized_request(
        MacroPlannerOrchestrator(provider=object()), context
    )
    values = {
        "repo_root": root,
        "fixture": root / DEFAULT_FIXTURE,
        "expected_source_sha": _sha(root),
        "expected_source_tree_hash": identity["source_tree_hash"],
        "expected_input_hash": identity["input_hash"],
        "expected_catalog_hash": identity["catalog_hash"],
        "expected_request_hash": probe_module._sha(serialized),
        "authorization_id": probe_module.AUTHORIZATION_ID,
        "expected_prior_ledger_hash": probe_module.EXPECTED_PRIOR_LEDGER_HASH,
        "expected_prior_attempt_hash": probe_module.EXPECTED_PRIOR_ATTEMPT_HASH,
        "preauthorize_usd": _preauthorized_worst_cost(),
        "opt_in": True,
        "api_key": "offline-test-key",
        "command": ["offline-test"],
    }
    values.update(changes)
    return ProbeRequest(**values)


def test_probe_request_has_no_second_ledger_path_override() -> None:
    assert "evidence" not in {field.name for field in fields(ProbeRequest)}


def _seed_prior_ledger(ledger: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    attempt = {
        "attempt": 1,
        "outcome": "failed",
        "provider_request_count": 1,
        "logical_request_count": 0,
        "reserved_cost_usd": "1.660000",
        "usage": {
            "prompt_tokens": 0,
            "reasoning_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "usage_unavailable": "provider response metadata/usage is absent",
    }
    document = {
        "probe_id": probe_module.PROBE_ID,
        "attempts": [attempt],
        "spend": {
            "actual_usd": "0",
            "reserved_usd": "1.660000",
            "committed_usd": "1.660000",
            "task_cap_usd": "1.75",
        },
    }
    prior_attempt_hash = probe_module._sha(probe_module._canonical(attempt))
    prior_ledger_hash = probe_module._sha(probe_module._canonical(document))
    monkeypatch.setattr(probe_module, "EXPECTED_PRIOR_ATTEMPT_HASH", prior_attempt_hash)
    monkeypatch.setattr(probe_module, "EXPECTED_PRIOR_LEDGER_HASH", prior_ledger_hash)
    key_path = ledger.with_name("integrity.key")
    ledger.parent.mkdir(parents=True, mode=0o700)
    ledger.parent.chmod(0o700)
    key_path.write_bytes(b"k" * 32)
    key_path.chmod(0o600)
    probe_module._atomic_write(ledger, probe_module._seal(document, b"k" * 32))
    return document


def _reseal_as_expected_prior(
    ledger: Path, document: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> ProbeRequest:
    attempt_hash = probe_module._sha(probe_module._canonical(document["attempts"][0]))
    ledger_hash = probe_module._sha(probe_module._canonical(document))
    monkeypatch.setattr(probe_module, "EXPECTED_PRIOR_ATTEMPT_HASH", attempt_hash)
    monkeypatch.setattr(probe_module, "EXPECTED_PRIOR_LEDGER_HASH", ledger_hash)
    probe_module._atomic_write(ledger, probe_module._seal(document, b"k" * 32))
    root = Path(__file__).resolve().parents[5]
    return _request(
        root,
        expected_prior_attempt_hash=attempt_hash,
        expected_prior_ledger_hash=ledger_hash,
    )


@pytest.fixture(autouse=True)
def canonical_owner_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "canonical-owner-state"
    ledger = root / "ledger.json"
    monkeypatch.setattr(
        probe_module,
        "_canonical_state_paths",
        lambda: (root, ledger, root / "integrity.key"),
    )
    _seed_prior_ledger(ledger, monkeypatch)
    monkeypatch.setattr(probe_module, "_assert_clean_committed_manifest", lambda _root: None)
    return ledger


def test_second_attempt_contract_is_exactly_owner_authorized() -> None:
    assert AUTHORIZATION_ID == "p3-t4-second-attempt-owner-approved-2026-08-26"
    assert EXPECTED_PRIOR_LEDGER_HASH == (
        "97c38f6c4bd2facc7bfc0488a991ac79e0d454e04fb177728317224a32babcdc"
    )
    assert EXPECTED_PRIOR_ATTEMPT_HASH == (
        "29802ebe121b5284e33d201bf79df7ee6901bf33204765ca5b43487a6d33b562"
    )
    assert MAX_TASK_ATTEMPTS == 2
    assert Decimal("3.32") == HARD_USD_CAP
    assert _preauthorized_worst_cost() == Decimal("1.660000")


@pytest.mark.asyncio
async def test_missing_canonical_history_never_initializes_fresh_state(
    canonical_owner_state: Path,
) -> None:
    root = Path(__file__).resolve().parents[5]
    canonical_owner_state.unlink()
    with pytest.raises(ProbePreflightError, match="existing canonical ledger"):
        await run_probe(_request(root), provider_factory=lambda *_args: FakeProvider({}))
    assert not canonical_owner_state.exists()


@pytest.mark.asyncio
async def test_reset_ledger_is_rejected_even_with_a_valid_seal(
    canonical_owner_state: Path,
) -> None:
    root = Path(__file__).resolve().parents[5]
    reset = {"probe_id": probe_module.PROBE_ID, "attempts": [], "spend": {}}
    probe_module._atomic_write(canonical_owner_state, probe_module._seal(reset, b"k" * 32))
    with pytest.raises(ProbePreflightError, match="prior ledger hash"):
        await run_probe(_request(root), provider_factory=lambda *_args: FakeProvider({}))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("authorization_id", "authorization ID"),
        ("expected_prior_ledger_hash", "prior ledger hash input"),
        ("expected_prior_attempt_hash", "prior attempt hash input"),
    ],
)
async def test_owner_authorization_and_prior_hash_inputs_are_exact(
    field: str, message: str
) -> None:
    root = Path(__file__).resolve().parents[5]
    with pytest.raises(ProbePreflightError, match=message):
        await run_probe(
            _request(root, **{field: "wrong"}),
            provider_factory=lambda *_args: FakeProvider({}),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [Decimal("1.659999"), Decimal("1.660001")])
async def test_second_attempt_preauthorization_is_exact(amount: Decimal) -> None:
    root = Path(__file__).resolve().parents[5]
    with pytest.raises(ProbePreflightError, match="must equal"):
        await run_probe(
            _request(root, preauthorize_usd=amount),
            provider_factory=lambda *_args: FakeProvider({}),
        )


@pytest.mark.asyncio
async def test_recomputed_prior_spend_must_match_even_when_resealed(
    canonical_owner_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = json.loads(canonical_owner_state.read_text())
    document.pop("integrity_hmac_sha256")
    document["spend"]["committed_usd"] = "0"
    request = _reseal_as_expected_prior(canonical_owner_state, document, monkeypatch)
    with pytest.raises(ProbePreflightError, match="prior spend"):
        await run_probe(request, provider_factory=lambda *_args: FakeProvider({}))


@pytest.mark.asyncio
async def test_prior_outcome_facts_must_match_even_when_resealed(
    canonical_owner_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = json.loads(canonical_owner_state.read_text())
    document.pop("integrity_hmac_sha256")
    document["attempts"][0]["outcome"] = "passed"
    request = _reseal_as_expected_prior(canonical_owner_state, document, monkeypatch)
    with pytest.raises(ProbePreflightError, match="attempt facts"):
        await run_probe(request, provider_factory=lambda *_args: FakeProvider({}))


@pytest.mark.asyncio
async def test_authorization_and_attempt_two_are_one_atomic_ledger_transition(
    canonical_owner_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).resolve().parents[5]
    before = canonical_owner_state.read_bytes()
    original_atomic_write = probe_module._atomic_write

    def fail_transition(path: Path, value: dict[str, Any]) -> None:
        if "authorization_amendments" in value:
            raise OSError("simulated atomic transition failure")
        original_atomic_write(path, value)

    monkeypatch.setattr(probe_module, "_atomic_write", fail_transition)
    provider = FakeProvider({})
    with pytest.raises(OSError, match="atomic transition"):
        await run_probe(_request(root), provider_factory=lambda *_args: provider)
    assert canonical_owner_state.read_bytes() == before
    assert provider.calls == []


@pytest.mark.asyncio
async def test_transition_preserves_attempt_one_and_seals_authorization(
    canonical_owner_state: Path,
) -> None:
    root = Path(__file__).resolve().parents[5]
    prior = json.loads(canonical_owner_state.read_text())
    prior_attempt = probe_module._canonical(prior["attempts"][0])
    await run_probe(_request(root), provider_factory=lambda *_args: FakeProvider({}))
    persisted = json.loads(canonical_owner_state.read_text())
    probe_module._verify_seal(persisted, b"k" * 32)
    assert probe_module._canonical(persisted["attempts"][0]) == prior_attempt
    assert persisted["authorization_amendments"] == [probe_module._authorization_amendment()]
    assert persisted["attempts"][1]["identity"]["owner_authorization"] == (
        probe_module._authorization_amendment()
    )


def test_dirty_committed_manifest_is_rejected(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "probe@example.invalid"], cwd=tmp_path)
    subprocess.run(["git", "config", "user.name", "Probe Test"], cwd=tmp_path)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("clean\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    REAL_ASSERT_CLEAN_COMMITTED_MANIFEST(tmp_path)
    tracked.write_text("dirty\n")
    with pytest.raises(ProbePreflightError, match="clean committed"):
        REAL_ASSERT_CLEAN_COMMITTED_MANIFEST(tmp_path)


def _valid_plan(root: Path) -> dict[str, Any]:
    descriptor = json.loads((root / DEFAULT_FIXTURE).read_text())
    audio = json.loads((root / descriptor["audio_profile_path"]).read_text())
    sections = audio["structure"]["sections"]
    result_sections = []
    focal_arc = []
    for section in sections:
        result_sections.append(
            {
                "section": section,
                "energy_target": "MED",
                "motion_density": "MED",
                "choreography_style": "HYBRID",
                "palette_role": {"stop_id": "probe_palette", "override": None},
                "theme": {
                    "theme_id": "theme.abstract.neon",
                    "scope": "section",
                    "tags": [],
                    "palette_id": None,
                },
                "motif_ids": [],
                "focal_roles": [
                    {"target": {"type": "group", "id": "PROBE_OUTLINE"}, "role": "LEAD"}
                ],
                "call_response_pairs": [],
                "coordination_intent": "UNIFIED",
                "notes": "Offline fixture response.",
            }
        )
        focal_arc.append(
            {
                "section_id": section["section_id"],
                "lead_target": {"type": "group", "id": "PROBE_OUTLINE"},
            }
        )
    return {
        "sections": result_sections,
        "palette_arc": [
            {
                "stop_id": "probe_palette",
                "palette": {
                    "palette_id": "core.christmas_traditional",
                    "role": None,
                    "intensity": None,
                    "variant": None,
                },
                "applies_from_section_id": sections[0]["section_id"],
                "transition": "HOLD",
            }
        ],
        "motif_continuity": [],
        "focal_arc": focal_arc,
    }


@pytest.mark.asyncio
async def test_preflight_rejects_without_opt_in_before_provider(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[5]
    called = False

    def factory(*_args):
        nonlocal called
        called = True
        raise AssertionError

    with pytest.raises(ProbePreflightError, match="opt-in"):
        await run_probe(_request(root, opt_in=False), provider_factory=factory)
    assert called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"api_key": None}, "OPENAI_API_KEY"),
        ({"preauthorize_usd": Decimal("0.01")}, "preauthorization"),
        ({"expected_source_sha": "0" * 40}, "source SHA"),
    ],
)
async def test_preflight_identity_and_budget_fail_before_call(
    tmp_path: Path, changes: dict[str, Any], message: str
) -> None:
    root = Path(__file__).resolve().parents[5]
    called = False

    def factory(*_args):
        nonlocal called
        called = True
        raise AssertionError

    with pytest.raises(ProbePreflightError, match=message):
        await run_probe(_request(root, **changes), provider_factory=factory)
    assert called is False


@pytest.mark.asyncio
async def test_success_uses_one_strict_request_and_writes_evidence(
    canonical_owner_state: Path,
) -> None:
    root = Path(__file__).resolve().parents[5]
    provider = FakeProvider(_valid_plan(root))
    attempt = await run_probe(_request(root), provider_factory=lambda *_args: provider)
    assert attempt["outcome"] == "passed", attempt
    assert len(provider.calls) == 1
    assert provider.calls[0]["provider_max_attempts"] == 1
    assert provider.calls[0]["allow_json_object_fallback"] is False
    assert attempt["response"]["id"] == "resp_offline_fixture"
    persisted = json.loads(canonical_owner_state.read_text())
    assert persisted["attempts"][1]["identity"]["budget"]["schema_repairs"] == 0
    assert persisted["attempts"][1]["usage"] == {
        "prompt_tokens": 1200,
        "reasoning_tokens": 200,
        "completion_tokens": 400,
        "total_tokens": 1800,
    }
    assert persisted["attempts"][1]["validated_plan_sha256"]
    assert persisted["attempts"][1]["request"]["config"]["response_format"]["type"] == (
        "json_schema"
    )


@pytest.mark.asyncio
async def test_exactly_one_additional_attempt_then_every_later_invocation_fails() -> None:
    root = Path(__file__).resolve().parents[5]
    provider = FakeProvider(
        {},
        metadata=ResponseMetadata(
            response_id="zero-cost",
            model="gpt-5.6-sol",
            actual_model_present=True,
            token_usage_is_explicit=True,
            finish_reason="completed",
            structured_output_mode="json_schema",
            response_schema_hash=EXPECTED_RESPONSE_SCHEMA_HASH,
            token_usage=TokenUsage(1, 0, 1, 2),
        ),
    )
    request = _request(root)
    second = await run_probe(request, provider_factory=lambda *_args: provider)
    assert second["attempt"] == 2
    for _ in range(2):
        with pytest.raises(ProbePreflightError, match="no third attempt"):
            await run_probe(request, provider_factory=lambda *_args: provider)
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_invalid_response_writes_failure_evidence(canonical_owner_state: Path) -> None:
    root = Path(__file__).resolve().parents[5]
    provider = FakeProvider({})
    attempt = await run_probe(_request(root), provider_factory=lambda *_args: provider)
    assert attempt["outcome"] == "failed"
    assert attempt["provider_request_count"] == 1
    assert attempt["logical_request_count"] == 1
    assert json.loads(canonical_owner_state.read_text())["attempts"][1]["outcome"] == "failed"


@pytest.mark.asyncio
async def test_oversize_serialized_request_fails_before_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parents[5]
    called = False
    monkeypatch.setattr(
        probe_module,
        "_serialized_request",
        lambda *_args: (b"x" * 200_001, {}),
    )

    def factory(*_args):
        nonlocal called
        called = True
        raise AssertionError

    with pytest.raises(ProbePreflightError, match="serialized request bound"):
        await run_probe(_request(root), provider_factory=factory)
    assert called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metadata",
    [
        ResponseMetadata(
            response_id=None,
            model="gpt-5.6-sol",
            finish_reason="completed",
            structured_output_mode="json_schema",
            response_schema_hash=EXPECTED_RESPONSE_SCHEMA_HASH,
        ),
        ResponseMetadata(
            response_id="r",
            model="gpt-5.6-sol",
            finish_reason="pending",
            structured_output_mode="json_schema",
            response_schema_hash=EXPECTED_RESPONSE_SCHEMA_HASH,
        ),
        ResponseMetadata(
            response_id="r",
            model="wrong-model",
            finish_reason="completed",
            structured_output_mode="json_schema",
            response_schema_hash=EXPECTED_RESPONSE_SCHEMA_HASH,
        ),
        ResponseMetadata(
            response_id="r",
            model="gpt-5.6-sol",
            finish_reason="completed",
            structured_output_mode="json_object_fallback",
            response_schema_hash=EXPECTED_RESPONSE_SCHEMA_HASH,
        ),
        ResponseMetadata(
            response_id="r",
            model="gpt-5.6-sol",
            finish_reason="completed",
            structured_output_mode="json_schema",
            response_schema_hash="wrong",
        ),
        ResponseMetadata(
            response_id="r",
            model="gpt-5.6-sol",
            finish_reason=None,
            structured_output_mode="json_schema",
            response_schema_hash=EXPECTED_RESPONSE_SCHEMA_HASH,
        ),
        ResponseMetadata(
            response_id="r",
            model="gpt-5.6-sol",
            finish_reason="completed",
            structured_output_mode="json_schema",
            structured_output_fallback_reason="unexpected",
            response_schema_hash=EXPECTED_RESPONSE_SCHEMA_HASH,
        ),
    ],
)
async def test_wrong_provider_metadata_is_a_recorded_failure(
    metadata: ResponseMetadata,
) -> None:
    root = Path(__file__).resolve().parents[5]
    provider = FakeProvider(_valid_plan(root), metadata=metadata)
    attempt = await run_probe(_request(root), provider_factory=lambda *_args: provider)
    assert attempt["outcome"] == "failed"
    assert attempt["provider_request_count"] == 1


@pytest.mark.asyncio
async def test_transport_failure_still_counts_provider_entry() -> None:
    root = Path(__file__).resolve().parents[5]
    provider = FakeProvider({}, error=RuntimeError("offline transport failure"))
    attempt = await run_probe(_request(root), provider_factory=lambda *_args: provider)
    assert attempt["outcome"] == "failed"
    assert attempt["provider_request_count"] == 1
    assert attempt["logical_request_count"] == 0


@pytest.mark.asyncio
async def test_terminal_success_refuses_another_attempt() -> None:
    root = Path(__file__).resolve().parents[5]
    provider = FakeProvider(_valid_plan(root))
    request = _request(root)
    assert (await run_probe(request, provider_factory=lambda *_args: provider))[
        "outcome"
    ] == "passed"
    with pytest.raises(ProbePreflightError, match="no third attempt"):
        await run_probe(request, provider_factory=lambda *_args: provider)
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_tampered_global_ledger_fails_before_provider(
    canonical_owner_state: Path,
) -> None:
    root = Path(__file__).resolve().parents[5]
    provider = FakeProvider({})
    request = _request(root)
    await run_probe(request, provider_factory=lambda *_args: provider)
    document = json.loads(canonical_owner_state.read_text())
    document["attempts"] = []
    canonical_owner_state.write_text(json.dumps(document))
    with pytest.raises(ProbePreflightError, match="integrity"):
        await run_probe(request, provider_factory=lambda *_args: provider)
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_symlinked_owner_state_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).resolve().parents[5]
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    monkeypatch.setattr(
        probe_module,
        "_canonical_state_paths",
        lambda: (linked, linked / "ledger.json", linked / "integrity.key"),
    )
    with pytest.raises(ProbePreflightError, match="symlink"):
        await run_probe(_request(root), provider_factory=lambda *_args: FakeProvider({}))


@pytest.mark.asyncio
async def test_identity_mismatch_can_be_repaired_without_consuming_attempt() -> None:
    root = Path(__file__).resolve().parents[5]
    provider = FakeProvider({})
    with pytest.raises(ProbePreflightError, match="source SHA"):
        await run_probe(
            _request(root, expected_source_sha="0" * 40),
            provider_factory=lambda *_args: provider,
        )
    attempt = await run_probe(_request(root), provider_factory=lambda *_args: provider)
    assert attempt["attempt"] == 2
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_concurrent_lock_fails_fast_without_provider_entry(
    canonical_owner_state: Path,
) -> None:
    root = Path(__file__).resolve().parents[5]
    canonical_owner_state.parent.mkdir(parents=True, exist_ok=True)
    canonical_owner_state.parent.chmod(0o700)
    lock_path = canonical_owner_state.parent / "probe.lock"
    lock_path.touch(mode=0o600)
    lock_path.chmod(0o600)
    provider = FakeProvider({})
    with lock_path.open("a+") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ProbePreflightError, match="holds the lock"):
            await run_probe(_request(root), provider_factory=lambda *_args: provider)
    assert provider.calls == []


def test_passwd_home_mismatch_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/tmp/not-the-passwd-home")
    with pytest.raises(ProbePreflightError, match="passwd"):
        REAL_CANONICAL_STATE_PATHS()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target", "mode", "message"),
    [
        ("integrity.key", 0o644, "integrity key permissions"),
        ("probe.lock", 0o644, "probe lock permissions"),
    ],
)
async def test_insecure_owner_state_file_modes_fail_closed(
    canonical_owner_state: Path,
    target: str,
    mode: int,
    message: str,
) -> None:
    root = Path(__file__).resolve().parents[5]
    state = canonical_owner_state.parent
    state.mkdir(mode=0o700, exist_ok=True)
    state.chmod(0o700)
    path = state / target
    path.write_bytes(b"k" * 32)
    path.chmod(mode)
    with pytest.raises(ProbePreflightError, match=message):
        await run_probe(_request(root), provider_factory=lambda *_args: FakeProvider({}))


@pytest.mark.asyncio
async def test_short_integrity_key_fails_closed(canonical_owner_state: Path) -> None:
    root = Path(__file__).resolve().parents[5]
    state = canonical_owner_state.parent
    state.mkdir(mode=0o700, exist_ok=True)
    state.chmod(0o700)
    key = state / "integrity.key"
    key.write_bytes(b"short")
    key.chmod(0o600)
    with pytest.raises(ProbePreflightError, match="length"):
        await run_probe(_request(root), provider_factory=lambda *_args: FakeProvider({}))


@pytest.mark.asyncio
async def test_frozen_runtime_mismatch_fails_before_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parents[5]
    request = _request(root)
    monkeypatch.setattr(probe_module.platform, "python_version", lambda: "0.0.0")
    provider = FakeProvider({})
    with pytest.raises(ProbePreflightError, match="python runtime"):
        await run_probe(request, provider_factory=lambda *_args: provider)
    assert provider.calls == []


@pytest.mark.asyncio
async def test_base_exception_persists_reserved_provider_count(
    canonical_owner_state: Path,
) -> None:
    class OfflineCrash(BaseException):
        pass

    root = Path(__file__).resolve().parents[5]
    provider = FakeProvider({}, error=OfflineCrash("simulated abrupt cancellation"))
    with pytest.raises(OfflineCrash):
        await run_probe(_request(root), provider_factory=lambda *_args: provider)
    attempt = json.loads(canonical_owner_state.read_text())["attempts"][1]
    assert attempt["provider_request_count"] == 1
    assert attempt["outcome"] == "failed"


@pytest.mark.asyncio
async def test_second_attempt_recomputes_cumulative_spend_and_then_closes(
    canonical_owner_state: Path,
) -> None:
    root = Path(__file__).resolve().parents[5]
    one_dollar = ResponseMetadata(
        response_id="one-dollar",
        model="gpt-5.6-sol",
        actual_model_present=True,
        token_usage_is_explicit=True,
        finish_reason="completed",
        structured_output_mode="json_schema",
        response_schema_hash=EXPECTED_RESPONSE_SCHEMA_HASH,
        token_usage=TokenUsage(4000, 8000, 8000, 20000),
    )
    provider = FakeProvider({}, metadata=one_dollar)
    request = _request(root)
    second = await run_probe(request, provider_factory=lambda *_args: provider)
    assert second["actual_cost_usd"] == "1.000000"
    for _ in range(2):
        with pytest.raises(ProbePreflightError, match="no third attempt"):
            await run_probe(request, provider_factory=lambda *_args: provider)
    assert len(provider.calls) == 1
    assert json.loads(canonical_owner_state.read_text())["spend"] == {
        "actual_usd": "1.000000",
        "reserved_usd": "1.660000",
        "committed_usd": "2.660000",
        "task_cap_usd": "3.32",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("expected_input_hash", "input hash"),
        ("expected_catalog_hash", "catalog hash"),
        ("expected_request_hash", "serialized-request hash"),
    ],
)
async def test_independently_audited_hash_mismatch_fails_before_provider(
    field: str, message: str
) -> None:
    root = Path(__file__).resolve().parents[5]
    provider = FakeProvider({})
    with pytest.raises(ProbePreflightError, match=message):
        await run_probe(
            _request(root, **{field: "0" * 64}),
            provider_factory=lambda *_args: provider,
        )
    assert provider.calls == []


@pytest.mark.asyncio
async def test_catalog_drift_fails_before_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parents[5]
    request = _request(root)
    provider = FakeProvider({})
    monkeypatch.setattr(
        probe_module,
        "_template_catalog_identity",
        lambda _root: {"local_extensions": False, "files": {"drift": "changed"}},
    )
    with pytest.raises(ProbePreflightError, match="catalog hash"):
        await run_probe(request, provider_factory=lambda *_args: provider)
    assert provider.calls == []


@pytest.mark.asyncio
async def test_local_template_overlay_fails_before_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parents[5]
    request = _request(root)
    provider = FakeProvider({})
    monkeypatch.setattr(
        probe_module,
        "_local_template_extensions_present",
        lambda _root: True,
    )
    with pytest.raises(ProbePreflightError, match="local data/templates"):
        await run_probe(request, provider_factory=lambda *_args: provider)
    assert provider.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token_usage", "usage_explicit", "reason"),
    [
        (TokenUsage(), False, "not explicitly reported"),
        (TokenUsage(10, 0, 0, 10), True, "incomplete"),
        (TokenUsage(10, 1, 1, 99), True, "internally inconsistent"),
    ],
)
async def test_untrustworthy_usage_commits_full_reservation_and_blocks_second_call(
    canonical_owner_state: Path,
    token_usage: TokenUsage,
    usage_explicit: bool,
    reason: str,
) -> None:
    root = Path(__file__).resolve().parents[5]
    metadata = ResponseMetadata(
        response_id="unmetered",
        model="gpt-5.6-sol",
        actual_model_present=True,
        token_usage_is_explicit=usage_explicit,
        finish_reason="completed",
        structured_output_mode="json_schema",
        response_schema_hash=EXPECTED_RESPONSE_SCHEMA_HASH,
        token_usage=token_usage,
    )
    provider = FakeProvider({}, metadata=metadata)
    request = _request(root)
    first = await run_probe(request, provider_factory=lambda *_args: provider)
    assert reason in first["usage_unavailable"]
    assert first["reserved_cost_usd"] == "1.660000"
    assert "actual_cost_usd" not in first
    with pytest.raises(ProbePreflightError, match="no third attempt"):
        await run_probe(request, provider_factory=lambda *_args: provider)
    assert len(provider.calls) == 1
    spend = json.loads(canonical_owner_state.read_text())["spend"]
    assert spend["reserved_usd"] == "3.320000"
    assert spend["actual_usd"] == "0"
