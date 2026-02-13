"""Helper for building xLights EffectDB settings strings.

Provides a fluent builder API to construct the comma-separated
KEY=VALUE strings stored in xLights EffectDB entries.

Key prefixes:
- E_ : Effect parameters (sliders, checkboxes, choices, text)
- B_ : Buffer/rendering parameters (buffer style, transform)
- T_ : Transition/timing parameters (layer method, in/out)
"""

from __future__ import annotations

from typing import Any


class SettingsStringBuilder:
    """Fluent builder for xLights EffectDB settings strings.

    Example:
        >>> b = SettingsStringBuilder()
        >>> b.add("E_SLIDER_Speed", 50)
        >>> b.add("E_CHECKBOX_Mirror", 0)
        >>> b.add_buffer_style("Per Model Default")
        >>> s = b.build()
        >>> s
        'E_SLIDER_Speed=50,E_CHECKBOX_Mirror=0,B_CHOICE_BufferStyle=Per Model Default'
    """

    def __init__(self) -> None:
        self._parts: list[str] = []

    def add(self, key: str, value: Any) -> SettingsStringBuilder:
        """Add a key=value pair.

        Args:
            key: Parameter key (e.g., 'E_SLIDER_Speed').
            value: Parameter value.

        Returns:
            Self for chaining.
        """
        self._parts.append(f"{key}={value}")
        return self

    def add_if(
        self, key: str, value: Any, condition: bool
    ) -> SettingsStringBuilder:
        """Add a key=value pair only if condition is True.

        Args:
            key: Parameter key.
            value: Parameter value.
            condition: Whether to include this parameter.

        Returns:
            Self for chaining.
        """
        if condition:
            self._parts.append(f"{key}={value}")
        return self

    def add_buffer_style(self, style: str) -> SettingsStringBuilder:
        """Add the buffer style parameter.

        Args:
            style: xLights buffer style name.

        Returns:
            Self for chaining.
        """
        return self.add("B_CHOICE_BufferStyle", style)

    def add_buffer_transform(self, transform: str) -> SettingsStringBuilder:
        """Add the buffer transform parameter.

        Args:
            transform: xLights buffer transform name.

        Returns:
            Self for chaining.
        """
        return self.add("B_CHOICE_BufferTransform", transform)

    def add_layer_method(self, method: str) -> SettingsStringBuilder:
        """Add the layer blending method.

        Args:
            method: xLights layer method name (e.g., 'Normal', 'Max').

        Returns:
            Self for chaining.
        """
        return self.add("T_CHOICE_LayerMethod", method)

    def add_fade_in(
        self,
        seconds: float,
        transition_type: str = "Fade",
        adjust: int | None = None,
        reverse: bool = False,
    ) -> SettingsStringBuilder:
        """Add fade-in transition keys.

        Args:
            seconds: Fade-in duration in seconds (e.g., 0.50).
            transition_type: Transition type name (default 'Fade').
            adjust: Transition adjustment (0-100), None to omit.
            reverse: Whether to reverse direction.

        Returns:
            Self for chaining.
        """
        self.add("T_TEXTCTRL_Fadein", f"{seconds:.2f}")
        self.add("T_CHOICE_In_Transition_Type", transition_type)
        if adjust is not None:
            self.add("T_SLIDER_In_Transition_Adjust", adjust)
        if reverse:
            self.add("T_CHECKBOX_In_Transition_Reverse", 1)
        return self

    def add_fade_out(
        self,
        seconds: float,
        transition_type: str = "Fade",
        adjust: int | None = None,
        reverse: bool = False,
    ) -> SettingsStringBuilder:
        """Add fade-out transition keys.

        Args:
            seconds: Fade-out duration in seconds (e.g., 0.50).
            transition_type: Transition type name (default 'Fade').
            adjust: Transition adjustment (0-100), None to omit.
            reverse: Whether to reverse direction.

        Returns:
            Self for chaining.
        """
        self.add("T_TEXTCTRL_Fadeout", f"{seconds:.2f}")
        self.add("T_CHOICE_Out_Transition_Type", transition_type)
        if adjust is not None:
            self.add("T_SLIDER_Out_Transition_Adjust", adjust)
        if reverse:
            self.add("T_CHECKBOX_Out_Transition_Reverse", 1)
        return self

    def build(self) -> str:
        """Build the final comma-separated settings string.

        Returns:
            Comma-separated KEY=VALUE string.
        """
        return ",".join(self._parts)


__all__ = [
    "SettingsStringBuilder",
]
