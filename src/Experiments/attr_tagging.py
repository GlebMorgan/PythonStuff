from __future__ import annotations as annotations_feature

from collections import defaultdict
from functools import partial
from itertools import starmap
from operator import setitem
from typing import Optional, Dict, NamedTuple, Union

from orderedset import OrderedSet

from Utils import attachItem, Logger, legacy, auto_repr, Null

log = Logger('AttrTagging')
log.setLevel('INFO')

VALIDATE_OPTION_ARGUMENTS = True


def isDunderAttr(attrname: str) -> bool:
    return attrname.startswith('__') and attrname.endswith('__')


def isClassVar(annotation: str) -> bool:
    return annotation.startswith('ClassVar[') and annotation.endswith(']')


def isMemberFunction(target: Dict, attr) -> bool:
    # ▼ Avoid error due to Attr.setupMode
    if hasattr(attr, __dict__) and attr.__dict__.get('__qualname__') is None: return False
    if not hasattr(attr, '__qualname__'): return False  # just optimization not to fetch class qualname
    return attr.__qualname__ == f"{target.get('__qualname__')}.{attr.__name__}"


class CodeDesignError(TypeError):
    """ Error: class is used incorrectly by higher-level code """


class AttrOptions(NamedTuple):
    const: bool = False
    lazy: Union[str, bool] = False
    factory: bool = NotImplemented  # TODO: 'factory' option


class Option:
    """ Option descriptor """

    __slots__ = 'name', 'owner'

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
        if VALIDATE_OPTION_ARGUMENTS:
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
            raise CodeDesignError(f"Invalid option: {item}")  # FIXME: This is raised constantly on internal calls
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    def __call__(self, optionArg):
        if self.currentOption is not None:
            self.currentOption.__call__(optionArg)
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
            if VALIDATE_OPTION_ARGUMENTS: cls.validateArgument(key, value)


