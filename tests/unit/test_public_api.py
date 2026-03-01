"""Tests for public API surface — CQ-10 __all__ exports."""

import importlib

import pytest

PACKAGES_WITH_ALL = [
    "twinklr.core.feature_store",
    "twinklr.core.feature_engineering",
    "twinklr.core.audio",
    "twinklr.core.agents.providers",
    "twinklr.core.config",
    "twinklr.core.profiling",
]


class TestAllExports:
    @pytest.mark.parametrize("pkg", PACKAGES_WITH_ALL)
    def test_all_defined(self, pkg):
        mod = importlib.import_module(pkg)
        assert hasattr(mod, "__all__"), f"{pkg} missing __all__"
        assert len(mod.__all__) > 0

    @pytest.mark.parametrize("pkg", PACKAGES_WITH_ALL)
    def test_all_members_importable(self, pkg):
        mod = importlib.import_module(pkg)
        for name in mod.__all__:
            assert hasattr(mod, name), f"{pkg}.{name} not found"
