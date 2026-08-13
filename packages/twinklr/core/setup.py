from setuptools import find_packages, setup
from setuptools.command.build_py import build_py as _build_py

# Physical layout: the package's Python source lives directly in this
# project's root directory, but the import name is the dotted "twinklr.core"
# namespace package. Mapping "twinklr.core" -> "." lets setuptools resolve
# every subpackage as "twinklr.core.<subpackage>" -> "./<subpackage>" without
# ever reaching outside the project root - unlike the previous
# where="../.." + package_dir={"": "../.."} shim, this stays inside the
# isolated build sandbox, so real (non-editable) builds work too (see P0-T5).
#
# Mapping the root package's directory to "." also makes setuptools treat
# every loose *.py file here as one of its modules, which would otherwise
# sweep this very file in as "twinklr.core.setup". setuptools' built-in
# exclusion for its own script (distutils.command.build_py, comparing against
# self.distribution.script_name) does not reliably trigger under `uv build`'s
# PEP 517 flow, so exclude it explicitly.
subpackages = find_packages(where=".")


class build_py(_build_py):
    def find_package_modules(self, package, package_dir):
        return [
            (pkg, module, path)
            for pkg, module, path in super().find_package_modules(package, package_dir)
            if module != "setup"
        ]


setup(
    packages=["twinklr.core", *[f"twinklr.core.{p}" for p in subpackages]],
    package_dir={"twinklr.core": "."},
    cmdclass={"build_py": build_py},
)