class Attr(OptionFetcher):
    """ Mutable default values must define .copy() method
            Syntax: (options are optional (heh), bla bla bla... )
                • name1: type = attr(default_value) .option1 .option2('parameter') .optionN(whatever)
                • name2: type = attr(default_value, option1=False, option2='parameter', optionN=whatever)
        Supported options:
            • 'const' — all attrs in current section will be immutable
                        value may be changed though by accessing '_attrname_slot' attribute
                        (it's Python, babie)
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
        self.type = Null
        if options: self.validateOptions(options)
        # ▼ Apply section-local defaults
        self.options = {**self.defaultOptions, **options}
        # ▲ CONSIDER: store only those options which != defaults
        #             and refer to latter when needed (for ex, in __str__)

    def __str__(self):
        return f"Attr '{self.name}' ({self.default}) <{self.type}> ⚑{self.tag}" \
            f"{{{'|'.join(option for option in self.options.keys() if option is not False)}}}".strip()

    def __repr__(self): auto_repr(self, self.name)


class SectionTitle(OptionFetcher):
    """ New section marker. Tells ClassdictProxy when new tag is defined.
        Syntax (expected within class body) (options can be omitted, if not required):
            • SECTION('tag_name', option1=par, optionN=True)
            • SECTION('tag_name') .option1(par) .optionN
            (square brackets could be used instead — PyCharm highlights these statements nicely :)
        Supported options:
            • 'const' — all attrs in current section will be immutable
                        value may be changed though by accessing '_attrname_slot' attribute
                        (it's Python, babie)
        TODO: finish SectionTitle docstring
    """

    proxy: ClassdictProxy = None

    def __getitem__(self, tagname: Optional[str], **options):
        # ▼ Reset tag
        if tagname is None:
            if options:
                raise CodeDesignError("SECTION options could not be set when resetting tag")
            else:
                self.resetDefaults()
                self.proxy.currentTag = None
                # ▼ Give nicer error message if option is defined further using dot notation
                return self.__class__

        elif not isinstance(tagname, str):
            raise CodeDesignError(f"Tag name is not a string: {tagname}")

        self.proxy.setNewTag(tagname.lower())

        if options: self.validateOptions(options)

        # ▼ Set section-local defaults based on global defaults
        assert self.defaultOptions is OptionFetcher.defaultOptions  # TESTME
        self.defaultOptions = AttrOptions._field_defaults.update(**options)
        return self

    def __call__(self, *args):
        return self.__getitem__(*args)


class AnnotationProxy:
    """ Non-annotated attrs are not processed due to Python' method bounding freedom
        ... TODO
    """
    # CONSIDER: add annotation-only attrs to cls.__attrs__ later, along with setting attr.type;
    #           may be problematic since OrderedSet seems incapable of inserting an item in the middle...
    def __init__(self, proxy):
        self.owner: ClassdictProxy = proxy

    def __setitem__(self, attrname, value):
        log.debug(f'[__annotations__][{attrname}] ◄—— {value}')

        # ▼ Put annotation on its place
        self.owner.annotations[attrname] = value

        # ▼ Add attr even if it has not been assigned with anything (only annotation)
        if self.owner.currentAttr.name != attrname: self.owner.addAttr(attrname)

        self.owner.currentAttr.type = value



class ClassdictProxy(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.tags: defaultdict = self.setdefault('__tags__', defaultdict(OrderedSet))
        self.attrs: list = self.setdefault('__attrs__', [])
        self.annotations: dict = self.setdefault('__annotations__', {})
        self.spy = AnnotationProxy(self)
        self.currentTag: str = None
        self.currentAttr: Attr = None

    def __getitem__(self, key):
        log.debug(f'[{key}] ——►')
        if key == '__annotations__': return self.spy
        else: return super().__getitem__(key)

    def __setitem__(self, key, value):
        log.debug(f"[{key}] ◄—— {value if not isinstance(value, Attr) else '<Attr object>'}")
        if not isMemberFunction(self, value) and not isDunderAttr(key):
            self.addAttr(key, value)
        return super().__setitem__(key, value)  # TODO: If slots, don't set class variable

    def addAttr(self, attrname, value=Null):
        """ Set tag to attr: dunders and member methods are ignored """

        # ▼ Assign tag  # NOTE: 'None' is a valid key now (to allow for an easy sample of all non-tagged attrs)
        self.tags[self.currentTag].add(attrname)

        # ▼ Create Attr() from member variable if not already
        attr = value if isinstance(value, Attr) else Attr(value)
        attr.name = attrname
        attr.tag = self.currentTag

        self.attrs.append(attr)
        self.currentAttr = attr

    @legacy
    def set(self, key, value):
        """ __setitem__() for internal use """
        return super().__setitem__(key, value)

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
    def __prepare__(metacls, clsname, bases, enableClasstools=True):
        if enableClasstools:
            SectionTitle.proxy = ClassdictProxy()
            return SectionTitle.proxy
        else: return {}

    def __new__(metacls, clsname, bases, clsdict, **kwargs):

        # ▼ Make attrs option descriptors work as expected
        Attr.setupMode = False
        Attr.resetDefaults()

        # ▼ Use tags that are already in clsdict if no parents found
        if hasattr(clsdict, 'tags') and bases:
            clsdict['__tags__'] = metacls.mergeTags(bases, clsdict.tags)

        # ▼ CONSIDER: should I explicitly do 'dict(clsdict)' here?
        return super().__new__(metacls, clsname, bases, clsdict)

    @staticmethod
    def mergeTags(parents, currentTags):
        # ▼ Collect all base class tags dicts + current class tags dict
        tagsDicts = attachItem(filter(None, (parent.__dict__.get('__tags__') for parent in parents)), currentTags)

        # ▼ Take main parent's tags as base tags dict
        try: newTags = tagsDicts.__next__().copy()

        # ▼ Use current tags if no single parent defines any
        except StopIteration: return currentTags

        # ▼ Merge all tags by tag name into 'newTags'
        for tagsDict in tagsDicts:
            reduceItems = ((tagname, newTags[tagname] | namesSet) for tagname, namesSet in tagsDict.items())
            for _ in starmap(partial(setitem, newTags), reduceItems): pass
            # TODO: Compare performance ▲ ▼, if negligible - replace with code below (more readable IMHO)
            # for tagname, updatedNamesSet in reduceItems:
            #     setitem(newTags, tagname, updatedNamesSet)
        return newTags


SECTION = SectionTitle()

# TODO: move all these shortcuts to a separate file (for ex., classtools.py)

TaggedType = TaggedAttrsTitledType


class Tagged(TaggedType): pass


if __name__ == '__main__':
    ...

    class A(metaclass=TaggedType):
        a = Attr(1, const=True)


    a = A()
