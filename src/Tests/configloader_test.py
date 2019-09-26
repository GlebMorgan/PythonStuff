from os.path import join as joinpath, isfile

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
    class CONFIG(ConfigLoader, section='TEST'): pass

    assert CONFIG.path is ConfigLoader.path


@reset
def test_ConfigLoader_used_directly():
    class CONFIG(ConfigLoader, section='WillFail'): pass

    with pytest.raises(RuntimeError) as e:
        CONFIG.load()
    assert msg(e) == "Application config directory path is not specified. " \
                     "ConfigLoader.path or CONFIG.path should be provided"

    with pytest.raises(RuntimeError) as e:
        ConfigLoader.load()
    assert msg(e) == 'ConfigLoader is intended to be used by subclassing'


@reset
def test_path_not_dir():
    class CONFIG(ConfigLoader, section='WillFail'): pass
    CONFIG.path = PATH + r"\testconfig_init.yaml"

    with pytest.raises(ValueError) as e:
        CONFIG.load()
    assert msg(e) == "Application config path is invalid directory: " + PATH + r"\testconfig_init.yaml"


@reset
def test_path_config():
    class CONFIG(ConfigLoader, section='TEST'):
        P1 = 'string'
        P2 = ()
        P3 = 0
    CONFIG.path = PATH
    CONFIG.filename = 'testconfig_simple.yaml'

    initDictKeys = list(dict(CONFIG.__dict__).keys())

    CONFIG.load()

    assert CONFIG.P1 == 'str'
    assert CONFIG.P2 == ('a', 'b', 'c')
    assert CONFIG.P3 is 42

    newDictKeys = list(dict(CONFIG.__dict__).keys())

    assert initDictKeys == newDictKeys

    assert CONFIG.__section__ == 'TEST'
    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1='str', P2=('a', 'b', 'c'), P3=42))


@reset
def test_config_dict_exists():
    class CONFIG(ConfigLoader, section='TEST'):
        P1 = 'string'
        P2 = ()
        P3 = 0
    CONFIG.path = PATH
    CONFIG.filename = 'testconfig_simple.yaml'

    CONFIG.load()

    CONFIG.filename = 'file_should_not_be_accessed.yaml'
    CONFIG.P1 = 'altered'

    # ▼ config dict will exist
    CONFIG.load()

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1='str', P2=('a', 'b', 'c'), P3=42))
    assert CONFIG.P1 == 'str'
    assert CONFIG.P2 == ('a', 'b', 'c')
    assert CONFIG.P3 is 42


@reset
def test_no_file_specified():
    class CONFIG(ConfigLoader, section='TEST'):
        P1 = 'string'
        P2 = ()
        P3 = 0
    CONFIG.path = PATH
    # CONFIG.filename is default

    CONFIG.load()

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1=CONFIG.P1, P2=CONFIG.P2, P3=CONFIG.P3))


@reset
def test_invalid_config_file():
    class CONFIG(ConfigLoader, section='TEST'):
        P1 = 'string'
        P2 = ()
        P3 = 0
    CONFIG.path = PATH
    CONFIG.filename = 'testconfig_invalid.yaml'

    CONFIG.load()

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1='str', P2=('a', 'b', 'c'), P3=80))


@reset
def test_empty_config_file():

    class CONFIG(ConfigLoader, section='TEST'):
        P1 = 'string'
        P2 = ()
        P3 = 0
    CONFIG.path = PATH
    CONFIG.filename = 'testconfig_empty.yaml'

    CONFIG.load()

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1=CONFIG.P1, P2=CONFIG.P2, P3=CONFIG.P3))


@reset
def test_nonexistent_config_file():
    class CONFIG(ConfigLoader, section='TEST'):
        P1 = 'string'
        P2 = ()
        P3 = 0
    CONFIG.path = PATH
    CONFIG.filename = 'nonexistent_config_file.yaml'

    CONFIG.load()

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1=CONFIG.P1, P2=CONFIG.P2, P3=CONFIG.P3))


@reset
def test_load_from_backup():
    class CONFIG(ConfigLoader, section='TEST'):
        P1 = 'string'
        P2 = ()
        P3 = 0
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_backup_only.yaml'

    CONFIG.load()

    assert CONFIG.P3 is 80
    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1='str', P2=('a', 'b', 'c'), P3=80))


@reset
def test_invalid_backup_file():
    class CONFIG(ConfigLoader, section='TEST'):
        P1 = 'string'
        P2 = ()
        P3 = 0
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_invalid_backup.yaml'

    CONFIG.load()

    assert CONFIG.P3 is 0
    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1='string', P2=(), P3=0))


