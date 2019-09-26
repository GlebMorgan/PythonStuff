from __future__ import annotations

from copy import deepcopy
from itertools import compress
from os import linesep, makedirs
from os.path import join as joinpath, dirname, abspath, basename, isdir, expandvars as envar, isfile
from shutil import copyfile
from typing import Dict, Type, Set, Optional, List

from Utils import Logger, formatDict, formatList, isiterable, classproperty
from ruamel.yaml import YAML, YAMLError


# CONSIDER: Constrain assigning common settings to ConfigLoader attrs (like .filePath and .loader), not child class


log = Logger("Config")


CONFIG_CLASSES: Set[Type[ConfigLoader]] = set()
CONFIGS_DICT: Dict[str, dict] = {}


class ConfigLoader:
    """ When subclassed, stores all UPPERCASE (of which isupper() returns True)
        class attrs as dict of categories with config parameters
        and saves/loads them to/from .yaml file
        Only specified object types are allowed inside config
    """

    # ▼ Immutable types must have .copy() attr
    SUPPORTED_TYPES = (int, float, str, bytes, bool, tuple, list, dict, set, type(None))

    # ▼ Config is stored in APPDATA.PelengTools by default
    #   Should not be used as complete config file path; application subdirectory needs to be appended
    CONFIG_FILE_BASE_PATH = joinpath(envar('%APPDATA%'), '.PelengTools')

    # ▼ Config file will be created automatically in case no one was found on specified path
    AUTO_CREATE_CONFIG_FILE = True

    filename: str = 'config.yaml'
    path: str = None
    loader = YAML(typ='safe')
    loader.default_flow_style = False

    # Initialized in successors:
    _loaded_: bool  # FIXME: deprecate this
    _ignoreUpdates_: bool
    __section__: str

    def __init_subclass__(cls, *, section):
        cls._loaded_ = False
        cls._ignoreUpdates_ = False
        cls.__section__: str = section
        CONFIG_CLASSES.add(cls)

    @classmethod
    def load(cls, app: str = None, *, force=False):
        """ Update class with config params retrieved from config file, if possible """

        if cls is ConfigLoader:
            raise NotImplementedError(f"{cls.__name__} is intended to be used by subclassing")

        if app is not None:
            cls.path = joinpath(cls.CONFIG_FILE_BASE_PATH, app)
        elif cls.path is None:
            raise RuntimeError("Application config directory path is not specified. "
                               f"{cls.__mro__[-2].__name__}.path or {cls.__name__}.path should be provided")

        if not isdir(cls.path):
            raise ValueError(f"Application config path is invalid directory: {cls.path}")

        invalidAttrs = cls._checkInvalidTypes_()
        if invalidAttrs:
            displayList = formatList((f'{name}: {type(getattr(cls, name))}' for name in invalidAttrs), indent=4)
            raise TypeError(f"{cls.__name__} contains invalid attr types:{linesep}{displayList}")

        log.info(f"Fetching config for '{cls.__section__}' from {cls.filename}...")

        if force or not CONFIGS_DICT:
            # Empty CONFIGS_DICT => .load() is called for the first time => load config from file
            path = joinpath(cls.path, cls.filename)
            log.debug(f"Loading config from {path}...")
            if not cls._loadFromFile_(path):
                log.info(f"Loading backup config...")
                if not cls._loadFromFile_(path + '.bak', backup=True):
                    cls._addCurrentSection_()
                    return cls._useDefaultConfig_()

        try: sectionDict = CONFIGS_DICT[cls.__section__]
        except KeyError:
            log.warning(f"Cannot find section '{cls.__section__}' in config file. Creating new one with defaults.")
            cls._addCurrentSection_()
            return cls._useDefaultConfig_()

        loadedParams = []
        for parName, currPar in cls.members():
            try: newPar = sectionDict[parName]
            except KeyError:
                log.error(f"Parameter '{parName}': not found in {cls.filename}")
                continue
            else:
                if currPar is not None and newPar is not None:
                    try: newPar = type(currPar)(newPar)  # cast to cls.attr type
                    except (ValueError, TypeError) as e:
                        log.error(f"Parameter '{parName}': cannot convert '{newPar}' "
                                  f"to type '{type(currPar).__name__}' — {e}")
                        continue
                if hasattr(newPar, 'copy'): setattr(cls, parName, deepcopy(newPar))
                else: setattr(cls, parName, newPar)
                loadedParams.append(parName)
                sectionDict[parName] = newPar
        extraParams = sectionDict.keys() - loadedParams
        if len(extraParams) > 0:
            log.warning(f"Unexpected parameters found in configuration file: {', '.join(extraParams)}")
            for par in extraParams: del sectionDict[par]

        if len(loadedParams) > 0: log.info(f"Config '{cls.__section__}' loaded, {len(loadedParams)} items")
        else: log.warning(f"Nothing was loaded for '{cls.__section__}' "
                          f"from {cls.filename} (wrong section name specified?)")

        cls._loaded_ = True
        log.debug(f"{cls.__name__}: {formatDict(dict(cls.members()))}")

    @classproperty
    def updated(cls):  # TODO: rename this and correct docstring
        """ Update internal config storage with actual class attrs (if ._ignoreUpdates_ is False)
            Returns True if actual config has been changed, False otherwise, None if configured to ignore updates
            May be used to save current class config only: CFG.save(CFG.update())
            CONSIDER: Type casting and comparisons are shallow, so (True, 2, 3.0) == (1,2,3) is accepted
        """

        if cls._ignoreUpdates_ is True:
            log.info(f"Section '{cls.__section__}': updates ignored by request")
            return None
        return CONFIGS_DICT[cls.__section__] != dict(cls.members())

    @classmethod
    def save(cls, force: bool = None) -> bool:
        """ Save all config sections to config file if any have changed or if forced
            NOTE: Call this method before app exit
            Return boolean denoting whether smth was actually saved to file
        """

        # ▼ Skip save on False. Used when necessity of save is acquired dynamically (ex: CFG.save(CFG.update()))
        if force is False: return False

        sections = tuple(configCls.__section__ for configCls in CONFIG_CLASSES)

        path = joinpath(cls.path, cls.filename)
        if isfile(path):
            if cls.AUTO_CREATE_CONFIG_FILE is False:
                log.debug("{cls.__name__} is configured not to create initial config file")
            else:
                try: makedirs(cls.path, exist_ok=True)
                except OSError as e:
                    log.error(f"Failed to create config directory tree:{linesep}{e}")
                    return False
                else: log.debug(f"Created directory {cls.path}")

        if not force:
            updatedSections = tuple(cfgCls.__section__ for cfgCls in CONFIG_CLASSES if cfgCls.updated is True)
            if updatedSections == ():
                log.info("No config changes in all sections – save skipped")
                return False
            else: log.info(f"Updated sections: {', '.join(updatedSections)}")
        else: log.debug(f"Force saving config for sections {', '.join(sections)}")

        newConfigsDict = {cfgCls.__section__: dict(cfgCls.members()) for cfgCls in CONFIG_CLASSES}

        log.debug(f"Creating backup config file {cls.filename + '.bak'}")
        cls.createBackup(path)

        log.debug(f"Saving config to file {cls.filename}")
        try:
            with open(path, 'w') as configFile:
                cls.loader.dump(newConfigsDict, configFile)
        except (OSError, YAMLError) as e:
            log.error(f"Failed to save configuration file:{linesep}{e}")
        else:
            global CONFIGS_DICT
            CONFIGS_DICT = newConfigsDict
            log.info(f"Config saved to {cls.filename}")

    @classmethod
    def createBackup(cls, path):
        try: copyfile(path, path + '.bak')
        except OSError as e: log.error(f"Failed to create backup config file: {e}")

    @classmethod
    def revert(cls, path):
        """ Restore config file from backup, if such is present """
        log.debug(f"Reverting config from {path + '.bak'}...")
        try: copyfile(path + '.bak', path)
        except OSError as e:
            log.warning(f"Reverting from backup failed: {e}")
            return False
        else:
            log.info("Reverted from backup successfully")
            return True

    @classmethod
    def ignore(cls):
        cls._ignoreUpdates_ = True

    @classmethod
    def params(cls):
        """ Yield all class attr names that are treated as config params """
        yield from (attrName for attrName in vars(cls).keys() if attrName.isupper())

    @classmethod
    def members(cls):
        """ Yield (name, value) pairs from all class config params """
        yield from ((name, value) for name, value in vars(cls).items() if name.isupper())
        # yield from filter(lambda dictItem: dictItem[0].isupper(), vars(cls).items())

    @classmethod
    def _checkInvalidTypes_(cls) -> Set[str]:
        pending = list(cls.members())
        done = []
        invalid = set()
        while True:
            try: name, value = pending.pop(0)
            except IndexError: return invalid
            # print(f'{name} = {value}')
            if not isinstance(value, cls.SUPPORTED_TYPES):
                # print(f'{name}: invalid')
                invalid.add(name)
            elif isiterable(value):
                # print(f'{name}: iterable')
                if isinstance(value, dict): iterator = value.items()
                else: iterator = enumerate(value)
                for i, elem in iterator:
                    if any(elem is verified for verified in done) or elem is value:
                        # print(f'{name}[{i}]: dup')
                        continue
                    pending.append((f'{name}[{i}]', elem))
            done.append(value)
            # print(f'{name}: done')

    @classmethod
    def _useDefaultConfig_(cls):
        # Just return and use class attrs when querying config params
        log.info(f"Using default config for '{cls.__section__}'")

    @classmethod
    def _loadFromFile_(cls, path, backup=False) -> bool:
        """ Load dict of config sections from .yaml file to CONFIGS_DICT module variable,
            return boolean value = failed/succeeded
            If `backup` is True, path is considered to be backup file path
        """
        # ▼ Denotes whether `file` is a backup file
        filetype = 'backup' if backup else 'config'
        try:
            with open(path) as configFile:
                # ▼ expect dict of config dicts in config file
                configDict = cls.loader.load(configFile)
                if configDict is None:
                    log.warning(f"{filetype.capitalize()} file is empty")
                    return False
                if not isinstance(configDict, dict):
                    log.error(f"Config loader {cls.loader.__class__.__name__} "
                              f"returned invalid result type: {configDict.__class__.__name__}")
                    return False
                else:
                    CONFIGS_DICT.update(configDict)
                    log.debug(f"Config loaded: {formatDict(configDict)}")
                    return True  # succeeded loading from file
        except YAMLError as e:
            log.error(f"Failed to parse {filetype} file:{linesep}{e}")
            return False
        except FileNotFoundError:
            log.warning(f"{filetype.capitalize()} file {basename(path)} not found")
            return False

    @classmethod
    def _addCurrentSection_(cls):
        CONFIGS_DICT[cls.__section__] = dict(cls.members())
        log.debug(f"New section added: {cls.__section__} {formatDict(CONFIGS_DICT[cls.__section__])}")

    @classmethod
    def _fileUpdateRequired_(cls): return any(not configClass._loaded_ for configClass in CONFIG_CLASSES)

    @classmethod
    def _fileUpdateSections_(cls): return tuple(cfgCls.__section__ for cfgCls in CONFIG_CLASSES if not cfgCls._loaded_)

    # @staticmethod
    # def _validateConfigFilePath_(path: str):
    #     if path is None:
    #         return None  # use default config file path (project path)
    #     elif not isdir(path):
    #         log.error(f"Invalid directory: {path}. Default config will be used")
    #         return False
    #     return True


