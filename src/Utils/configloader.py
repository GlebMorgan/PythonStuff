from __future__ import annotations

from copy import deepcopy
from os import linesep, makedirs, listdir
from os.path import join as joinpath, basename, isdir, expandvars as envar, isfile
from shutil import copyfile
from typing import Dict, Type, Set

from .colored_logger import Logger
from .utils import formatDict, formatList, isiterable, classproperty
from ruamel.yaml import YAML, YAMLError


log = Logger("Config")
log.setLevel("DEBUG")


CONFIG_CLASSES: Set[Type[ConfigLoader]] = set()
CONFIGS_DICT: Dict[str, dict] = {}


class ConfigLoader:
    """ Usage: class CONFIG(ConfigLoader, section='NAME')
        When subclassed, stores all UPPERCASE (of which isupper() returns True)
        class attrs as dict of categories with config parameters
        and saves/loads them to/from .yaml file
        Only specified object types are allowed inside config
    """

    LOADER = 'yaml'

    # ▼ Immutable types must have .copy() attr
    SUPPORTED_TYPES = (int, float, str, bytes, bool, tuple, list, dict, set, type(None))

    # ▼ Config is stored in APPDATA.PelengTools by default
    #   Should not be used as complete config file path; application subdirectory needs to be appended
    CONFIG_FILE_BASE_PATH = joinpath(envar('%APPDATA%'), '.PelengTools')

    # ▼ Config file will be created automatically in case no one was found on specified path
    AUTO_CREATE_CONFIG_FILE = True

    filename: str = 'config.yaml'
    path: str = None

    if LOADER == 'yaml':
        loader = YAML(typ='safe')
        loader.default_flow_style = False
    elif LOADER == 'json':
        raise NotImplementedError('JSON loader needs testing!')

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
            if not isdir(cls.path):
                dirs = sorted(listdir(cls.CONFIG_FILE_BASE_PATH))
                raise ValueError(f"Config directory ['{app}'] not found. Existing directories: {dirs or 'None'}")
        elif cls.path is None:
            raise RuntimeError("Application config directory path is not specified. "
                               f"{cls.__mro__[-2].__name__}.path or {cls.__name__}.path should be provided")

        if not isdir(cls.path):
            raise ValueError(f"Application config path is invalid directory: {cls.path}")

        invalidAttrs = cls._checkInvalidTypes_()
        if invalidAttrs:
            displayList = formatList((f'{name}: {type(getattr(cls, name))}' for name in invalidAttrs), indent=4)
            raise TypeError(f"{cls.__name__} contains invalid attr types:{linesep}{displayList}")

        log.info(f"Fetching config for '{cls.__section__}'...")

        if force or not CONFIGS_DICT:
            # Empty CONFIGS_DICT => .load() is called for the first time => load config from file
            log.debug(f"Config path: {cls.path}")
            path = joinpath(cls.path, cls.filename)
            if not cls._loadFromFile_(path):
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
        try: return CONFIGS_DICT[cls.__section__] != dict(cls.members())
        except KeyError: return True

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
        if not isfile(path):
            force = True
            if cls.AUTO_CREATE_CONFIG_FILE is False:
                log.debug("{cls.__name__} is configured not to create config file automatically")
                return False
            elif not isdir(cls.path):
                try: makedirs(cls.path)
                except OSError as e:
                    log.error(f"Failed to create config directory tree:{linesep}{e}")
                    return False
                else: log.debug(f"Created directory {cls.path}")

        if not force:
            updatedConfigs = tuple(cfgCls for cfgCls in CONFIG_CLASSES if cfgCls.updated is True)
            if updatedConfigs == ():
                log.info("No config changes in all sections – save skipped")
                return False
            else: log.info(f"Updated sections: {', '.join(cfg.__section__ for cfg in updatedConfigs)}")
        else:
            updatedConfigs = CONFIG_CLASSES
            log.debug(f"Force saving config for sections {', '.join(sections)}")

        newConfigsDict = {cfgCls.__section__: dict(cfgCls.members()) for cfgCls in updatedConfigs}
        global CONFIGS_DICT
        CONFIGS_DICT.update({key: deepcopy(cfg) for key, cfg in newConfigsDict.items()})

        if isfile(path): cls.createBackup(path)

        log.debug(f"Saving config to file {cls.filename}...")
        try:
            with open(path, 'w', encoding='utf-8') as configFile:
                cls.loader.dump(CONFIGS_DICT, configFile)
        except (OSError, YAMLError) as e:
            log.error(f"Failed to save configuration file:{linesep}{e}")
            return False
        else:
            log.info(f"Config saved to {cls.filename}")
            return True

    @classmethod
    def createBackup(cls, path) -> bool:
        try:
            copyfile(path, path + '.bak')
        except OSError as e:
            log.error(f"Failed to create backup config file: {e}")
            return False
        else:
            log.debug(f"Created backup config {cls.filename + '.bak'}")
            return True

    @classmethod
    def revert(cls, path=path):
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
        log.info(f"Loading {filetype} from {cls.filename}...")
        try:
            with open(path, encoding='utf-8') as configFile:
                # ▼ expect dict of config dicts in config file
                configsDict = cls.loader.load(configFile)
                if configsDict is None:
                    log.warning(f"{filetype.capitalize()} file is empty")
                    return False
                if not isinstance(configsDict, dict):
                    log.error(f"Config loader {cls.loader.__class__.__name__} "
                              f"returned invalid result type: {configsDict.__class__.__name__}")
                    return False
                else:
                    global CONFIGS_DICT
                    if not CONFIGS_DICT:
                        CONFIGS_DICT = {key: cfg if cfg is not None else {} for key, cfg in configsDict.items()}
                    else:
                        for section, config in configsDict.items():
                            sectionDict = CONFIGS_DICT.setdefault(section, {})
                            if config is not None: sectionDict.update(config)
                    log.debug(f"Config loaded: {formatDict(configsDict)}")
                    return True  # succeeded loading from file
        except YAMLError as e:
            log.error(f"Failed to parse {filetype} file:{linesep}{e}")
            return False
        except FileNotFoundError:
            log.warning(f"{filetype.capitalize()} file {basename(path)} not found")
            return False

    @classmethod
    def _addCurrentSection_(cls):
        CONFIGS_DICT[cls.__section__] = deepcopy(dict(cls.members()))
        log.debug(f"New section added: {cls.__section__} {formatDict(CONFIGS_DICT[cls.__section__])}")

    # @staticmethod
    # def _validateConfigFilePath_(path: str):
    #     if path is None:
    #         return None  # use default config file path (project path)
    #     elif not isdir(path):
    #         log.error(f"Invalid directory: {path}. Default config will be used")
    #         return False
    #     return True


if __name__ == '__main__':
    try:
        from os import system
        system(r'cd ..\Tests && python -m pytest configloader_test.py -ra -vvv')
    except Exception as e:
        print(e)
        input('...')
