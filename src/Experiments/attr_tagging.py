from __future__ import annotations as annotations_feature

from collections import defaultdict
from functools import partial
from itertools import starmap
from operator import setitem
from typing import Optional, Dict, Any, Mapping, NamedTuple, Union

from orderedset import OrderedSet

from Utils import attachItem, Logger, legacy

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

    def __get__(self, instance: OptionFetcher, owner):
        if owner is None: return self  # Access descriptor itself from class
        if instance.setupMode is False:
            # ▼ Act as normal getter
            return getattr(instance.options, self.name)
        else:
            # ▼ Set option to attr or change default value
            if self.owner is instance:
                # ▼ Same reference means option has been set earlier
                raise CodeDesignError(f"Duplicate option definition: {self.name}")
            self.owner = instance
            self.setOption(True)
            # return self to allow for option arguments via __call__
            return self

    def __call__(self, par):
        if self.VALIDATE_ARGUMENTS:
            self.owner.validateArgument(self.name, par)  # TODO: when to validate options?
        # ▼ If option is called with parameter, reassign option with provided value
        self.setOption(par)
        return self.owner

    def __getattr__(self, item):
        # ▼ If next option is defined, call another option descriptor through owner
        return self.owner.item

    def setOption(self, value):
        if isinstance(self.owner, Attr): setattr(self.owner.options, self.name, value)
        else: self.owner.defaultOptions[self.name] = value


class OptionFetcher:
    # CONSIDER: singleton? slots? apply to each class in a file

    defaultOptions = AttrOptions._field_defaults.copy()
    setupMode = True  # TODO: reset this to False when finished class creation

    for optionname in AttrOptions._fields:
        locals()[optionname] = Option(optionname)
        del optionname  # NOTE: awful hack — consider eliminating this

    def __getattr__(self, item):
        if self.setupMode is True:
            # ▼ Provide proper error message if wrong option is given
            raise CodeDesignError(f"Invalid option: {item}")
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    @staticmethod
    def validateArgument(option: str, par):
        if option == 'lazy':
            return isinstance(par, str)
        elif not isinstance(par, bool):
            raise CodeDesignError(f"Invalid value for '{option}': {par}")

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
        TODO: Attr docstring
    """

    __slots__ = 'name', 'default', 'type', 'tag', 'options'

    # TESTME: support 4 syntax variations (these 2 + with []):
    #           syntax1: str = attr(default_value) .option1 .option2(parameter) .optionN
    #           syntax2: str = attr(default_value, opt1=True, opt2='par', opt3=True)
    # CONSIDER: d: int = 3 <attr> 'lazy const -init'
    # CONSIDER: d: int = attr > 3 > 'lazy const -init'
    # CONSIDER: d: int = attr > 'lazy const -init'          # no default

    # CONSIDER: default_factory issue: is it still relevant
    #           when defaults are assigned to each instance individually?

    def __init__(self, value, **options):
        self.default = value
        # ▼ Apply section-common defaults
        self.validateOptions(options)
        self.options = AttrOptions(**self.defaultOptions, **options)

    def __str__(self):
        return f"Attr '{self.name}' {{{self.default}}} <{self.type}> " \
            f"{'|'.join(option for option in self.get('options').keys() if self.get(option) is not False)}"

    def get(self, item):
        """ Attribute getter for internal use """
        return super().__getattribute__(self, item)


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
        if tagname is None:
            # ▼ Reset tag
            if options:
                raise CodeDesignError("SECTION options could not be set when resetting tag")
            else:
                self.resetDefaults()
                self.proxy.resetTag()
                return

        elif not isinstance(tagname, str):
            raise CodeDesignError(f"Tag name is not a string: {tagname}")

        self.proxy.setNewTag(tagname.lower())

        self.validateOptions(options)

        self.defaultOptions = AttrOptions._field_defaults.update(**options)
        return self

    def __call__(self, *args):
        return self.__getitem__(*args)


class AnnotationProxy(dict):

    def __init__(self, clsdictProxy):
        super().__init__()
        self.target = clsdictProxy

    def __setitem__(self, attrname, value):
        log.debug(f'[__annotations__][{attrname}] ◄—— {value}')

        # ▼ Put annotation on its place
        self.target.annotations[attrname] = value

        # ▼ Assign tag if attr has no value, only annotation;
        #   duplicate assignments won't be performed since .tags is a set
        self.target.addAttr(attrname)

        # ▼ Assign attr.type, if current item is last added to __attrs__
        lastAddedAttr = self.target.attrs[-1]
        if lastAddedAttr.name == attrname: lastAddedAttr.type = value


class ClsdictProxy(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tags = self.setdefault('__tags__', defaultdict(OrderedSet))
        self.attrs = self.setdefault('__attrs__', [])
        self.annotations = self.setdefault('__annotations__', {})
        self.spy = AnnotationProxy(self)
        self.currentTag: str = None

    def __getitem__(self, key):
        log.debug(f'[{key}] ——►')
        if key == '__annotations__': return self.spy
        else: return super().__getitem__(key)

    def __setitem__(self, key, value):
        log.debug(f'[{key}] ◄—— {value}')
        if not isMemberFunction(self, value) and not isDunderAttr(key):
            self.addAttr(key, value)
        return super().__setitem__(key, value)

    def addAttr(self, attrname, value):
        """ Set tag to attr: dunders and member methods are ignored """
        if self.currentTag is not None:
            # ▼ Assign tag
            self.tags[self.currentTag].add(attrname)
        if isinstance(value, Attr): attr = value
        else: attr = Attr(value)
        attr.name = attrname
        attr.tag = self.currentTag
        self.attrs.append(attr)
        # TODO: create Attr() object here + rename method to 'createAttr'

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
