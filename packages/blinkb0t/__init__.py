# BlinkB0t namespace package
# This enables blinkb0t.core and blinkb0t.cli to be installed as separate packages
# while sharing the blinkb0t namespace
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
