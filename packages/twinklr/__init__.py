# Twinklr namespace package
# This enables twinklr.core and twinklr.cli to be installed as separate packages
# while sharing the twinklr namespace
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
