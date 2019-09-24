import pytest

from Experiments.configloader import ConfigLoader, CONFIGS_DICT, CONFIG_CLASSES

def test_configloader():
    class CONFIG(ConfigLoader): pass
    assert CONFIG.path is ConfigLoader.path