@reset
def test_force_load():
    class CONFIG(ConfigLoader, section='TEST'):
        I1 = 'old'
        I2 = (1, 2)
        I3 = False
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_simple.yaml'

    CONFIG.load()

    ConfigLoader.filename = 'testconfig_triple.yaml'

    CONFIG.__section__ = 'TEST2'
    CONFIG.load(force=True)

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(
            TEST=dict(P1='str', P2=['a', 'b', 'c'], P3=42),
            TEST2=dict(I1='new', I2=(9, 7), I3=True),
            TEST3=None
    )
    assert CONFIG.I1 == 'new'
    assert CONFIG.I2 == (9, 7)
    assert CONFIG.I3 is True


@reset
def test_no_section():
    class CONFIG(ConfigLoader, section='NEW'):
        P1 = 's'
        P2 = ()
        P3 = {'a': 4}
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_simple.yaml'

    CONFIG.load()

    assert CONFIG.P1 == 's'
    assert CONFIG.P2 is ()
    assert CONFIG.P3 == {'a': 4}
    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(
            TEST=dict(P1='str', P2=['a', 'b', 'c'], P3=42),
            NEW=dict(P1='s', P2=(), P3={'a': 4}),
    )


@reset
def test_check_invalid_types():
    members = [1, 2, 3]
    original_members_func = ConfigLoader.members.__func__

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

    ConfigLoader.members = classmethod(original_members_func)


@reset
def test_wrong_config_file():
    class CONFIG(ConfigLoader, section='TEST'):
        W1 = 's'
        W2 = ()
        W3 = {'a': 4}
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_simple.yaml'

    CONFIG.load()

    assert CONFIG.W1 == 's'
    assert CONFIG.W2 is ()
    assert CONFIG.W3 == {'a': 4}
    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == dict(TEST=dict())


@reset
def test_attr_types():
    class CONFIG(ConfigLoader, section='TYPES'):
        SIMPLE = 1
        OK = 'ok'
        DICT_INT = {1: 1, 2: 'old'}
        DICT_STR = {'1': 1, '2': 'old'}
        NONE_CLASS_FILE = None
        NONE_FILE = 3
        NONE_CLASS = None
        CAST_TYPE = 1.1
        INCOMP_TYPE = 1
        NOT_FOUND_IN_FILE = 'n'
        lowercase = 'l'
        REF = SIMPLE
        BRACES = 's'
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_types.yaml'

    file_contents = '\n'.join((
            'TYPES:',
            '  SIMPLE: 1',
            '  OK: ok',
            '  DICT_INT: {1: 1, 2: 2, 3: 3}',
            '  DICT_STR: {"1": 1, "2": 2, "3": 3}',
            '  NONE_CLASS_FILE: null',
            '  NONE_FILE: null',
            '  NONE_CLASS: 42',
            '  CAST_TYPE: 1',
            '  INCOMP_TYPE: COM1',
            '  lowercase: ignored',
            '  REF: 1',
            '  EXTRA: 0',
            '  BRACES: "str"',
            '',
    ))

    configFilePath = joinpath(ConfigLoader.path, ConfigLoader.filename)
    with open(configFilePath, 'w') as file:
        file.write(file_contents)
        file.flush()

    CONFIG.load()

    assert CONFIG.__section__ == 'TYPES'
    assert CONFIG.SIMPLE is 1
    assert CONFIG.OK == 'ok'
    assert CONFIG.DICT_INT == {1: 1, 2: 2, 3: 3}
    assert CONFIG.DICT_STR == {'1': 1, '2': 2, '3': 3}
    assert CONFIG.NONE_CLASS_FILE is None
    assert CONFIG.NONE_FILE is None
    assert CONFIG.NONE_CLASS is 42
    assert type(CONFIG.CAST_TYPE) is float
    assert CONFIG.CAST_TYPE == 1.0
    assert CONFIG.INCOMP_TYPE is 1
    assert CONFIG.NOT_FOUND_IN_FILE == 'n'
    assert CONFIG.lowercase == 'l'
    assert CONFIG.REF is 1
    assert CONFIG.BRACES == 'str'

    assert configloader.CONFIG_CLASSES == {CONFIG}
    assert configloader.CONFIGS_DICT == {
        'TYPES': {
            'SIMPLE': 1,
            'OK': 'ok',
            'DICT_INT': {1: 1, 2: 2, 3: 3},
            'DICT_STR': {'1': 1, '2': 2, '3': 3},
            'NONE_CLASS_FILE': None,
            'NONE_FILE': None,
            'NONE_CLASS': 42,
            'CAST_TYPE': 1.0,
            'REF': 1,
            'BRACES': 'str',
        }
    }


