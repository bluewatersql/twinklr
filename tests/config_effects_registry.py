"""Accountable effect ledger for every externally declared Twinklr config path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_loader.py::test_load_config_json",
        "public behavior discriminator",
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
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/audio/test_analyzer_metadata_integration.py::TestAudioAnalyzerMetadataIntegration::test_api_clients_initialized_when_needed",
        "public behavior discriminator",
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
        "public behavior discriminator",
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
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/recipe_builder/test_generation.py::test_generate_candidates_uses_central_sol_tier_request_defaults",
        "public behavior discriminator",
    ),
    "job.agent.recipe_generation_agent.model": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/recipe_builder/test_generation.py::test_generate_candidates_uses_central_sol_tier_request_defaults",
        "public behavior discriminator",
    ),
    "job.agent.recipe_generation_agent.reasoning_effort": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/recipe_builder/test_generation.py::test_generate_candidates_uses_central_sol_tier_request_defaults",
        "public behavior discriminator",
    ),
    "job.agent.recipe_generation_agent.temperature": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/recipe_builder/test_generation.py::test_generate_candidates_uses_central_sol_tier_request_defaults",
        "public behavior discriminator",
    ),
    "job.agent.recipe_generation_agent.max_tokens": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/recipe_builder/test_generation.py::test_generate_candidates_uses_central_sol_tier_request_defaults",
        "public behavior discriminator",
    ),
    "job.agent.recipe_generation_agent.timeout_seconds": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/recipe_builder/test_generation.py::test_generate_candidates_uses_central_sol_tier_request_defaults",
        "public behavior discriminator",
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
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_loader.py::test_load_config_json",
        "public behavior discriminator",
    ),
    "job.project_name": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_loader.py::test_load_config_json",
        "public behavior discriminator",
    ),
    "job.write_checkpoint": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/agents/sequencer/moving_heads/test_stage.py::TestMovingHeadStageCheckpointWriter::test_checkpoint_disabled_by_config",
        "public behavior discriminator",
    ),
    "job.transitions": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_transition_planner.py::TestTransitionPlannerBasic::test_plan_with_default_hint",
        "public behavior discriminator",
    ),
    "job.transitions.enabled": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_transition_planner.py::TestTransitionPlannerBasic::test_plan_with_default_hint",
        "public behavior discriminator",
    ),
    "job.transitions.default_duration_bars": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_transition_planner.py::TestTransitionPlannerBasic::test_plan_with_default_hint",
        "public behavior discriminator",
    ),
    "job.transitions.default_mode": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_transition_planner.py::TestTransitionPlannerBasic::test_plan_with_default_hint",
        "public behavior discriminator",
    ),
    "job.transitions.default_curve": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_transition_planner.py::TestTransitionPlannerBasic::test_plan_with_default_hint",
        "public behavior discriminator",
    ),
    "job.transitions.min_section_duration_bars": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_transition_planner.py::TestTransitionPlannerBasic::test_plan_with_default_hint",
        "public behavior discriminator",
    ),
    "job.transitions.allow_overlaps": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_transition_planner.py::TestTransitionPlannerBasic::test_plan_with_default_hint",
        "public behavior discriminator",
    ),
    "job.transitions.per_channel_defaults": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_transition_planner.py::TestTransitionPlannerBasic::test_plan_with_default_hint",
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
        "tests/unit/formats/xlights/sequence/test_timeline.py::TestBuildTimelineTracks::test_config_disables_tracks",
        "public behavior discriminator",
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
    "fixture.base_config.dmx_mapping.pan_fine_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.pan_fine_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
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
    "fixture.base_config.dmx_mapping.tilt_fine_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.tilt_fine_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
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
    "fixture.base_config.dmx_mapping.use_16bit_pan_tilt": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
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
    "fixture.base_config.dmx_mapping.shutter_default": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.shutter_map": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.shutter_map.closed": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.shutter_map.open": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.shutter_map.strobe_slow": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.shutter_map.strobe_medium": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.dmx_mapping.shutter_map.strobe_fast": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
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
    "fixture.base_config.dmx_mapping.color_map": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
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
    "fixture.base_config.dmx_mapping.gobo_map": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.inversions": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.inversions.pan": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.inversions.tilt": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.inversions.dimmer": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.inversions.shutter": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.inversions.color": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.inversions.gobo": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.pan_tilt_range": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.pan_tilt_range.pan_range_deg": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.pan_tilt_range.tilt_range_deg": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.orientation": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.orientation.pan_front_dmx": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.orientation.tilt_zero_dmx": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
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
    "fixture.base_config.limits": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.limits.pan_min": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.limits.pan_max": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.limits.tilt_min": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.limits.tilt_max": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.base_config.limits.avoid_backward": ConfigDisposition(
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
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_get_xlights_mapping",
        "non-default changes public fixture mapping",
    ),
    "fixture.fixtures.fixture_id": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureInstance::test_instance_id_sync",
        "fixture identity changes synchronized public instance",
    ),
    "fixture.fixtures.config": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureInstance::test_instance_id_sync",
        "fixture identity changes synchronized public instance",
    ),
    "fixture.fixtures.config.fixture_id": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureInstance::test_instance_id_sync",
        "fixture identity changes synchronized public instance",
    ),
    "fixture.fixtures.config.dmx_universe": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_start_address": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.channel_count": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.dimmer_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.dimmer_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.dimmer_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.dimmer_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.dimmer_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.dimmer_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.dimmer_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.dimmer_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.dimmer_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_fine_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_fine_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_fine_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_fine_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_fine_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_fine_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_fine_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_fine_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.pan_fine_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_fine_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_fine_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_fine_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_fine_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_fine_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_fine_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_fine_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_fine_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.tilt_fine_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.use_16bit_pan_tilt": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_default": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_mapped_unwritten_shutter_emits_declared_default",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_map": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/handlers/test_parameterized_channels.py::test_handlers_resolve_fixture_maps",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_map.closed": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/handlers/test_parameterized_channels.py::test_handlers_resolve_fixture_maps",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_map.open": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/handlers/test_parameterized_channels.py::test_handlers_resolve_fixture_maps",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_map.strobe_slow": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/handlers/test_parameterized_channels.py::test_handlers_resolve_fixture_maps",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_map.strobe_medium": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/handlers/test_parameterized_channels.py::test_handlers_resolve_fixture_maps",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.shutter_map.strobe_fast": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/handlers/test_parameterized_channels.py::test_handlers_resolve_fixture_maps",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.color_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.color_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.color_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.color_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.color_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.color_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.color_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.color_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.color_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.color_map": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/handlers/test_parameterized_channels.py::test_unmappable_wheel_preset_falls_back_to_declared_open",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.gobo_channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.gobo_channel.channel": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_written_channels_unchanged",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.dmx_mapping.gobo_channel.config": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.gobo_channel.config.channel_min": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.gobo_channel.config.channel_max": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.gobo_channel.config.channel_default": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.gobo_channel.config.channel_inverted": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.gobo_channel.config.channel_value_map": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.gobo_channel.config.channel_calibration": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.dmx_mapping.gobo_map": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/handlers/test_parameterized_channels.py::test_unmappable_wheel_preset_falls_back_to_declared_open",
        "non-default changes emitted DMX behavior",
    ),
    "fixture.fixtures.config.inversions": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings",
        "non-default changes emitted inversion settings",
    ),
    "fixture.fixtures.config.inversions.pan": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings",
        "non-default changes emitted inversion settings",
    ),
    "fixture.fixtures.config.inversions.tilt": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings",
        "non-default changes emitted inversion settings",
    ),
    "fixture.fixtures.config.inversions.dimmer": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings",
        "non-default changes emitted inversion settings",
    ),
    "fixture.fixtures.config.inversions.shutter": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings",
        "non-default changes emitted inversion settings",
    ),
    "fixture.fixtures.config.inversions.color": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings",
        "non-default changes emitted inversion settings",
    ),
    "fixture.fixtures.config.inversions.gobo": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings",
        "non-default changes emitted inversion settings",
    ),
    "fixture.fixtures.config.pan_tilt_range": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureConfig::test_calibration_fields_change_output_dmx",
        "non-default changes calibrated output DMX",
    ),
    "fixture.fixtures.config.pan_tilt_range.pan_range_deg": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureConfig::test_calibration_fields_change_output_dmx",
        "non-default changes calibrated output DMX",
    ),
    "fixture.fixtures.config.pan_tilt_range.tilt_range_deg": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureConfig::test_calibration_fields_change_output_dmx",
        "non-default changes calibrated output DMX",
    ),
    "fixture.fixtures.config.orientation": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureConfig::test_calibration_fields_change_output_dmx",
        "non-default changes calibrated output DMX",
    ),
    "fixture.fixtures.config.orientation.pan_front_dmx": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureConfig::test_calibration_fields_change_output_dmx",
        "non-default changes calibrated output DMX",
    ),
    "fixture.fixtures.config.orientation.tilt_zero_dmx": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureConfig::test_calibration_fields_change_output_dmx",
        "non-default changes calibrated output DMX",
    ),
    "fixture.fixtures.config.orientation.tilt_up_dmx": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.orientation.tilt_above_horizon_deg": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.orientation.resting_position": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.orientation.resting_position.pan_dmx": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.orientation.resting_position.tilt_dmx": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.orientation.resting_position.description": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.limits": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureConfig::test_calibration_fields_change_output_dmx",
        "non-default changes calibrated output DMX",
    ),
    "fixture.fixtures.config.limits.pan_min": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureConfig::test_calibration_fields_change_output_dmx",
        "non-default changes calibrated output DMX",
    ),
    "fixture.fixtures.config.limits.pan_max": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureConfig::test_calibration_fields_change_output_dmx",
        "non-default changes calibrated output DMX",
    ),
    "fixture.fixtures.config.limits.tilt_min": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureConfig::test_calibration_fields_change_output_dmx",
        "non-default changes calibrated output DMX",
    ),
    "fixture.fixtures.config.limits.tilt_max": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureConfig::test_calibration_fields_change_output_dmx",
        "non-default changes calibrated output DMX",
    ),
    "fixture.fixtures.config.limits.avoid_backward": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.capabilities": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.capabilities.has_color_wheel": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.capabilities.has_gobo_wheel": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.capabilities.has_prism": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.capabilities.has_zoom": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.capabilities.has_iris": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.capabilities.has_frost": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.capabilities.beam_angle_deg": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.movement_speed": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.movement_speed.pan_speed_deg_per_sec": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.movement_speed.tilt_speed_deg_per_sec": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.movement_speed.color_change_ms": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.movement_speed.gobo_change_ms": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.position": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_position_index_changes_rig_order",
        "non-default changes rig fixture order",
    ),
    "fixture.fixtures.config.position.position_index": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_position_index_changes_rig_order",
        "non-default changes rig fixture order",
    ),
    "fixture.fixtures.config.position.pan_offset_deg": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config.position.tilt_offset_deg": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.xlights_model_name": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_get_xlights_mapping",
        "non-default changes public fixture mapping",
    ),
    "fixture.fixtures.dmx_start_address": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.position": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.fixtures.position.position_index": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.fixtures.position.pan_offset_deg": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.position.tilt_offset_deg": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "fixture.fixtures.config_overrides": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_base_config_and_override_change_expanded_fixture_behavior",
        "separately loaded fixture path changes expanded render/rig behavior",
    ),
    "fixture.xlights_group": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_get_xlights_mapping",
        "non-default changes public fixture mapping",
    ),
    "fixture.xlights_semantic_groups": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/config/test_fixtures.py::TestFixtureGroup::test_get_xlights_mapping",
        "non-default changes public fixture mapping",
    ),
    "template.enabled": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.template_id": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.version": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.name": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.category": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.roles": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.repeat": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.repeat.repeatable": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.repeat.mode": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.repeat.cycle_bars": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.repeat.loop_step_ids": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.repeat.remainder_policy": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.defaults": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.step_id": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.target": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.timing": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.timing.base_timing": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
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
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.timing.base_timing.duration_bars": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.timing.phase_offset": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_phase_offset.py::test_phase_offset_fields_change_calculated_schedule",
        "non-default changes calculated fixture schedule",
    ),
    "template.template.steps.timing.phase_offset.mode": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_phase_offset.py::test_phase_offset_fields_change_calculated_schedule",
        "non-default changes calculated fixture schedule",
    ),
    "template.template.steps.timing.phase_offset.group": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.timing.phase_offset.order": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_phase_offset_order_changes_compiled_fixture_schedule",
        "non-default changes compiled per-fixture phase schedule",
    ),
    "template.template.steps.timing.phase_offset.spread_bars": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_phase_offset.py::test_phase_offset_fields_change_calculated_schedule",
        "non-default changes calculated fixture schedule",
    ),
    "template.template.steps.timing.phase_offset.distribution": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.timing.phase_offset.wrap": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/compile/test_phase_offset.py::test_phase_offset_fields_change_calculated_schedule",
        "non-default changes calculated fixture schedule",
    ),
    "template.template.steps.geometry": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.geometry.geometry_type": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.geometry.params": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.geometry.pan_pose_by_role": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.geometry.tilt_pose": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.geometry.aim_zone": ConfigDisposition(
        ConfigDispositionKind.REMOVED,
        None,
        "P4-T5 removed; P4-T6 must delete stale documentation",
    ),
    "template.template.steps.movement": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.movement.movement_type": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.movement.intensity": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.movement.cycles": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.movement.params": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
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
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.dimmer.dimmer_type": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.dimmer.intensity": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.dimmer.min_norm": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.dimmer.max_norm": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.dimmer.cycles": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.dimmer.params": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.color": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.color.preset": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.color.params": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.shutter": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.shutter.pattern": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.shutter.params": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.gobo": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.gobo.pattern": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.steps.gobo.params": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
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
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.metadata.tags": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.metadata.recommended_sections": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.metadata.energy_range": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.template.metadata.description": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.presets": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.presets.preset_id": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.presets.name": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.presets.defaults": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.presets.step_patches": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.presets.step_patches.geometry": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.presets.step_patches.movement": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.presets.step_patches.dimmer": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.presets.step_patches.color": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.presets.step_patches.shutter": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.presets.step_patches.gobo": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
    ),
    "template.presets.step_patches.timing": ConfigDisposition(
        ConfigDispositionKind.EFFECT_TEST,
        "tests/unit/sequencer/moving_heads/templates/test_data_loader.py::test_data_template_registers_and_renders",
        "public behavior discriminator",
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
