import pytest

from Experiments import configloader
from Experiments.configloader import ConfigLoader
from Utils import formatList
from ruamel.yaml import YAML

PATH = r"C:\Users\Peleng-HP\AppData\Roaming\.PelengTools\Tests\ConfigLoader"

savedState = {
    'CONFIG_FILE_BASE_PATH': ConfigLoader.CONFIG_FILE_BASE_PATH,
    'AUTO_CREATE_CONFIG_FILE': ConfigLoader.AUTO_CREATE_CONFIG_FILE,
    'filename': ConfigLoader.filename,
    'path': ConfigLoader.path,
    'loader': ConfigLoader.loader,
    '_loaded_': ConfigLoader._loaded_,
    '_ignoreUpdates_': ConfigLoader._ignoreUpdates_,
    '_section_': ConfigLoader._section_,
}

def msg(e): return e.value.args[0]

def reset(f):
    def reset_configloader_wrapper(*args, **kwargs):
        configloader.CONFIG_CLASSES = set()
        configloader.CONFIGS_DICT = {}
        for name, value in savedState.items():
            setattr(ConfigLoader, name, value)
        ConfigLoader.loader.default_flow_style = False
        f(*args, **kwargs)
    return reset_configloader_wrapper


# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #


@reset
def test_ConfigLoader_vars():
    class CONFIG(ConfigLoader): pass

    assert CONFIG.path is ConfigLoader.path


@reset
def test_ConfigLoader_used_directly():
    class CONFIG(ConfigLoader): pass

    with pytest.raises(RuntimeError) as e:
        CONFIG.load('WillFail')
    assert msg(e) == "Application config directory path is not specified. " \
                     "ConfigLoader.path or CONFIG.path should be provided"

    with pytest.raises(RuntimeError) as e:
        ConfigLoader.load('WillFail')
    assert msg(e) == 'ConfigLoader is intended to be used by subclassing'


@reset
def test_path_not_dir():
    class CONFIG(ConfigLoader): pass
    CONFIG.path = PATH + r"\testconfig_init.yaml"

    with pytest.raises(ValueError) as e:
        CONFIG.load('willFail')
    assert msg(e) == "Application config path is invalid directory: " + PATH + r"\testconfig_init.yaml"


@reset
def test_path_config():
    class CONFIG(ConfigLoader):
        P1 = 'string'
        P2 = ()
        P3 = 0
    CONFIG.path = PATH
    CONFIG.filename = 'testconfig_simple.yaml'

    initDictKeys = list(dict(CONFIG.__dict__).keys())
    initDictKeys.remove('P1')
    initDictKeys.remove('P2')
    initDictKeys.remove('P3')

    CONFIG.load('TEST')

    assert CONFIG.P1 == 'str'
    assert CONFIG.P2 == ('a', 'b', 'c')
    assert CONFIG.P3 == 42

    newDictKeys = list(dict(CONFIG.__dict__).keys())
    newDictKeys.remove('P1')
    newDictKeys.remove('P2')
    newDictKeys.remove('P3')

    assert initDictKeys + ['_section_', '_loaded_'] == newDictKeys

    assert CONFIG._section_ == 'TEST'
    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1='str', P2=['a', 'b', 'c'], P3=42))


@reset
def test_config_dict_exists():
    class CONFIG(ConfigLoader):
        P1 = 'string'
        P2 = ()
        P3 = 0
    CONFIG.path = PATH
    CONFIG.filename = 'testconfig_simple.yaml'

    CONFIG.load('TEST')

    CONFIG.filename = 'file_should_not_be_accessed.yaml'
    CONFIG.P1 = 'altered'

    # ▼ config dict will exist
    CONFIG.load('TEST')

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1='str', P2=['a', 'b', 'c'], P3=42))
    assert CONFIG.P1 == 'str'
    assert CONFIG.P2 == ('a', 'b', 'c')
    assert CONFIG.P3 == 42


@reset
def test_no_file_specified():
    class CONFIG(ConfigLoader):
        P1 = 'string'
        P2 = ()
        P3 = 0
    CONFIG.path = PATH
    # CONFIG.filename is default

    CONFIG.load('TEST')

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1=CONFIG.P1, P2=CONFIG.P2, P3=CONFIG.P3))


