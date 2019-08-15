from __future__ import annotations as annotations_feature

from collections import defaultdict
from functools import partial
from itertools import starmap
from operator import setitem
from typing import Optional, Dict, Any, Mapping, NamedTuple, Union

from orderedset import OrderedSet

from Utils import attachItem, Logger, legacy, auto_repr, Null

log = Logger('AttrTagging')
log.setLevel('INFO')


def isDunderAttr(attrname: str) -> bool:
    return attrname.startswith('__') and attrname.endswith('__')


def isClassVar(annotation: str) -> bool:
    return annotation.startswith('ClassVar[') and annotation.endswith(']')


def isMemberFunction(target: Dict, attr) -> bool:
    if not hasattr(attr, '__qualname__'): return False  # just optimization not to fetch class qualname
    return attr.__qualname__ == f"{target.get('__qualname__')}.{attr.__name__}"


class CodeDesignError(TypeError):
    """ Error: class is used incorrectly by higher-level code """


@legacy  # not to break tests
class const:
    """ Marker class to denote immutable attrs """


@legacy
class OptionsParser:
    # CONSIDER: do I need singleton here?
    # _instance_ = None  # Make singleton as class just provides syntax
    #
    # def __new__(cls, *args, **kwargs):
    #     if not isinstance(cls._instance_, cls):
    #         cls._instance_ = object.__new__(cls)
    #     return cls._instance_

    def __init__(self, target: Dict[str, Any]):
        self.options = target

    def __get__(self, instance, owner):
        log.debug("Get option")  # set option without parameters
        self.attrobject = instance
        setattr(self.attrobject, self.name, True)
        return self.attrobject

    def __call__(self, par):
        setattr(self.attrobject, self.name, par)  # set option with parameter
        return self.attrobject


# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #


class AttrOptions(NamedTuple):
    const: bool = False
    lazy: Union[str, bool] = False
    factory: bool = NotImplemented  # TODO: 'factory' option


class Option:
    """ Option descriptor """

    __slots__ = 'name', 'owner'

    VALIDATE_ARGUMENTS = True

    def __init__(self, optionname: str):
        self.name: str = optionname
        self.owner: OptionFetcher = None
        # ▲ Target attr object, assigned in __get__

    def __get__(self, instance: OptionFetcher, ownercls):
        # ▼ Access descriptor itself from class
        if instance is None: return self

        # ▼ Act as normal getter if not in setup mode
        if instance.setupMode is False:
            return getattr(instance.options, self.name)

        # ▼ Same reference means option has been set earlier
        if self.owner is instance:
            raise CodeDesignError(f"Duplicate option definition: {self.name}")

        # ▼ Set option to attr or change default value otherwise
        self.owner = instance
        self.setOption(True)

        # ▼ Store current descriptor to allow owner redirect call with an argument
        self.owner.currentOption = self

        return self.owner

    def __call__(self, arg):
        if self.VALIDATE_ARGUMENTS:
            self.owner.validateArgument(self.name, arg)  # CONSIDER: when to validate options?
        # ▼ If option is called with argument, reassign option with provided value
        self.setOption(arg)
        self.owner.currentOption = None

    def __getattr__(self, item):
        # ▼ If next option follows, call another option descriptor through owner
        return getattr(self.owner, item)

    def setOption(self, value):
        if isinstance(self.owner, Attr):
            self.owner.options[self.name] = value
        elif isinstance(self.owner, SectionTitle):
            self.owner.defaultOptions[self.name] = value
        # CONSIDER: else — error?


