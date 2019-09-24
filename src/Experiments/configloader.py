from __future__ import annotations

from itertools import compress
from os import linesep
from os.path import join as joinpath, dirname, abspath, basename, isdir, expandvars as envar
from shutil import copyfile
from typing import Dict, Type, Set

from Utils import Logger, formatDict
from ruamel.yaml import YAML, YAMLError


# CONSIDER: Constrain assigning common settings to ConfigLoader attrs (like .filePath and .loader), not child class


log = Logger("Config")


CONFIG_CLASSES: Set[Type[ConfigLoader]] = set()
CONFIGS_DICT: Dict[str, dict] = {}


class ConfigLoader:
    """ When subclassed, stores all UPPERCASE (of which isupper() returns True)
        class attrs as dict of categories with config parameters
        and saves/loads them to/from .yaml file
    """

    # ▼ Config is stored in APPDATA.PelengTools by default
    #   Should not be used as complete config file path; application subdirectory needs to be appended
    CONFIG_FILE_BASE_PATH = joinpath(envar('%APPDATA%'), '.PelengTools')

    # ▼ Config file will be created automatically in case no one was found on specified path
    AUTO_CREATE_CONFIG_FILE = True

    filename: str = 'config.yaml'
    path: str = None
    loader = YAML(typ='safe')
    loader.default_flow_style = False

    # Initialized by successors:
    loaded = False
    ignoreUpdates = False
    section: str = None

    @classmethod
    def load(cls, section: str, app: str = None, force=False):
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

        log.info(f"Fetching config for '{section}'...")

        cls.section = section
        CONFIG_CLASSES.add(cls)

        if force or not CONFIGS_DICT:
            # Empty CONFIGS_DICT => .load() is called for the first time => load config from .yaml file
            path = joinpath(cls.path, cls.filename)
            log.debug(f"Loading config for '{cls.section}' from {path}...")
            if not cls._loadFromFile_(path):  # => non existent or empty file => no profit, use defaults
                return cls._useDefaultConfig_()

        try:
            configFileDict = CONFIGS_DICT[cls.section].copy()
        except KeyError:
            log.warning(f"Cannot find section '{cls.section}' in config file. Creating new one with defaults.")
            cls._addCurrentSection_()
            return cls._useDefaultConfig_()

        for parName in cls.params():
            currPar = getattr(cls, parName)
            try: newPar = configFileDict.pop(parName)
            except KeyError:
                log.error(f"Parameter '{parName}': not found in config file {cls.filename}")
                continue
            else:
                if currPar is not None and newPar is not None:
                    # cast to current type
                    try: newPar = type(currPar)(newPar)
                    except (ValueError, TypeError) as e:
                        log.error(f"Parameter '{parName}': cannot convert '{newPar}' "
                                  f"to type '{type(currPar).__name__}' ––► {e}")
                        continue
                setattr(cls, parName, newPar)
        if len(configFileDict) != 0:
            log.warning(f"Unexpected parameters found in configuration file: {', '.join(configFileDict)}")
            currSectionDict = CONFIGS_DICT[cls.section]
            for par in configFileDict: del currSectionDict[par]

        cls.loaded = True
        log.info(f"Config '{cls.section}' loaded, {len(tuple(cls.params()))} items")
        log.debug(f"{cls.__name__}: {formatDict({name: getattr(cls, name) for name in cls.params()})}")

    @classmethod
    def update(cls):
        """ Update internal config storage with actual class attrs (if .ignoreUpdates is False)
            Returns True if actual config has been changed, False otherwise, None if configured to ignore updates
            May be used to save current class config only: CFG.save(CFG.update())
            CONSIDER: (True, 2, 3.0) == (1,2,3) as well as [1,2] != (1,2) => need to compare types as well
        """
        assert CONFIGS_DICT
        if cls.ignoreUpdates is True:
            log.info(f"Section '{cls.section}': updates ignored by request")
            return None

        storedConfig = tuple(CONFIGS_DICT[cls.section].values())
        CONFIGS_DICT[cls.section].update({name: getattr(cls, name) for name in cls.params()})
        current_config = tuple(CONFIGS_DICT[cls.section].values())

        return storedConfig != current_config

    @classmethod
    def save(cls, force=None):
        """ Save all config sections to config file if any have changed or if forced
            NOTE: Call this method before app exit
        """

        # ▼ Skip save on False. Used when necessity of save is acquired dynamically (ex: CFG.save(CFG.update()))
        if force is False:
            log.debug(f"Section '{cls.section}': Save skipped (no changes)")
            return False

        if not CONFIG_CLASSES:
            assert False, "what should I log here?"
            if AUTO_CREATE_CONFIG_FILE is False:
                log.debug("{cls.__name__} is configured not to create initial config file")
                return False

        sections = (configCls.section for configCls in CONFIG_CLASSES)

        if not force:
            log.info(f"Updating config for sections {', '.join(sections)}")
            configChanged = (configCls.update() for configCls in CONFIG_CLASSES)
            # ▼ the iteration order on the SET is consistent within single execution run, so results will be aligned
            updatedConfigSections = tuple(configCls.section for configCls in compress(CONFIG_CLASSES, configChanged))
            newSections = cls._fileUpdateSections_()
            if updatedConfigSections or newSections:
                log.debug(f"Config updated for sections: {', '.join(set(updatedConfigSections + newSections))}")
            else:
                log.info("Config does not change, save skipped")
                return False
        else:
            log.debug(f"Force saving config for sections {', '.join(sections)}")

        path = joinpath(cls.path, cls.filename)

        log.debug(f"Creating backup config file {cls.filename + '.bak'}")
        cls.backup(path)

        log.debug(f"Saving config to file {cls.filename}")
        try:
            with open(path, 'w') as configFile:
                cls.loader.dump(CONFIGS_DICT, configFile)
                log.info(f"Config saved for sections: {', '.join(sections)}")
        except (OSError, YAMLError) as e:
            log.error(f"Failed to save configuration file:{linesep}{e}")

    @classmethod
    def backup(cls, path):
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
    def params(cls):
        """ Iterate through all class attr names that are treated as config params """
        yield from (attrName for attrName in vars(cls).keys() if attrName.isupper())

    @classmethod
    def _useDefaultConfig_(cls):
        # Just return and use class attrs when querying config params
        log.info(f"Using default config for '{cls.section}'")

    @classmethod
    def _loadFromFile_(cls, path) -> bool:
        """ Load dict of config sections from .yaml file to CONFIGS_DICT module variable,
            return boolean value = failed/succeeded
        """
        # ▼ Denotes whether `file` is a backup file
        backup = path.endswith('.bak')
        filetype = 'backup' if backup else 'config'
        try:
            with open(path) as configFile:
                # ▼ expect dict of config dicts in config file
                configDict = cls.loader.load(configFile)
                if configDict is None:
                    log.warning(f"{filetype.capitalize()} file is empty")
                    return cls._loadFromBackup_(path) if not backup else False
                if not isinstance(configDict, dict):
                    log.error(f"Config loader {cls.loader.__class__.__name__} "
                              f"returned invalid result type: {configDict.__class__.__name__}")
                    return cls._loadFromBackup_(path) if not backup else False
                else:
                    CONFIGS_DICT.update(configDict)
                    log.debug(f"Config for '{cls.section}' loaded: {formatDict(configDict)}")
                    return True  # succeeded loading from file
        except YAMLError as e:
            log.error(f"Failed to parse {filetype} file:{linesep}{e}")
            return cls._loadFromBackup_(path) if not backup else False
        except FileNotFoundError:
            log.warning(f"{filetype.capitalize()} file {basename(path)} not found")
            return False
        finally:
            if CONFIGS_DICT.get(cls.section) is None: cls._addCurrentSection_()

    @classmethod
    def _loadFromBackup_(cls, path):
        log.debug(f"Loading backup config for '{cls.section}'...")
        status = cls._loadFromFile_(path + '.bak')
        if status is True: cls.revert(path)
        return status

    @classmethod
    def _addCurrentSection_(cls):
        CONFIGS_DICT[cls.section] = {parName: getattr(cls, parName) for parName in cls.params()}
        log.debug(f"New section added: {cls.section} {formatDict(CONFIGS_DICT[cls.section])}")

    @classmethod
    def _fileUpdateRequired_(cls): return any(not configClass.loaded for configClass in CONFIG_CLASSES)

    @classmethod
    def _fileUpdateSections_(cls): return tuple(cfgCls.section for cfgCls in CONFIG_CLASSES if not cfgCls.loaded)

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