@reset
def test_invalid_config_file():
    class CONFIG(ConfigLoader):
        P1 = 'string'
        P2 = ()
        P3 = 0
    CONFIG.path = PATH
    CONFIG.filename = 'testconfig_invalid.yaml'

    CONFIG.load('TEST')

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1=CONFIG.P1, P2=CONFIG.P2, P3=CONFIG.P3))


@reset
def test_empty_config_file():

    class CONFIG(ConfigLoader):
        P1 = 'string'
        P2 = ()
        P3 = 0
    CONFIG.path = PATH
    CONFIG.filename = 'testconfig_empty.yaml'

    CONFIG.load('TEST')

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1=CONFIG.P1, P2=CONFIG.P2, P3=CONFIG.P3))


@reset
def test_nonexistent_config_file():
    class CONFIG(ConfigLoader):
        P1 = 'string'
        P2 = ()
        P3 = 0
    CONFIG.path = PATH
    CONFIG.filename = 'nonexistent_config_file.yaml'

    CONFIG.load('TEST')

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1=CONFIG.P1, P2=CONFIG.P2, P3=CONFIG.P3))


@reset
def test_revert_from_backup():
    class CONFIG(ConfigLoader):
        P1 = 'string'
        P2 = ()
        P3 = 0
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_backup.yaml'

    CONFIG.load('TEST')

    assert CONFIG.P3 == 80
    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1='str', P2=['a', 'b', 'c'], P3=80))


@reset
def test_invalid_backup_file():
    class CONFIG(ConfigLoader):
        P1 = 'string'
        P2 = ()
        P3 = 0
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_invalid.yaml'

    CONFIG.load('TEST')

    assert CONFIG.P3 == 0
    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1='string', P2=(), P3=0))


@reset
def test_force_load():
    class CONFIG(ConfigLoader):
        P1 = 'string'
        P2 = ()
        P3 = 0
        I3 = False
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_simple.yaml'

    CONFIG.load("TEST")

    ConfigLoader.filename = 'testconfig_triple.yaml'

    CONFIG.load("TEST2", force=True)

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(
            TEST=dict(P1='str', P2=['a', 'b', 'c'], P3=42),
            TEST2=dict(I3=True),
            TEST3=None
    )
    assert CONFIG.P3 == 42
    assert CONFIG.I3 is True


@reset
def test_no_section():
    class CONFIG(ConfigLoader):
        P1 = 's'
        P2 = ()
        P3 = {'a': 4}
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_simple.yaml'

    CONFIG.load('NEW')

    assert CONFIG.P1 == 's'
    assert CONFIG.P2 == ()
    assert CONFIG.P3 == {'a': 4}
    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1='s', P2=(), P3={'a': 4}))


@reset
def test_check_invalid_types():
    members = [1, 2, 3]
    ConfigLoader.members = lambda: ((f'par{i}', item) for i, item in enumerate(members))
    c = ConfigLoader._checkInvalidTypes_

    print()
    assert c() == set()

    members = [0, [7, 8, 9], ('a', 'b'), None]
    members.append([members[1], members[2], members[2]])
    members.append(members)
    print()
    assert c() == set()

    members = [0, [7, ..., 9], ('a', pytest), None, type("Class", (), {})()]
    members.extend(([members[1], members[2], members[2]], type, print, {'x':42, 'y':(4,5), 'z':(b'FF',)}))
    members[8]['p'] = members[8]
    members.append(members)

    print()
    assert c() == {'par1[1]', 'par2[1]', 'par4', 'par6', 'par7'}

    print(formatList(members, indent=4))



# ——————————————————————————————————————————————— STOPPED HERE ——————————————————————————————————————————————————————— #


@reset
def _test_ignore_updates():  # TODO: ignoreUpdates concerns saving config
    class CONFIG(ConfigLoader):
        P1 = 'string'
        P2 = ()
        P3 = 0
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_triple.yaml'

    class IGNORED(ConfigLoader):
        I1 = 'ign'
        I2 = [1, 2, 3]
        I3 = False
    IGNORED.ignore()

    CONFIG.load('TEST')
    IGNORED.load('TEST2')

    assert configloader.CONFIG_CLASSES == {CONFIG, IGNORED}
    assert configloader.CONFIGS_DICT == dict(
            TEST = dict(P1='str', P2=['a', 'b', 'c'], P3=42),
            TEST2 = dict(I1='new', I2=[9, 7], I3=True),
            TEST3 = None
    )
    assert IGNORED.I1 == 'ign'
    assert IGNORED.I2 == [1, 2, 3]
    assert IGNORED.I3 is False