class OptionFetcher:
    # CONSIDER: singleton? slots? apply to each class in a file

    defaultOptions = AttrOptions._field_defaults.copy()
    setupMode = True  # TODO: reset this to False when finished class creation
    currentOption = None

    for optionname in AttrOptions._fields:
        locals()[optionname] = Option(optionname)
    del optionname  # NOTE: awful hack — consider eliminating this

    def __getattr__(self, item):
        # ▼ Provide proper error message if wrong option is given
        if self.setupMode is True:
            raise CodeDesignError(f"Invalid option: {item}")
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    def __call__(self, optionArg):
        if self.currentOption is not None:
            self.currentOption(optionArg)
            return self
        else:
            raise CodeDesignError(f"Duplicate parenthesis in {self.currentOption.name} option")

    @staticmethod
    def validateArgument(optionname: str, par):
        if optionname == 'lazy':
            return isinstance(par, str)
        elif not isinstance(par, bool):
            raise CodeDesignError(f"Invalid value for '{optionname}': {par}")

    @classmethod
    def resetDefaults(cls):
        cls.defaultOptions.update(AttrOptions._field_defaults)

    @classmethod
    def validateOptions(cls, options: dict):
        for key, value in options.items():
            if key not in AttrOptions._fields: raise CodeDesignError(f"Invalid option: {key}")
            if cls.VALIDATE_ARGUMENTS: cls.validateArgument(key, value)


class Attr(OptionFetcher):
    """ Mutable default values must define .copy() method
            Options are optional (heh), bla bla bla...
                Syntax1: str = attr(default_value) .option1 .option2(parameter) .optionN
                Syntax2: str = attr(default_value, opt1=True, opt2='par', opt3=True)
        TODO: Attr docstring
    """

    __slots__ = 'name', 'default', 'type', 'tag', 'options'

    # CONSIDER: d: int = 3 <attr> 'lazy const -init'
    # CONSIDER: d: int = attr > 3 > 'lazy const -init'
    # CONSIDER: d: int = attr > 'lazy const -init'          # no default

    # CONSIDER: default_factory issue: is it still relevant
    #           when defaults are assigned to each instance individually?

    def __init__(self, value=Null, **options):
        self.default = value
        if options: self.validateOptions(options)
        # ▼ Apply section-common defaults
        self.options = {**self.defaultOptions, **options}

    def __str__(self):
        return f"Attr '{self.name}' ({self.default}) <{self.type}> ⚑{self.tag}" \
            f"{{{'|'.join(option for option in self.options.keys() if self.options)}}}".strip()

    def __repr__(self): auto_repr(self, self.name)


class SectionTitle(OptionFetcher):
    """ New section marker. Tells ClsdictProxy when new tag is defined.
        Usages (in class body) (options can be omitted, if not required):
            • SECTION('tag_name', option1, optionN)
            • SECTION('tag_name') .option1 .optionN
            (square brackets could be used instead — PyCharm highlights these statements nicely :)
        Supported options:
            • 'const' — all attrs in current section will be immutable
                        value may be changed though by accessing '_attrname_slot' attribute
                        (it's Python, babie)
        TODO: finish SectionTitle docstring
    """

    proxy: ClsdictProxy = None

    def __getitem__(self, tagname: Optional[str], **options):
        # ▼ Reset tag
        if tagname is None:
            if options:
                raise CodeDesignError("SECTION options could not be set when resetting tag")
            else:
                self.resetDefaults()
                self.proxy.resetTag()
                return

        elif not isinstance(tagname, str):
            raise CodeDesignError(f"Tag name is not a string: {tagname}")

        self.proxy.setNewTag(tagname.lower())

        if options: self.validateOptions(options)

        assert self.defaultOptions is OptionFetcher.defaultOptions  # TESTME
        self.defaultOptions = AttrOptions._field_defaults.update(**options)
        return self

    def __call__(self, *args):
        return self.__getitem__(*args)


class AnnotationProxy:

    def __init__(self, proxy):
        self.owner: ClsdictProxy = proxy

    def __setitem__(self, attrname, value):
        log.debug(f'[__annotations__][{attrname}] ◄—— {value}')

        # ▼ Put annotation on its place
        self.owner.annotations[attrname] = value

        # ▼ Add attr even if it has no value (only annotation)
        #   Duplicate tag assignments won't be performed since .tags contains SETs
        self.owner.addAttr(attrname)

        # ▼ Assign attr.type, if current item is last added to __attrs__
        # TODO: STOPPED HERE
        lastAddedAttr = self.owner.attrs[-1]
        if lastAddedAttr.name == attrname: lastAddedAttr.type = value


