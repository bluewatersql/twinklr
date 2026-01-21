"""xLights format adapters for curve specifications."""

from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec


class NativeCurveFormatter:
    """Format native curve specifications for xLights."""

    @staticmethod
    def format_for_xlights(spec: ValueCurveSpec, channel: int) -> str:
        """Generate xLights value curve parameter string.

        Args:
            spec: Native curve specification
            channel: DMX channel number (1-512)

        Returns:
            xLights value curve parameter string

        Examples:
            >>> from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
            >>> from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
            >>> spec = ValueCurveSpec(type=NativeCurveType.RAMP, p2=150.0)
            >>> NativeCurveFormatter.format_for_xlights(spec, 11)
            'Active=TRUE|Id=ID_VALUECURVE_DMX11|Type=Ramp|Min=0|Max=255|P2=150.00|RV=FALSE|'
        """
        # Convert curve type to title case for xLights (case-sensitive)
        # Internal: "ramp", "sine", "abs sine" -> xLights: "Ramp", "Sine", "Abs Sine"
        xlights_type = spec.type.value.title()

        parts = [
            "Active=TRUE",
            f"Id=ID_VALUECURVE_DMX{channel}",
            f"Type={xlights_type}",
            "Min=0",
            "Max=255",
        ]

        # Add non-zero parameters
        if spec.p1 != 0.0:
            parts.append(f"P1={spec.p1:.2f}")
        if spec.p2 != 0.0:
            parts.append(f"P2={spec.p2:.2f}")
        if spec.p3 != 0.0:
            parts.append(f"P3={spec.p3:.2f}")
        if spec.p4 != 0.0:
            parts.append(f"P4={spec.p4:.2f}")

        # Reverse flag (must be TRUE or FALSE in caps)
        parts.append(f"RV={'TRUE' if spec.reverse else 'FALSE'}")

        # xLights format requires trailing pipe
        return "|".join(parts) + "|"
