"""Template pipeline orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from blinkb0t.core.config.fixtures import FixtureGroup, FixtureInstance
from blinkb0t.core.config.models import JobConfig
from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement
from blinkb0t.core.domains.sequencing.infrastructure.xsq.parser import XSQParser
from blinkb0t.core.domains.sequencing.models.poses import PoseID
from blinkb0t.core.domains.sequencing.moving_heads.templates.factory import TemplateProcessorFactory
from blinkb0t.core.domains.sequencing.moving_heads.templates.loader import TemplateLoader


class TemplatePipeline:
    """High-level template rendering pipeline.

    Creates factory, loads templates, orchestrates rendering.
    """

    def __init__(
        self,
        template_dir: str | Path,
        song_features: dict[str, Any],
        job_config: JobConfig,
        fixtures: FixtureGroup,
        xsq_path: str | Path,
    ):
        """Initialize pipeline.

        Args:
            template_dir: Template directory
            song_features: Song features
            job_config: Job configuration
            fixtures: Fixture group
            xsq_path: XSQ file path
        """
        # Load XSQ
        parser = XSQParser()
        self.xsq = parser.parse(xsq_path)

        # Create factory (creates all infrastructure ONCE)
        self.factory = TemplateProcessorFactory(
            song_features=song_features,
            job_config=job_config,
            fixtures=fixtures,
            xsq=self.xsq,
        )

        # Create processor (via factory)
        self.processor = self.factory.create_processor()

        # Create loader
        self.loader = TemplateLoader(template_dir=template_dir)

    def render_template(
        self,
        template_id: str,
        fixture: FixtureInstance,
        base_pose: PoseID,
        section_start_ms: float,
        section_end_ms: float,
        params: dict[str, Any] | None = None,
    ) -> list[EffectPlacement]:
        """Render template for fixture."""
        # Load template
        template = self.loader.load_template(template_id, params or {})

        # Process template (reuses processor, doesn't recreate)
        effects: list[EffectPlacement] = self.processor.process_template(
            template=template,
            fixture=fixture,
            base_pose=base_pose,
            section_start_ms=section_start_ms,
            section_end_ms=section_end_ms,
        )
        return effects