class ClsdictProxy(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.tags: defaultdict  = self.setdefault('__tags__', defaultdict(OrderedSet))
        self.attrs: list        = self.setdefault('__attrs__', [])
        self.annotations: dict  = self.setdefault('__annotations__', {})
        self.spy                = AnnotationProxy(self)
        self.currentTag: str    = None
        self.currentAttr: Attr  = None

    def __getitem__(self, key):
        log.debug(f'[{key}] ——►')
        if key == '__annotations__': return self.spy
        else: return super().__getitem__(key)

    def __setitem__(self, key, value):
        log.debug(f'[{key}] ◄—— {value}')
        if not isMemberFunction(self, value) and not isDunderAttr(key):
            self.addAttr(key, value)
        return super().__setitem__(key, value)

    def addAttr(self, attrname, value=Null):
        """ Set tag to attr: dunders and member methods are ignored """
        # ▼ Assign tag
        if self.currentTag is not None:
            self.tags[self.currentTag].add(attrname)

        # ▼ Create Attr() from member variable if not already
        attr = value if isinstance(value, Attr) else Attr(value)
        attr.name = attrname
        attr.tag = self.currentTag
        self.attrs.append(attr)

        # ▼ Store current attr to allow spy to set type and avoid duplicates
        self.currentAttr = attr

    @legacy
    def set(self, key, value):
        """ __setitem__() for internal use """
        return super().__setitem__(key, value)

    def resetTag(self):
        self.currentTag = None

    def setNewTag(self, tagname):
        # ▼ check for duplicating section
        if tagname in self.tags.keys():
            raise CodeDesignError(f"Section '{tagname}': found duplicate definition")
        self.currentTag = tagname


class TaggedAttrsTitledType(type):
    """ TODO: TaggedAttrsTitledType docstring
        Variables defined without annotations are not tagged
        SECTION without any attrs inside is not created
        Tag names are case-insensitive
        Member methods (class is direct parent in __qualname__) are not tagged,
            even if they are assigned not using 'def'
    """

    __tags__ = {}

    @classmethod
    def __prepare__(metacls, clsname, bases, enableAttrsTagging=True):
        if enableAttrsTagging:
            SECTION.proxy = ClsdictProxy()
            return SECTION.proxy
        else: return {}

    def __new__(metacls, clsname, bases, clsdict, **kwargs):
        args = (metacls, clsname, bases, clsdict)  # CONSIDER: should I explicitly do 'dict(clsdict)' here?

        # ▼ Use tags that are already in clsdict if no parents found
        if hasattr(clsdict, 'tags') and bases:
            # ▼ Collect all base class tags dicts + current class tags dict
            tagsDicts = attachItem(filter(None, (parent.__dict__.get('__tags__') for parent in bases)), clsdict.tags)

            # ▼ Take main parent's tags as base tags dict
            try: newTags = clsdict['__tags__'] = tagsDicts.__next__().copy()

            # ▼ Use current tags if no single parent defines any
            except StopIteration: return super().__new__(*args)

            # ▼ Merge all tags by tag name
            for tagsDict in tagsDicts:
                reduce_items = ((tagname, newTags[tagname] | namesSet) for tagname, namesSet in tagsDict.items())
                for _ in starmap(partial(setitem, newTags), reduce_items): pass
        # TODO: cleanup Attr (reset defaults, for ex) not to disrupt future Attr class use
        Attr.setupMode = False
        return super().__new__(*args)


SECTION = SectionTitle()

# TODO: move all these shortcuts to a separate file (for ex., classtools.py)

TaggedType = TaggedAttrsTitledType


class Tagged(TaggedType): pass


if __name__ == '__main__':
    ...
