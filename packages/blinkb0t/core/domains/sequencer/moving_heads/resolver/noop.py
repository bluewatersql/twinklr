from .interfaces import DimmerGenerator, GeometryResolver, MovementGenerator


class NoopGeometryResolver(GeometryResolver):
    def resolve_base_pose(self, rig, fixtures, geometry_spec):
        # center everything
        return dict.fromkeys(fixtures, (128, 128))


class NoopMovementGenerator(MovementGenerator):
    def generate(self, movement_spec, duration_ms):
        return {"pan": None, "tilt": None}


class NoopDimmerGenerator(DimmerGenerator):
    def generate(self, dimmer_spec, duration_ms):
        return None