@reset
def test_save_force_is_false():
    class CONFIG(ConfigLoader, section='TEST'):
        P1 = 'old'
        P2 = (1,)
        P3 = 33
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_simple.yaml'

    assert CONFIG.save(force=False) is False

    assert CONFIG.P1 == 'old'
    assert CONFIG.P2 == (1,)
    assert CONFIG.P3 == 33
    assert configloader.CONFIGS_DICT == {}

    CONFIG.load()

    assert CONFIG.__section__ == 'TEST'

    assert CONFIG.save(force=False) is False

    assert CONFIG.P1 == 'str'
    assert CONFIG.P2 == ('a', 'b', 'c')
    assert CONFIG.P3 == 42
    assert configloader.CONFIGS_DICT == dict(TEST=dict(P1='str', P2=('a', 'b', 'c'), P3=42))


@reset
def test_ignore_updates():
    class CONFIG(ConfigLoader, section='UPDATE'):
        P1 = 's'
        P2 = ()
        P3 = {'a': 4}

    configloader.CONFIGS_DICT = dict(UPDATE=dict(P1='s', P2=(), P3={'a': 4}))
    assert CONFIG.updated is False

    CONFIG.P4 = ['new']
    assert CONFIG.updated is True

    del CONFIG.P4
    assert CONFIG.updated is False

    CONFIG.P3['a'] = 4
    assert CONFIG.updated is False

    CONFIG.P3['a'] = 4.0
    assert CONFIG.updated is False

    CONFIG.P3['a'] = 5
    assert CONFIG.updated is True

    CONFIG.P3['a'] = 4
    assert CONFIG.updated is False

    CONFIG.P2 = 'azaza'
    assert CONFIG.updated is True

    CONFIG.ignore()
    assert CONFIG.updated is None

    assert configloader.CONFIGS_DICT == dict(UPDATE=dict(P1='s', P2=(), P3={'a': 4}))



@reset
def test_save_simple():
    class CONFIG(ConfigLoader, section='SAVE'):
        P1 = 's'
        P2 = ()
        P3 = {'a': 4}
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_save_simple.yaml'

    file_contents = '\n'.join([
        "SAVE:",
        "  P1: ''",
        "  P2: [1]",
        "  P3: {a: 4}",
        "",
    ])

    configFilePath = joinpath(ConfigLoader.path, ConfigLoader.filename)
    with open(configFilePath, 'w') as file:
        file.write(file_contents)
        file.flush()

    CONFIG.load()

    assert CONFIG.P1 == ''
    assert CONFIG.P2 == (1,)
    assert CONFIG.P3 == {'a': 4}
    assert CONFIG.__section__ == 'SAVE'
    assert configloader.CONFIGS_DICT == dict(SAVE=dict(P1='', P2=(1,), P3={'a': 4}))

    CONFIG.P3['a'] = 3
    CONFIG.P1 = None

    assert CONFIG.updated is True
    assert configloader.CONFIGS_DICT == dict(SAVE=dict(P1='', P2=(1,), P3={'a': 4}))

    CONFIG.save()

    assert isfile(configFilePath) is True
    assert isfile(configFilePath+'.bak') is True
    assert configloader.CONFIGS_DICT == dict(SAVE=dict(P1=None, P2=(1,), P3={'a': 3}))

    storedConfig = YAML(typ='safe').load(open(configFilePath))

    assert storedConfig == dict(SAVE=dict(P1=None, P2=[1], P3={'a': 3}))







# ——————————————————————————————————————————————— STOPPED HERE ——————————————————————————————————————————————————————— #


@reset
def _test_ignore_updates_unit():  # TODO: ignoreUpdates concerns saving config
    class CONFIG(ConfigLoader, section='TEST'):
        P1 = 'string'
        P2 = ()
        P3 = 0
    ConfigLoader.path = PATH
    ConfigLoader.filename = 'testconfig_triple.yaml'

    class IGNORED(ConfigLoader, 'TEST2'):
        I1 = 'ign'
        I2 = [1, 2, 3]
        I3 = False
    IGNORED.ignore()

    CONFIG.load()
    IGNORED.load()

    assert configloader.CONFIG_CLASSES == {CONFIG, IGNORED}
    assert configloader.CONFIGS_DICT == dict(
            TEST = dict(P1='str', P2=['a', 'b', 'c'], P3=42),
            TEST2 = dict(I1='new', I2=[9, 7], I3=True),
            TEST3 = None
    )
    assert IGNORED.I1 == 'ign'
    assert IGNORED.I2 == [1, 2, 3]
    assert IGNORED.I3 is False
