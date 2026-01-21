class GeometryResolver:
    def resolve_base_pose(self, rig, fixtures, geometry_spec):
        raise NotImplementedError


class MovementGenerator:
    def generate(self, movement_spec, duration_ms):
        raise NotImplementedError


class DimmerGenerator:
    def generate(self, dimmer_spec, duration_ms):
        raise NotImplementedError
