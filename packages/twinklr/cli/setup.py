from setuptools import find_packages, setup

# Find all packages - now physical structure matches import path
packages = find_packages(where="../..", include=["blinkb0t.cli", "blinkb0t.cli.*"])

setup(
    packages=packages,
    package_dir={"": "../.."},
)
