"""Accountable effect ledger for every externally declared Twinklr config path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ConfigDispositionKind(StrEnum):
    EFFECT_TEST = "effect_test"
    INVARIANT_TEST = "invariant_test"
    REMOVED = "removed"


@dataclass(frozen=True)
class ConfigDisposition:
    kind: ConfigDispositionKind
    test_nodeid: str | None
    note: str


CONFIG_EFFECTS: dict[str, ConfigDisposition] = {
    "app.project_root": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_loader.py::test_load_config_json",
        "public behavior discriminator",
    ),
    "app.output_dir": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "app.cache_dir": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_loader.py::test_load_config_json",
        "public behavior discriminator",
    ),
    "app.audio_processing": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer.py::TestAudioAnalyzer::test_static_minimal_features_structure",
        "public behavior discriminator",
    ),
    "app.audio_processing.hop_length": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer.py::TestAudioAnalyzer::test_static_minimal_features_structure",
        "public behavior discriminator",
    ),
    "app.audio_processing.frame_length": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer.py::TestAudioAnalyzer::test_static_minimal_features_structure",
        "public behavior discriminator",
    ),
    "app.audio_processing.rhythm_source": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/mir/test_analyzer_integration.py::test_selected_sources_feed_one_feature_truth_and_preserve_custom_analysis",
        "public behavior discriminator",
    ),
    "app.audio_processing.structure_source": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/mir/test_analyzer_integration.py::test_selected_sources_feed_one_feature_truth_and_preserve_custom_analysis",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.enable_metadata": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.enable_lyrics": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.enable_phonemes": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.enable_acoustid": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.enable_musicbrainz": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.enable_lyrics_lookup": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.enable_whisperx": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.stems": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_stems_stage.py::test_outer_cache_rejects_false_gate_after_threshold_opens",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.stems.enabled": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_stems_stage.py::test_outer_cache_rejects_false_gate_after_threshold_opens",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.stems.model_name": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_stems_stage.py::test_outer_cache_rejects_false_gate_after_threshold_opens",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.stems.vocal_presence_threshold": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_stems_stage.py::test_outer_cache_rejects_false_gate_after_threshold_opens",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.lyrics_require_timed": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.lyrics_min_coverage": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.lyrics_language": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.whisperx_model": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.whisperx_device": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.whisperx_batch_size": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.whisperx_return_char_alignments": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.phoneme_enable_g2p_fallback": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "app.audio_processing.enhancements.phoneme_min_duration_ms": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.phoneme_vowel_weight": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.phoneme_consonant_weight": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.viseme_min_hold_ms": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.viseme_min_burst_ms": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.viseme_boundary_soften_ms": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.viseme_mapping_version": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.acoustid_api_key": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.genius_access_token": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.musicbrainz_rate_limit_rps": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.musicbrainz_timeout_s": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_enhancement_factory_rate_limit.py::test_http_retry_and_timeout_config_reaches_request_owners",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.http_max_retries": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_enhancement_factory_rate_limit.py::test_http_retry_and_timeout_config_reaches_request_owners",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.http_timeout_s": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_enhancement_factory_rate_limit.py::test_http_retry_and_timeout_config_reaches_request_owners",
        "public behavior discriminator",
    ),
    "app.audio_processing.enhancements.http_circuit_breaker_threshold": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T4 removed; P4-T6 must delete stale documentation",
    ),
    "app.audio_processing.enhancements.http_circuit_breaker_timeout_s": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T4 removed; P4-T6 must delete stale documentation",
    ),
    "app.logging": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/cli/test_logging_config.py::test_run_pipeline_configures_logging_from_app_config",
        "public behavior discriminator",
    ),
    "app.logging.level": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/cli/test_logging_config.py::test_run_pipeline_configures_logging_from_app_config",
        "public behavior discriminator",
    ),
    "app.logging.format": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/cli/test_logging_config.py::test_run_pipeline_configures_logging_from_app_config",
        "public behavior discriminator",
    ),
    "app.llm_api_key": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/test_session.py::test_llm_provider_dispatches_from_app_config",
        "public behavior discriminator",
    ),
    "app.llm_provider": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/test_session.py::test_llm_provider_dispatches_from_app_config",
        "public behavior discriminator",
    ),
    "app.llm_base_url": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/test_session.py::test_llm_provider_dispatches_from_app_config",
        "public behavior discriminator",
    ),
    "job.schema_version": ConfigDisposition(
        ConfigDispositionKind.INVARIANT_TEST,
        "tests/unit/config/test_config_inventory.py::test_fixed_policy_config_paths_are_invariant",
        "one accepted version, 3.1; an undeclared one fails validation",
    ),
    "job.moving_heads": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_mh_render_policy.py::"
        "test_loading_a_job_on_a_rig_without_profiles_is_rejected_before_execution",
        "the policy's initial states decide whether loading the job with its fixtures passes",
    ),
    "job.fixture_config_path": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/pipeline/test_display_pipeline_wiring.py::test_job_config_controls_display_planner_iterations_and_threshold",
        "public behavior discriminator",
    ),
    "job.agent": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/pipeline/test_display_pipeline_wiring.py::test_job_config_controls_display_planner_iterations_and_threshold",
        "public behavior discriminator",
    ),
    "job.agent.max_iterations": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/shared/judge/test_controller.py::test_max_iterations_zero_skips_judge",
        "public behavior discriminator",
    ),
    "job.agent.success_threshold": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/cli/test_run_contract.py::test_success_threshold_from_config_single_scale",
        "public behavior discriminator",
    ),
    "job.agent.plan_agent": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.plan_agent.model": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.plan_agent.reasoning_effort": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.plan_agent.temperature": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.plan_agent.max_tokens": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.plan_agent.timeout_seconds": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.judge_agent": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.judge_agent.model": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.judge_agent.reasoning_effort": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.judge_agent.temperature": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.judge_agent.max_tokens": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.judge_agent.timeout_seconds": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.refinement_agent": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.refinement_agent.model": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.refinement_agent.reasoning_effort": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.refinement_agent.temperature": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.refinement_agent.max_tokens": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.refinement_agent.timeout_seconds": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.profile_agent": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.profile_agent.model": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.profile_agent.reasoning_effort": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.profile_agent.temperature": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.profile_agent.max_tokens": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.profile_agent.timeout_seconds": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.lyrics_agent": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.lyrics_agent.model": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.lyrics_agent.reasoning_effort": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.lyrics_agent.temperature": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.lyrics_agent.max_tokens": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.lyrics_agent.timeout_seconds": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.asset_enricher_agent": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.asset_enricher_agent.model": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.asset_enricher_agent.reasoning_effort": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.asset_enricher_agent.temperature": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.asset_enricher_agent.max_tokens": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.asset_enricher_agent.timeout_seconds": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::test_configured_model_reaches_fake_provider",
        "public behavior discriminator",
    ),
    "job.agent.recipe_generation_agent": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.agent.recipe_generation_agent.model": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.agent.recipe_generation_agent.reasoning_effort": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.agent.recipe_generation_agent.temperature": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.agent.recipe_generation_agent.max_tokens": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.agent.recipe_generation_agent.timeout_seconds": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.agent.image_model": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/assets/test_stage.py::test_execute_persists_generated_and_text_assets",
        "public behavior discriminator",
    ),
    "job.agent.llm_logging": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/logging/test_async_file_logger_verbosity.py::test_log_full_prompts_flag_enables_content_at_debug",
        "public behavior discriminator",
    ),
    "job.agent.llm_logging.enabled": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/logging/test_async_file_logger_verbosity.py::test_log_full_prompts_flag_enables_content_at_debug",
        "public behavior discriminator",
    ),
    "job.agent.llm_logging.log_path": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/logging/test_async_file_logger_verbosity.py::test_log_full_prompts_flag_enables_content_at_debug",
        "public behavior discriminator",
    ),
    "job.agent.llm_logging.log_level": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/logging/test_async_file_logger_verbosity.py::test_log_full_prompts_flag_enables_content_at_debug",
        "public behavior discriminator",
    ),
    "job.agent.llm_logging.format": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/logging/test_async_file_logger_verbosity.py::test_log_full_prompts_flag_enables_content_at_debug",
        "public behavior discriminator",
    ),
    "job.agent.llm_logging.sanitize": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/test_session.py::test_llm_logging_sanitize_reaches_logger_factory",
        "public behavior discriminator",
    ),
    "job.agent.agent_cache": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/caching/test_cache_identity.py::TestCacheRootAnchoring::test_cache_root_is_cwd_independent",
        "public behavior discriminator",
    ),
    "job.agent.agent_cache.enabled": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/caching/test_cache_identity.py::TestCacheRootAnchoring::test_cache_root_is_cwd_independent",
        "public behavior discriminator",
    ),
    "job.agent.agent_cache.cache_path": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/caching/test_cache_identity.py::TestCacheRootAnchoring::test_cache_root_is_cwd_independent",
        "public behavior discriminator",
    ),
    "job.agent.agent_cache.ttl_seconds": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/caching/test_cache_identity.py::TestCacheRootAnchoring::test_cache_root_is_cwd_independent",
        "public behavior discriminator",
    ),
    "job.assets": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/assets/test_stage.py::test_dry_run_reports_without_provider_calls",
        "public behavior discriminator",
    ),
    "job.assets.enabled": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/assets/test_stage.py::test_dry_run_reports_without_provider_calls",
        "public behavior discriminator",
    ),
    "job.assets.dry_run": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/assets/test_stage.py::test_dry_run_reports_without_provider_calls",
        "public behavior discriminator",
    ),
    "job.assets.max_image_requests_per_run": ConfigDisposition(
        ConfigDispositionKind.INVARIANT_TEST,
        "tests/unit/config/test_config_inventory.py::test_fixed_policy_config_paths_are_invariant",
        "public behavior discriminator",
    ),
    "job.assets.estimated_image_usd_per_request": ConfigDisposition(
        ConfigDispositionKind.INVARIANT_TEST,
        "tests/unit/config/test_config_inventory.py::test_fixed_policy_config_paths_are_invariant",
        "public behavior discriminator",
    ),
    "job.assets.image_quality": ConfigDisposition(
        ConfigDispositionKind.INVARIANT_TEST,
        "tests/unit/config/test_config_inventory.py::test_fixed_policy_config_paths_are_invariant",
        "public behavior discriminator",
    ),
    "job.assets.asset_base_path": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/assets/test_stage.py::test_dry_run_reports_without_provider_calls",
        "public behavior discriminator",
    ),
    "job.output_dir": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.project_name": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.write_checkpoint": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/sequencer/moving_heads/test_stage.py::TestMovingHeadStageCheckpointWriter::test_checkpoint_disabled_by_config",
        "public behavior discriminator",
    ),
    "job.timeline_tracks": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/formats/xlights/sequence/test_timeline.py::TestBuildTimelineTracks::test_config_disables_tracks",
        "public behavior discriminator",
    ),
    "job.timeline_tracks.beats": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/formats/xlights/sequence/test_timeline.py::TestBuildTimelineTracks::test_config_disables_tracks",
        "public behavior discriminator",
    ),
    "job.timeline_tracks.bars": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/formats/xlights/sequence/test_timeline.py::TestBuildTimelineTracks::test_config_disables_tracks",
        "public behavior discriminator",
    ),
    "job.timeline_tracks.sections": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/formats/xlights/sequence/test_timeline.py::TestBuildTimelineTracks::test_sections_config_gates_public_track_builder[sections-disabled]",
        "false disables section emission through the public track builder",
    ),
    "job.timeline_tracks.lyrics": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/formats/xlights/sequence/test_timeline.py::TestBuildTimelineTracks::test_config_disables_tracks",
        "public behavior discriminator",
    ),
    "job.timeline_tracks.phonemes": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/formats/xlights/sequence/test_timeline.py::TestBuildTimelineTracks::test_config_disables_tracks",
        "public behavior discriminator",
    ),
    "fixture.group_id": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_universe": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.channel_count": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.pan_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.pan_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.pan_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.tilt_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.tilt_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.dimmer_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.dimmer_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.dimmer_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.dimmer_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.dimmer_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.dimmer_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.dimmer_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.dimmer_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.dimmer_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_fine_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_fine_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_fine_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_fine_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_fine_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_fine_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.pan_fine_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_fine_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_fine_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_fine_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_fine_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_fine_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_fine_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.tilt_fine_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.shutter_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.shutter_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.shutter_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.shutter_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.shutter_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.shutter_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.shutter_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.shutter_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.shutter_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.color_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.color_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.color_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.color_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.color_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.color_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.color_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.color_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.color_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.gobo_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.gobo_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.gobo_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.gobo_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.gobo_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.gobo_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.gobo_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.gobo_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.dmx_mapping.gobo_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.orientation.tilt_up_dmx": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.orientation.tilt_above_horizon_deg": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.orientation.resting_position": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.orientation.resting_position.pan_dmx": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.orientation.resting_position.tilt_dmx": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.orientation.resting_position.description": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.capabilities": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.capabilities.has_color_wheel": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.capabilities.has_gobo_wheel": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.capabilities.has_prism": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.capabilities.has_zoom": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.capabilities.has_iris": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.capabilities.has_frost": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.capabilities.beam_angle_deg": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.movement_speed": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.movement_speed.pan_speed_deg_per_sec": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.movement_speed.tilt_speed_deg_per_sec": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.movement_speed.color_change_ms": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.base_config.movement_speed.gobo_change_ms": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].fixture_id": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureInstance::test_instance_id_sync",
        "fixture identity changes synchronized public instance",
    ),
    "fixture.fixtures[SimplifiedFixtureInstance].fixture_id": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "simplified fixture identity is proven through its expansion seam",
    ),
    "fixture.fixtures[FixtureInstance].config": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureInstance::test_instance_id_sync",
        "fixture identity changes synchronized public instance",
    ),
    "fixture.fixtures[FixtureInstance].config.fixture_id": ConfigDisposition(
        ConfigDispositionKind.INVARIANT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureInstance::test_instance_id_sync",
        "outer fixture identity is the invariant authority and overwrites this nested value",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_universe": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_start_address": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.channel_count": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_channel]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_channel.channel]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_channel]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_channel.channel]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.dimmer_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping.dimmer_channel]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.dimmer_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping.dimmer_channel.channel]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.dimmer_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.dimmer_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.dimmer_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.dimmer_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.dimmer_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.dimmer_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.dimmer_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_fine_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_fine_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_fine_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_fine_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_fine_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_fine_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.pan_fine_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_fine_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_fine_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_fine_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_fine_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_fine_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_fine_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.tilt_fine_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.shutter_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping.shutter_channel]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.shutter_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping.shutter_channel.channel]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.shutter_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.shutter_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.shutter_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.shutter_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.shutter_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.shutter_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.shutter_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.color_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping.color_channel]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.color_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping.color_channel.channel]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.color_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.color_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.color_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.color_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.color_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.color_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.color_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.gobo_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping.gobo_channel]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.gobo_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].config.dmx_mapping.gobo_channel.channel]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.gobo_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.gobo_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.gobo_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.gobo_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.gobo_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.gobo_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.dmx_mapping.gobo_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.orientation.tilt_up_dmx": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.orientation.tilt_above_horizon_deg": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.orientation.resting_position": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.orientation.resting_position.pan_dmx": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.orientation.resting_position.tilt_dmx": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.orientation.resting_position.description": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.capabilities": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.capabilities.has_color_wheel": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.capabilities.has_gobo_wheel": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.capabilities.has_prism": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.capabilities.has_zoom": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.capabilities.has_iris": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.capabilities.has_frost": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.capabilities.beam_angle_deg": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.movement_speed": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.movement_speed.pan_speed_deg_per_sec": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.movement_speed.tilt_speed_deg_per_sec": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.movement_speed.color_change_ms": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.movement_speed.gobo_change_ms": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[FixtureInstance].config.position": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_position_index_changes_rig_order",
        "non-default changes rig fixture order",
    ),
    "fixture.fixtures[FixtureInstance].config.position.position_index": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_position_index_changes_rig_order",
        "non-default changes rig fixture order",
    ),
    "fixture.fixtures[FixtureInstance].xlights_model_name": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[FixtureInstance].xlights_model_name]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[SimplifiedFixtureInstance].xlights_model_name": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.fixtures[SimplifiedFixtureInstance].xlights_model_name]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "fixture.fixtures[SimplifiedFixtureInstance].dmx_start_address": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures[SimplifiedFixtureInstance].position": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.fixtures[SimplifiedFixtureInstance].position.position_index": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.fixtures[SimplifiedFixtureInstance].config_overrides": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.xlights_group": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_fixture_field_changes_shipped_behavior_snapshot[fixture.xlights_group]",
        "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
    ),
    "template.enabled": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_registration_field_changes_public_registry[template.enabled]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_registration_field_changes_public_registry[template.template]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.template_id": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_registration_field_changes_public_registry[template.template.template_id]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.version": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_registration_field_changes_public_registry[template.template.version]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.name": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_registration_field_changes_public_registry[template.template.name]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.category": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_registration_field_changes_public_registry[template.template.category]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.roles": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.repeat": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.repeat]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.repeat.repeatable": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.repeat.mode": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.repeat.mode]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.repeat.cycle_bars": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.repeat.cycle_bars]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.repeat.loop_step_ids": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.repeat.loop_step_ids]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.repeat.remainder_policy": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.repeat.remainder_policy]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.steps": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.steps]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.steps.step_id": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.steps.step_id]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.steps.target": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.steps.target]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.steps.timing": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.steps.timing]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.steps.timing.base_timing": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.steps.timing.base_timing]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.steps.timing.base_timing.mode": ConfigDisposition(
        ConfigDispositionKind.INVARIANT_TEST,
        "tests/unit/config/test_config_inventory.py::test_fixed_policy_config_paths_are_invariant",
        "public behavior discriminator",
    ),
    "template.template.steps.timing.base_timing.quantize_type": ConfigDisposition(
        ConfigDispositionKind.INVARIANT_TEST,
        "tests/unit/config/test_config_inventory.py::test_fixed_policy_config_paths_are_invariant",
        "public behavior discriminator",
    ),
    "template.template.steps.timing.base_timing.start_offset_bars": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.steps.timing.base_timing.start_offset_bars]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.steps.timing.base_timing.duration_bars": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.steps.timing.base_timing.duration_bars]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.steps.timing.phase_offset.group": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.timing.phase_offset.distribution": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.movement": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.steps.movement]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.steps.movement.amplitude_override": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.movement.frequency_override": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.movement.center_offset_override": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.dimmer": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_compile_field_changes_emitted_snapshot[template.template.steps.dimmer]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.steps.dimmer.cycles": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.color.params": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.shutter.params": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.gobo.params": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.entry_transition": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.entry_transition.mode": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.entry_transition.duration_bars": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.entry_transition.curve": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.exit_transition": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.exit_transition.mode": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.exit_transition.duration_bars": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.exit_transition.curve": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.priority": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.blend_mode": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.metadata": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_registration_field_changes_public_registry[template.template.metadata]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.metadata.tags": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_registration_field_changes_public_registry[template.template.metadata.tags]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.metadata.recommended_sections": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_metadata_field_changes_planner_prompt_context[template.template.metadata.recommended_sections]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.metadata.energy_range": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_metadata_field_changes_planner_prompt_context[template.template.metadata.energy_range]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.template.metadata.description": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_metadata_field_changes_planner_prompt_context[template.template.metadata.description]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.presets": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_preset_field_changes_compiled_snapshot[template.presets]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.presets.preset_id": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_preset_field_changes_compiled_snapshot[template.presets.preset_id]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.presets.step_patches": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_preset_field_changes_compiled_snapshot[template.presets.step_patches]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.presets.step_patches.movement": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_preset_field_changes_compiled_snapshot[template.presets.step_patches.movement]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.presets.step_patches.dimmer": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_preset_field_changes_compiled_snapshot[template.presets.step_patches.dimmer]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "template.presets.step_patches.timing": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        "test_template_preset_field_changes_compiled_snapshot[template.presets.step_patches.timing]",
        "exact path changes a shipped registry, planner, preset, or compile seam, or makes the compile refuse the template",
    ),
    "app.audio_processing.cache_enabled": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "app.planning": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.include_notes_track": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.debug": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.assumptions": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.agent.token_budget": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.agent.enforce_token_budget": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.agent.token_buffer_pct": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.agent.vision_judge_agent": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.pose_config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "job.planner_features": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "app.audio_processing.enhancements.metadata_merge_policy_version": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "app.audio_processing.enhancements.metadata_min_confidence_warn": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "analysis.sectioning_preset.context_weights": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "analysis.energy_profile.gradient_percentile": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
}

PROTECTED_EXACT_EFFECT_PATHS = frozenset({"job.timeline_tracks.sections"})

# The entries above as written, before the loops below route paths to their
# parameterized tests; the guard at the end of the module checks them.
_STATIC_EFFECTS = dict(CONFIG_EFFECTS)

# Parameterized discriminators below use the canonical path itself as the pytest ID;
# each case mutates that exact field and observes a production expansion/export seam.
for _fixture_path, _fixture_disposition in tuple(CONFIG_EFFECTS.items()):
    if _fixture_path.startswith("fixture.") and (
        _fixture_disposition.kind is ConfigDispositionKind.EFFECT_TEST
    ):
        if _fixture_path in PROTECTED_EXACT_EFFECT_PATHS:
            continue
        CONFIG_EFFECTS[_fixture_path] = ConfigDisposition(
            ConfigDispositionKind.EFFECT_TEST,
            "tests/unit/config/test_effect_discriminators.py::"
            f"test_fixture_field_changes_shipped_behavior_snapshot[{_fixture_path}]",
            "exact path changes expansion, rig order, or the planner's xLights group mapping or channel listing",
        )

# Physical-profile and run initial-state fields feed the moving-head renderer. Registered
# after the loop above, each exact path mutates its field and must change the one component of
# the profile and initial-state contract its note names. "Identity only" paths have no
# consumer beyond the render fingerprint; the task that adds one repoints them.
_PROFILE_REJECTED = "exact path's alternative values are rejected by validation"
_PROFILE_WORDS = "exact path changes the encoded DMX word"
_PROFILE_CHECK = "exact path changes the initial-state check"
_PROFILE_IDENTITY_ONLY = "identity only; no consumer yet"
_PROFILE_PREPOSITION = "exact path changes the planned preposition transactions"
_PROFILE_DARKNESS = "exact path changes which planned cues start dark"
_PROFILE_FRAMES = "exact path changes the encoded fixture frames"
_PROFILE_CHANGES = "exact path changes the listed wheel state changes"
_PROFILE_FIELDS = {
    "": _PROFILE_WORDS,
    "schema_version": _PROFILE_REJECTED,
    "profile_id": _PROFILE_IDENTITY_ONLY,
    "provenance": _PROFILE_PREPOSITION,
    "footprint": _PROFILE_FRAMES,
    "defaults": _PROFILE_FRAMES,
    "axes": _PROFILE_WORDS,
    "axes.unit": _PROFILE_REJECTED,
    "axes.physical_min": _PROFILE_WORDS,
    "axes.physical_max": _PROFILE_WORDS,
    "axes.allowed_min": _PROFILE_WORDS,
    "axes.allowed_max": _PROFILE_WORDS,
    "axes.coarse_offset": _PROFILE_FRAMES,
    "axes.fine_offset": _PROFILE_WORDS,
    "axes.inverted": _PROFILE_WORDS,
    "axes.dmx_min": _PROFILE_WORDS,
    "axes.dmx_max": _PROFILE_WORDS,
    "axes.travel_speed_per_s": _PROFILE_PREPOSITION,
    "axes.latency_ms": _PROFILE_PREPOSITION,
    "axes.settle_ms": _PROFILE_PREPOSITION,
    "discrete": _PROFILE_CHECK,
    "discrete.offset": _PROFILE_FRAMES,
    "discrete.states": _PROFILE_CHECK,
    "discrete.states.range_min": _PROFILE_IDENTITY_ONLY,
    "discrete.states.range_max": _PROFILE_IDENTITY_ONLY,
    "discrete.states.value": _PROFILE_FRAMES,
    "discrete.states.settle_ms": _PROFILE_CHANGES,
    "discrete.settle_ms": _PROFILE_CHANGES,
    "discrete.default_state": _PROFILE_CHANGES,
    "discrete.closed_state": _PROFILE_PREPOSITION,
    "visibility": _PROFILE_PREPOSITION,
    "visibility.dimmer_zero_extinguishes": _PROFILE_DARKNESS,
    "visibility.extinguishing_shutter_states": _PROFILE_DARKNESS,
    "visibility.close_latency_ms": _PROFILE_PREPOSITION,
    "visibility.open_latency_ms": _PROFILE_PREPOSITION,
}
for _profile_root in (
    "fixture.fixtures[FixtureInstance].config.physical_profile",
    "fixture.base_config.physical_profile",
):
    for _field, _note in _PROFILE_FIELDS.items():
        _physical_path = f"{_profile_root}.{_field}" if _field else _profile_root
        CONFIG_EFFECTS[_physical_path] = ConfigDisposition(
            ConfigDispositionKind.EFFECT_TEST,
            "tests/unit/config/test_mh_capabilities.py::"
            f"test_physical_profile_field_changes_contract[{_physical_path}]",
            _note,
        )
# Song-intent meaning tags on discrete states (W1) and the `offer: false` opt-out. `hex`
# and `pattern` decide the wheel state a section's colour and gobo play (W4), `strobe` the
# shutter state a strobe event plays (W6): each path must change the frames of a plan
# that sets one. `offer: false` is identity only (an opted-out state is not offered, as an
# untagged one).
_TAG_EFFECTS = {
    "hex": (
        "test_state_tag_changes_what_a_section_plays",
        "a section's colour plays the tagged state (song-intent W4)",
    ),
    "pattern": (
        "test_state_tag_changes_what_a_section_plays",
        "a section's gobo plays the tagged state (song-intent W4)",
    ),
    "strobe": (
        "test_state_tag_changes_what_a_section_plays",
        "a strobe event plays the tagged shutter state (song-intent W6)",
    ),
    "offer": (
        "test_state_tag_changes_identity_not_output",
        "identity only: an opted-out state is offered nothing, as an untagged one (W3)",
    ),
}
for _profile_root in (
    "fixture.fixtures[FixtureInstance].config.physical_profile",
    "fixture.base_config.physical_profile",
):
    for _tag, (_test, _note) in _TAG_EFFECTS.items():
        _tag_path = f"{_profile_root}.discrete.states.{_tag}"
        CONFIG_EFFECTS[_tag_path] = ConfigDisposition(
            ConfigDispositionKind.EFFECT_TEST,
            f"tests/unit/config/test_mh_state_tags.py::{_test}[{_tag_path}]",
            _note,
        )
for _field, _note in {
    "": _PROFILE_CHECK,
    "pan_deg": _PROFILE_CHECK,
    "tilt_deg": _PROFILE_CHECK,
    "zoom_deg": _PROFILE_CHECK,
    "dimmer": _PROFILE_CHECK,
    "discrete_states": _PROFILE_CHECK,
    "settled": _PROFILE_PREPOSITION,
    "dark": _PROFILE_PREPOSITION,
}.items():
    _initial_state_path = "job.moving_heads.initial_states" + (f".{_field}" if _field else "")
    CONFIG_EFFECTS[_initial_state_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_mh_capabilities.py::"
        f"test_initial_state_field_changes_contract[{_initial_state_path}]",
        _note,
    )

# P1.3 output budgets. They bound only moving-head output, so each exact path is
# evidenced by a fixed render that its limit accepts at the measured size and
# rejects one below it.
for _budget_path in ("job.moving_heads.max_effects", "job.moving_heads.max_xsq_bytes"):
    CONFIG_EFFECTS[_budget_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_frame_encoder.py::"
        f"test_budget_field_changes_accept_reject[{_budget_path}]",
        "exact path changes whether a fixed moving-head output is accepted or rejected",
    )

_TEMPLATE_REGISTRATION_PATHS = {
    "template.enabled",
    "template.template",
    "template.template.template_id",
    "template.template.version",
    "template.template.name",
    "template.template.category",
    "template.template.metadata",
    "template.template.metadata.tags",
}
_TEMPLATE_METADATA_PATHS = {
    "template.template.metadata.description",
    "template.template.metadata.recommended_sections",
    "template.template.metadata.energy_range",
}
for _template_path, _template_disposition in tuple(CONFIG_EFFECTS.items()):
    if not _template_path.startswith("template.") or (
        _template_disposition.kind is not ConfigDispositionKind.EFFECT_TEST
    ):
        continue
    if _template_path in PROTECTED_EXACT_EFFECT_PATHS:
        continue
    if _template_path in _TEMPLATE_REGISTRATION_PATHS:
        _template_test = "test_template_registration_field_changes_public_registry"
    elif _template_path in _TEMPLATE_METADATA_PATHS:
        _template_test = "test_template_metadata_field_changes_planner_prompt_context"
    elif _template_path.startswith("template.presets"):
        _template_test = "test_template_preset_field_changes_compiled_snapshot"
    else:
        _template_test = "test_template_compile_field_changes_emitted_snapshot"
    CONFIG_EFFECTS[_template_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_template_effect_discriminators.py::"
        f"{_template_test}[{_template_path}]",
        "exact path changes a shipped registry, planner, preset, or compile seam, "
        "or makes the compile refuse the template",
    )

# P1.2 template step fields. They feed the step compile; registered after the loop
# above, each exact path mutates its field and must either change `compile_step`'s
# result or be rejected by validation or compile. Since C1.4 flattened `movement.physical`
# and `dimmer.physical`, `movement` and `dimmer` are these paths, so the entries here
# replace that loop's for them (its two snapshot cases still run). `shape` is coupled to
# `mode`, extents and period, so no single-field alternative is valid; its evidence is
# the kernel test, which fails if the compiler ignored it.
_TEMPLATE_REJECTED = "exact path's alternative is rejected by validation or compile"
_TEMPLATE_COMPILED = "exact path changes the compile result"
for _field, _note in {
    "movement": _TEMPLATE_REJECTED,
    "movement.mode": _TEMPLATE_REJECTED,
    "movement.start_pan_deg": _TEMPLATE_COMPILED,
    "movement.start_tilt_deg": _TEMPLATE_COMPILED,
    "movement.pan_extent_deg": _TEMPLATE_COMPILED,
    "movement.tilt_extent_deg": _TEMPLATE_COMPILED,
    "movement.period_beats": _TEMPLATE_COMPILED,
    "dimmer": _TEMPLATE_COMPILED,
    "dimmer.period_beats": _TEMPLATE_COMPILED,
    "dimmer.duty_cycle": _TEMPLATE_COMPILED,
    "dimmer.phase_cycles": _TEMPLATE_COMPILED,
    "dimmer.low": _TEMPLATE_COMPILED,
    "dimmer.high": _TEMPLATE_COMPILED,
    "shutter": _TEMPLATE_COMPILED,
    "shutter.period_beats": _TEMPLATE_COMPILED,
    "shutter.duty_cycle": _TEMPLATE_COMPILED,
    "shutter.phase_cycles": _TEMPLATE_COMPILED,
    "shutter.low_state": _TEMPLATE_COMPILED,
    "shutter.high_state": _TEMPLATE_COMPILED,
}.items():
    _step_field_path = f"template.template.steps.{_field}"
    CONFIG_EFFECTS[_step_field_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_step.py::"
        f"test_step_field_changes_compile[{_step_field_path}]",
        _note,
    )
CONFIG_EFFECTS["template.template.steps.movement.shape"] = ConfigDisposition(
    ConfigDispositionKind.EFFECT_TEST,
    "tests/unit/sequencer/moving_heads/compile/test_step.py::"
    "test_each_kernel_shapes_the_compiled_path[sine_tilt]",
    "each kernel shapes the compiled path",
)

# P1.4 discrete template step fields: named shutter, color and gobo states held
# for a step. Like P1.2's, they feed the step compile; each exact
# path selects another declared state and must change `compile_step`'s
# result, so a compile that ignored the field fails its case.
for _field in ("shutter_state", "color", "gobo"):
    _step_field_path = f"template.template.steps.{_field}"
    CONFIG_EFFECTS[_step_field_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_step_discrete.py::"
        f"test_discrete_field_changes_compile[{_step_field_path}]",
        _TEMPLATE_COMPILED,
    )

# P2.4a reposition fallbacks: a step's opt-in and the job's policy, both required. Each
# exact path is evidenced by a render whose cue that cannot be repositioned is
# kept dark with both set and refused once that one path is back at its default.
for _fallback_path in (
    "template.template.steps.reposition_fallback",
    "job.moving_heads.reposition_fallback",
):
    CONFIG_EFFECTS[_fallback_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_entry_window.py::"
        f"test_reposition_fallback_field_changes_preposition[{_fallback_path}]",
        "exact path changes whether a cue that cannot be repositioned is kept dark or the "
        "render is refused",
    )

# What a render does with a cue the plan placed where it cannot play. Evidenced
# by a render that keeps such a cue dark at the default and is refused under `error`.
CONFIG_EFFECTS["job.moving_heads.on_unplayable"] = ConfigDisposition(
    ConfigDispositionKind.EFFECT_TEST,
    "tests/unit/sequencer/moving_heads/compile/test_unplayable.py::"
    "test_on_unplayable_field_changes_the_render",
    "exact path changes whether an unplayable cue is kept dark or the render is refused",
)

# P2.1 named rig components: a fixture group's position and attribute presets and the
# step references that name them. They feed the compile; each
# exact path mutates its field and must either change `compile_template`'s
# result or be refused by validation or compile (a reference that no longer resolves).
for _component_path, _note in {
    "fixture.presets": _TEMPLATE_REJECTED,
    "fixture.presets.positions": _TEMPLATE_REJECTED,
    "fixture.presets.positions.fixtures": _TEMPLATE_COMPILED,
    "fixture.presets.positions.fixtures.pan_deg": _TEMPLATE_COMPILED,
    "fixture.presets.positions.fixtures.tilt_deg": _TEMPLATE_COMPILED,
    "fixture.presets.positions.fallback": _TEMPLATE_COMPILED,
    "fixture.presets.attributes": _TEMPLATE_REJECTED,
    "fixture.presets.attributes.fixtures": _TEMPLATE_COMPILED,
    "fixture.presets.attributes.fixtures.shutter": _TEMPLATE_COMPILED,
    "fixture.presets.attributes.fixtures.color": _TEMPLATE_COMPILED,
    "fixture.presets.attributes.fixtures.gobo": _TEMPLATE_COMPILED,
    "fixture.presets.attributes.fixtures.dimmer": _TEMPLATE_COMPILED,
    "fixture.presets.attributes.fallback": _TEMPLATE_COMPILED,
    "template.template.steps.component_refs": _TEMPLATE_REJECTED,
    "template.template.steps.component_refs.position_id": _TEMPLATE_COMPILED,
    "template.template.steps.component_refs.attribute_preset_ids": _TEMPLATE_COMPILED,
}.items():
    CONFIG_EFFECTS[_component_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_component_presets.py::"
        f"test_component_preset_field_changes_compile[{_component_path}]",
        _note,
    )

# P2.2 rig topology and phase distribution: a fixture group's canonical rig and the step
# distributions that spread phase over it. They feed the compile;
# each exact path mutates its field and must either change the compiled pan, tilt,
# dimmer or shutter values or be refused (a distribution on a rig left without topology).
for _topology_path, _note in {
    "fixture.topology": _TEMPLATE_REJECTED,
    "fixture.topology.members": _TEMPLATE_COMPILED,
    "fixture.topology.members.fixture_id": _TEMPLATE_COMPILED,
    "fixture.topology.members.row": _TEMPLATE_COMPILED,
    "fixture.topology.members.column": _TEMPLATE_COMPILED,
    "fixture.topology.members.ordinal": _TEMPLATE_COMPILED,
    "template.template.steps.distribution": _TEMPLATE_COMPILED,
    "template.template.steps.distribution.domains": _TEMPLATE_COMPILED,
    "template.template.steps.distribution.block_size": _TEMPLATE_COMPILED,
    "template.template.steps.distribution.group_count": _TEMPLATE_COMPILED,
    "template.template.steps.distribution.wings": _TEMPLATE_COMPILED,
    "template.template.steps.distribution.spread_cycles": _TEMPLATE_COMPILED,
    "template.template.steps.distribution.direction": _TEMPLATE_COMPILED,
}.items():
    CONFIG_EFFECTS[_topology_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_topology_phase.py::"
        f"test_topology_field_changes_compile[{_topology_path}]",
        _note,
    )

# P2.3 relative paths: the template-owned transform of a circle, lissajous or sweep and
# the lissajous frequency ratio. They feed the compile; each exact
# path mutates its field and must change the compiled pan and tilt values. The `ONCE`
# repeat value has no path of its own: `template.template.repeat.mode` keeps its
# discriminator, and ONCE's scheduling is tested in the same module.
for _path_field in (
    "transform",
    "transform.rotation_deg",
    "transform.reverse",
    "transform.phase_cycles",
    "lissajous_ratio",
):
    _path_path = f"template.template.steps.movement.{_path_field}"
    CONFIG_EFFECTS[_path_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_paths.py::"
        f"test_path_field_changes_compile[{_path_path}]",
        _TEMPLATE_COMPILED,
    )

# P2.4b visibility envelopes and attribute overlays: a step's lit window and the
# template's temporary wheel states. They feed the compile; each
# exact path mutates its field and must change the compiled cues or be refused. The
# profile's `discrete.open_state`, identity-only until now, is what an envelope step
# without a static shutter state is lit through; its records are repointed here.
for _visibility_path, _note in {
    "template.template.steps.visibility": _TEMPLATE_COMPILED,
    "template.template.steps.visibility.visible_phase_start": _TEMPLATE_COMPILED,
    "template.template.steps.visibility.visible_phase_end": _TEMPLATE_COMPILED,
    "template.template.steps.visibility.attack_beats": _TEMPLATE_COMPILED,
    "template.template.steps.visibility.release_beats": _TEMPLATE_COMPILED,
    "template.template.steps.visibility.level": _TEMPLATE_COMPILED,
    "template.template.overlays": _TEMPLATE_COMPILED,
    "template.template.overlays.start_beats": _TEMPLATE_COMPILED,
    "template.template.overlays.end_beats": _TEMPLATE_COMPILED,
    "template.template.overlays.mask_beats": _TEMPLATE_COMPILED,
    "template.template.overlays.channel": _TEMPLATE_COMPILED,
    "template.template.overlays.state": _TEMPLATE_COMPILED,
    "template.template.overlays.attribute_preset_id": _TEMPLATE_COMPILED,
    "template.template.overlays.release": _TEMPLATE_REJECTED,
}.items():
    CONFIG_EFFECTS[_visibility_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_visibility.py::"
        f"test_visibility_field_changes_compile[{_visibility_path}]",
        _note,
    )
for _profile_root in (
    "fixture.fixtures[FixtureInstance].config.physical_profile",
    "fixture.base_config.physical_profile",
):
    _open_state_path = f"{_profile_root}.discrete.open_state"
    CONFIG_EFFECTS[_open_state_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_visibility.py::"
        f"test_open_state_changes_the_lit_shutter[{_open_state_path}]",
        _TEMPLATE_COMPILED,
    )

# P2.5 zoom pilot: a step's beam angle on a profile's zoom axis. It feeds only the opt-in
# compile; each exact path mutates its field and must change the cues compiled
# on a zoom rig and a zoomless one, or be refused (`if_unsupported` back at `error` on the
# zoomless rig). The profile's `axes.dmx_min`/`dmx_max` and the initial state's
# `zoom_deg` are evidenced with the other profile and initial-state paths above.
for _zoom_path, _note in {
    "template.template.steps.zoom": _TEMPLATE_COMPILED,
    "template.template.steps.zoom.shape": _TEMPLATE_REJECTED,
    "template.template.steps.zoom.start_deg": _TEMPLATE_COMPILED,
    "template.template.steps.zoom.extent_deg": _TEMPLATE_COMPILED,
    "template.template.steps.zoom.if_unsupported": _TEMPLATE_REJECTED,
}.items():
    CONFIG_EFFECTS[_zoom_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_optical_axis.py::"
        f"test_zoom_field_changes_compile[{_zoom_path}]",
        _note,
    )

# Exact App/Job discriminators. These overrides prevent stale generic smoke-test
# pointers from re-entering the accountable ledger.
for _root_path in ("app.project_root", "app.cache_dir"):
    CONFIG_EFFECTS[_root_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/caching/test_cache_identity.py::TestCacheRootAnchoring::"
        f"test_app_cache_path_changes_audio_analyzer_cache_root[{_root_path}]",
        "exact path changes the production analyzer cache root",
    )

for _audio_path in (
    "app.audio_processing",
    "app.audio_processing.hop_length",
    "app.audio_processing.frame_length",
):
    CONFIG_EFFECTS[_audio_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        f"test_audio_window_field_changes_energy_extraction_call[{_audio_path}]",
        "exact path changes the production energy-extraction request",
    )

_PHONEME_PATHS = {
    path
    for path in CONFIG_EFFECTS
    if path.startswith(
        (
            "app.audio_processing.enhancements.phoneme_",
            "app.audio_processing.enhancements.viseme_",
        )
    )
}
_PHONEME_PATHS.add("app.audio_processing.enhancements.enable_phonemes")
for _phoneme_path in _PHONEME_PATHS:
    if CONFIG_EFFECTS[_phoneme_path].kind is ConfigDispositionKind.EFFECT_TEST:
        CONFIG_EFFECTS[_phoneme_path] = ConfigDisposition(
            ConfigDispositionKind.EFFECT_TEST,
            "tests/unit/config/test_effect_discriminators.py::"
            f"test_each_phoneme_field_changes_builder_call[{_phoneme_path}]",
            "exact path changes the production phoneme/viseme builder request",
        )

_ENHANCEMENT_FACTORY_PATHS = {
    "app.audio_processing.enhancements",
    "app.audio_processing.enhancements.enable_metadata",
    "app.audio_processing.enhancements.enable_lyrics",
    "app.audio_processing.enhancements.enable_acoustid",
    "app.audio_processing.enhancements.enable_musicbrainz",
    "app.audio_processing.enhancements.enable_lyrics_lookup",
    "app.audio_processing.enhancements.enable_whisperx",
    "app.audio_processing.enhancements.lyrics_require_timed",
    "app.audio_processing.enhancements.lyrics_min_coverage",
    "app.audio_processing.enhancements.lyrics_language",
    "app.audio_processing.enhancements.whisperx_model",
    "app.audio_processing.enhancements.whisperx_device",
    "app.audio_processing.enhancements.whisperx_batch_size",
    "app.audio_processing.enhancements.whisperx_return_char_alignments",
    "app.audio_processing.enhancements.acoustid_api_key",
    "app.audio_processing.enhancements.genius_access_token",
    "app.audio_processing.enhancements.musicbrainz_rate_limit_rps",
    "app.audio_processing.enhancements.musicbrainz_timeout_s",
    "app.audio_processing.enhancements.http_max_retries",
    "app.audio_processing.enhancements.http_timeout_s",
}
for _enhancement_path in _ENHANCEMENT_FACTORY_PATHS:
    CONFIG_EFFECTS[_enhancement_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_effect_discriminators.py::"
        "test_each_enhancement_factory_field_changes_constructed_services"
        f"[{_enhancement_path}]",
        "exact path changes a production enhancement service constructor",
    )

for _provider_path in ("app.llm_api_key", "app.llm_base_url"):
    CONFIG_EFFECTS[_provider_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/test_session.py::"
        f"test_provider_field_changes_constructor_request[{_provider_path}]",
        "exact path changes the provider constructor request",
    )
CONFIG_EFFECTS["app.llm_provider"] = ConfigDisposition(
    ConfigDispositionKind.EFFECT_TEST,
    "tests/unit/test_session.py::test_provider_selection_changes_constructor_branch",
    "provider selection changes the concrete provider constructor",
)

_ROLE_NAMES = (
    "plan_agent",
    "judge_agent",
    "refinement_agent",
    "profile_agent",
    "lyrics_agent",
    "asset_enricher_agent",
)
for _role_path in (
    path
    for path in CONFIG_EFFECTS
    if path.startswith("job.agent.")
    and any(path.startswith(f"job.agent.{role}") for role in _ROLE_NAMES)
    and CONFIG_EFFECTS[path].kind is ConfigDispositionKind.EFFECT_TEST
):
    CONFIG_EFFECTS[_role_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/test_model_retarget.py::"
        f"test_each_agent_role_field_changes_its_shipped_request[{_role_path}]",
        "exact role path changes the request observed at the provider boundary",
    )

CONFIG_EFFECTS["job.agent.image_model"] = ConfigDisposition(
    ConfigDispositionKind.EFFECT_TEST,
    "tests/unit/agents/assets/test_stage.py::"
    "test_job_image_model_changes_asset_client_request_owner",
    "configured image model changes the production asset client",
)
for _cache_path in (
    "job.agent.agent_cache",
    "job.agent.agent_cache.enabled",
    "job.agent.agent_cache.cache_path",
):
    CONFIG_EFFECTS[_cache_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/caching/test_cache_identity.py::"
        f"test_agent_cache_field_changes_session_cache_owner[{_cache_path}]",
        "exact path changes the session cache implementation or root",
    )
CONFIG_EFFECTS["job.agent.agent_cache.ttl_seconds"] = ConfigDisposition(
    ConfigDispositionKind.EFFECT_TEST,
    "tests/unit/caching/test_cache_identity.py::test_agent_cache_ttl_changes_real_session_expiry",
    "configured TTL changes expiration in the real session cache",
)

for _source_path in (
    "app.audio_processing.rhythm_source",
    "app.audio_processing.structure_source",
):
    CONFIG_EFFECTS[_source_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/mir/test_analyzer_integration.py::"
        f"test_audio_source_field_changes_production_factory_selection[{_source_path}]",
        "exact selector reaches its matching production analyzer factory",
    )

for _stem_path in (
    "app.audio_processing.enhancements.stems",
    "app.audio_processing.enhancements.stems.enabled",
    "app.audio_processing.enhancements.stems.model_name",
):
    CONFIG_EFFECTS[_stem_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_stems_stage.py::"
        f"test_stem_config_field_changes_public_separation_result[{_stem_path}]",
        "exact stem path changes the public separation result",
    )
CONFIG_EFFECTS["app.audio_processing.enhancements.stems.vocal_presence_threshold"] = (
    ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_stems_stage.py::test_stem_threshold_changes_public_vocal_gate",
        "configured threshold changes the downstream vocal gate",
    )
)

for _logging_path in (
    "job.agent.llm_logging",
    "job.agent.llm_logging.enabled",
    "job.agent.llm_logging.log_path",
    "job.agent.llm_logging.log_level",
    "job.agent.llm_logging.format",
    "job.agent.llm_logging.sanitize",
):
    CONFIG_EFFECTS[_logging_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/logging/test_async_file_logger_verbosity.py::"
        f"test_llm_logging_field_changes_actual_session_log_output[{_logging_path}]",
        "exact path changes a completed session call's real file output",
    )

for _asset_path in (
    "job.assets",
    "job.assets.enabled",
    "job.assets.dry_run",
    "job.assets.asset_base_path",
):
    CONFIG_EFFECTS[_asset_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/assets/test_stage.py::"
        f"test_asset_config_field_changes_asset_creation_stage_behavior[{_asset_path}]",
        "exact path changes the production asset stage result or output root",
    )

for _timeline_path in (
    "job.timeline_tracks",
    "job.timeline_tracks.beats",
    "job.timeline_tracks.bars",
    "job.timeline_tracks.lyrics",
    "job.timeline_tracks.phonemes",
):
    if _timeline_path in PROTECTED_EXACT_EFFECT_PATHS:
        continue
    CONFIG_EFFECTS[_timeline_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/test_rendering_pipeline.py::"
        "TestExportDelivery::"
        f"test_timeline_config_field_changes_rendering_stage_delivery_layers[{_timeline_path}]",
        "exact path changes production RenderingStage-to-delivery timing layers",
    )

CONFIG_EFFECTS["job.fixture_config_path"] = ConfigDisposition(
    ConfigDispositionKind.EFFECT_TEST,
    "tests/unit/agents/sequencer/moving_heads/test_rendering_stage.py::"
    "test_load_fixture_config_resolves_relative_job_config_path",
    "configured path changes the production fixture loader target",
)
CONFIG_EFFECTS["job.agent"] = ConfigDisposition(
    ConfigDispositionKind.EFFECT_TEST,
    "tests/unit/pipeline/test_display_pipeline_wiring.py::"
    "test_job_config_controls_display_planner_iterations_and_threshold",
    "configured agent object changes shipped planner iteration and threshold wiring",
)


# Guard: an entry as written names a test that exists, so an entry a loop above routes
# elsewhere can never keep pointing at deleted evidence.
_TESTS_ROOT = Path(__file__).resolve().parents[1]


def _names_a_test(nodeid: str) -> bool:
    """Whether `nodeid`'s file exists and defines its test function."""
    file, *parts = nodeid.split("::")
    path = _TESTS_ROOT / file
    function = parts[-1].split("[")[0] if parts else ""
    return path.is_file() and f"def {function}(" in path.read_text(encoding="utf-8")


_STALE_EFFECTS = sorted(
    path
    for path, disposition in _STATIC_EFFECTS.items()
    if disposition.test_nodeid is not None and not _names_a_test(disposition.test_nodeid)
)
assert not _STALE_EFFECTS, f"ledger entries name missing tests: {_STALE_EFFECTS}"

# Restored angular paths and dwell: each authored knot field changes emitted DMX.
for _knot_field in ("path_knots", "path_knots.phase", "path_knots.x", "path_knots.y"):
    _knot_path = f"template.template.steps.movement.{_knot_field}"
    CONFIG_EFFECTS[_knot_path] = ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/integration/test_mh_restored_movements.py::"
        f"test_path_knot_field_changes_emitted_frames[{_knot_path}]",
        _TEMPLATE_COMPILED,
    )
