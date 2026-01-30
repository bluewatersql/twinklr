from setuptools import find_packages, setup

# Find all packages - now physical structure matches import path
packages = find_packages(where="../..", include=["blinkb0t.core", "blinkb0t.core.*"])

setup(
    packages=packages,
    package_dir={"": "../.."},
)
