from blinkb0t.core.domains.sequencer.moving_heads.resolver.curve_ops import CurveOps
from blinkb0t.core.domains.sequencer.moving_heads.resolver.noop import (
    NoopDimmerGenerator,
    NoopGeometryResolver,
    NoopMovementGenerator,
)
from blinkb0t.core.domains.sequencer.moving_heads.templates.compiler import TemplateCompiler


def build_compiler():
    geometry = NoopGeometryResolver()
    movement = NoopMovementGenerator()
    dimmer = NoopDimmerGenerator()
    curve_ops = CurveOps()  # can also be noop for now

    return TemplateCompiler(
        geometry_resolver=geometry,
        movement_generator=movement,
        dimmer_generator=dimmer,
        curve_ops=curve_ops,
    )