if __name__ == '__main__':
    class TestConfig(ConfigLoader):
        P1 = 34
        P2 = 'bla bla'
        P3 = None
        P4 = [1, 2, 3, 4, 5]
        e = 'service'


    class TestConfig2(ConfigLoader):
        P1 = 'azaza'
        P2 = ('a', 'b', 'c', 'd', 'e')
        P3 = None
        s = 'service2'


    ConfigLoader.filename = 'testconfig.yaml'
    wd = r"D:\GLEB\Python\ProtocolProxy\v02"

    print(f"TestConfig dir: {formatDict(vars(TestConfig))}")
    print(f"TestConfig2 dir: {formatDict(vars(TestConfig2))}")

    TestConfig.load('APP', wd)
    TestConfig2.load('TEST', wd)

    print("TestConfig (loaded) params: \n" + linesep.join(
            f"    {name} = {getattr(TestConfig, name)}" for name in TestConfig.params()))
    print("TestConfig2 (loaded) params: \n" + linesep.join(
            f"    {name} = {getattr(TestConfig2, name)}" for name in TestConfig2.params()))

    input("Enter to save config...")

    print(f"TestConfig.P2: {TestConfig.P1}")
    print(f"TestConfig.P3: {TestConfig.P3}")

    TestConfig.P1 = 'newP1'
    TestConfig.P3 = 'newP2'

    TestConfig.save()

    print(f"TestConfig.P2: {TestConfig.P1}")
    print(f"TestConfig.P3: {TestConfig.P3}")
