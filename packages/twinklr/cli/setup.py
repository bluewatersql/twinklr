from setuptools import find_packages, setup
from setuptools.command.build_py import build_py as _build_py

# See packages/twinklr/core/setup.py for the package_dir mapping rationale
# and the setup.py self-sweep exclusion rationale (P0-T5).
subpackages = find_packages(where=".")


class build_py(_build_py):  # noqa: N801 — mirrors setuptools' own command name
    def find_package_modules(self, package, package_dir):
        return [
            (pkg, module, path)
            for pkg, module, path in super().find_package_modules(package, package_dir)
            if module != "setup"
        ]


setup(
    packages=["twinklr.cli", *[f"twinklr.cli.{p}" for p in subpackages]],
    package_dir={"twinklr.cli": "."},
    cmdclass={"build_py": build_py},
)
