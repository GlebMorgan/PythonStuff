from collections import defaultdict
from functools import partial
from itertools import starmap
from operator import setitem
from typing import Any, ClassVar, NamedTuple, Union, Dict, Optional

from orderedset import OrderedSet
from Utils import auto_repr, Null, Logger, attachItem, formatDict

__options__ = 'tag', 'const', 'lazy'

# ▼ TODO: Elaborate this, maybe, even add kind of check in ClassDictProxy.__setitem__
# ▼ ONLY Attr() objects may be assigned to variables inside user class definition!
__all__ = 'Attr', 'TAG', 'OPTIONS', *__options__

log = Logger('AttrTagging')
log.setLevel('INFO')


# CONSIDER: __all__ = tag, const, lazy, TAG, OPTIONS
# TODO: check for duplicating tags inside TAG SectionTitle object (store list of used tags and compare on __call__())
# TODO: store attrs in dict {name: Attr()} instead of list

# GENERAL CONFIG:

# Add option definition objects (those used with '|option' syntax) to class dict
# to make their names available (only) inside class body, thus avoiding extra imports
# These objects will be removed from class dict as soon as class statement is fully executed
INJECT_OPTIONS = True

# Auto-initialize all annotated attrs without assignment with None value
AUTO_INIT = False


# NOTE: always deny non-annotated attrs for now
# Raise error if non-function attr is declared without annotation,
# else — treat non-annotated attrs as class attrs (do not process them with class tools routine)
# Note: non-annotated attrs inside SECTION blocks are not allowed
DENY_BARE_ATTRS = False


class CodeDesignError(TypeError):
    """ Error: class is used incorrectly by higher-level code """


def activateSetupMode(function):
    def setupModeWrapper(*args, **kwargs):
        Option.__setattr__ = Option.denyAttrAccess
        result = function(*args, **kwargs)
        Option.__setattr__ = object.__setattr__
        return result
    return setupModeWrapper


class AnnotationProxy:
    """ Non-annotated attrs are not processed due to Python' method bounding freedom
        ... TODO
    """
    # CONSIDER: add annotation-only attrs to cls.__attrs__ later, along with setting attr.type;
    #           may be problematic since OrderedSet seems incapable of inserting an item in the middle...
    def __init__(self, proxy):
        self.owner: ClassDictProxy = proxy

    def __setitem__(self, attrname, annotation):
        log.debug(f'[__annotations__][{attrname}] ◄—— {annotation}')

        # ▼ Put annotation on its place
        self.owner.annotations[attrname] = annotation

        attr = self.owner.currentAttr

        # ▼ Create Attr() if variable was declared using just name and annotation
        if attr.name != attrname:
            attr = Attr(attrname, None) if AUTO_INIT else Attr(attrname)
        attr.type = annotation

        # ▼ Set options if not defined earlier by option definition objects
        for option in ('tag', 'const', 'lazy'):
            if not hasattr(self, option):
                setattr(self, option, self.owner.currentOptions[option])

        # NOTE: 'None' is a valid tag key (to allow for an easy sample of all non-tagged attrs)
        self.owner.tags[attr.tag].add(attrname)

        self.owner.attrs[attrname] = attr


class ClassDictProxy(dict):
    """ Non-annotated attrs are not processed outside SECTION
        ... TODO
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.tags: defaultdict = self.setdefault('__tags__', defaultdict(OrderedSet))
        self.attrs: dict = self.setdefault('__attrs__', {})
        self.annotations: dict = self.setdefault('__annotations__', {})

        self.spy = AnnotationProxy(self)
        self.injectSlots = False  # TODO: Fetch this from outside
        self.currentOptions: Dict[str, Any] = {}
        self.currentAttr: Attr = None

        # ▼ Initialize options
        self.resetOptions()

    def __getitem__(self, key):
        log.debug(f'[{key}] ——►')
        if key == '__annotations__': return self.spy
        else: return super().__getitem__(key)

    def __setitem__(self, key, value):
        log.debug(f"[{key}] ◄—— {value if not isinstance(value, Attr) else f'<Attr object {value.default}>'}")

        # ▼ Skip dunder attrs pass Attr mechanics
        if key.startswith('__') and key.endswith('__'):
            return super().__setitem__(key, value)

        # ▼ Set current attr (create one, if not already)
        if isinstance(value, Attr):
            value.name = key
            self.currentAttr = value
            value = value.default
        else: self.currentAttr = Attr(key, value)

        # ▼ Avoid creating conflicting class attr, if injecting slots
        if not self.injectSlots:
            return super().__setitem__(key, value)

    def resetOptions(self):
        self.currentOptions.update({option.name: option.default for option in (tag, const, lazy)})


class Attr:
    """
        ... TODO
    """

    __slots__ = 'name', 'default', 'type', 'tag', 'const', 'lazy'

    def __init__(self, name=Null, value=Null):
        if name is not Null: self.name = name
        self.default = value
        # FIXME: ASSIGN DEFAULT OPTION HERE!!!

    def __str__(self):
        return f"Attr '{self.name}' [{self.default}] <{self.type}> ⚑{self.tag}" \
               f"{' 🔒'*self.const}{' 🕓'*self.lazy}"

    def __repr__(self): return auto_repr(self, self.name)


class Section:

    proxy: ClassDictProxy = None

    def __enter__(self): pass

    def __exit__(self, *args):
        self.proxy.resetOptions()



class Option:
    """
        |option       – enable option (or set value to default) (if supported)
        |option(arg)  – set option value to arg (if supported)
        |-option      – disable option (or set value to None)

        • default (option value)
        • flag (option type):
            flag=True  – option is True/False only, no parameters are accepted
            flag=False – option stores a value, that must be provided as an argument
            flag=None  – option stores a value, but argument could be omitted
                            (.default will be used as a value in this case)
    """

    __slots__ = 'name', 'value', 'state', 'default', 'flag'

    def __init__(self, name, *, default, flag: Union[bool, None]):
        self.name = name
        self.default = default  # default value, <bool> if .type=True
        self.flag = flag  # require, allow or deny argument
        # ▼ Stores current value (changed by modifiers, reset after applying to attr)
        self.value = Null

    def __ror__(self, value):  # CONSIDER: rename value to smth more suitable

        # ▼ Set .value to appropriate default if option used with no modifiers
        if self.value is Null:
            if self.flag is False:
                raise CodeDesignError(f"Option {self.name} requires an argument")
            else:
                self.value = True if self.flag is True else self.default

        # ▼ If applied to Section, change section-common defaults via Section.proxy
        if isinstance(value, Section):
            self.value.proxy.currentOptions[self.name] = self.value

        # ▼ Else, convert value to Attr() and apply option to it
        else:
            if not isinstance(value, Attr):
                value = Attr(value=value)
            setattr(value, self.name, self.value)

        # ▼ Reset value if altered by modifiers
        self.value = Null
        return value

    def __call__(self, arg):
        if self.flag is True:
            raise CodeDesignError(f"Option {self.name} is not callable")
        self.value = arg
        return self

    def __neg__(self):
        # CONSIDER: isinstance(False, int) is True,
        #   so care should be taken if 'int' options would be created in future
        # NOTE: disabling an option with assigned argument will reset it
        self.value = False if self.flag is True else None
        return self

    def denyAttrAccess(self, name, value):
        raise AttributeError(f"'{self.name}' object is not intended to use beyond documented syntax")


class TaggedAttrsTitledType(type):
    """ TODO: TaggedAttrsTitledType docstring
        Variables defined without annotations are not tagged
        SECTION without any attrs inside is not created
        Tag names are case-insensitive
        Member methods (class is direct parent in __qualname__) are not tagged,
            even if they are assigned not using 'def'
    """

    # __tags__ = {}  # FIXME: move this to cls.__new__ !
    # __attrs__ = {}  # FIXME: move this to cls.__new__ !

    # TODO: Make revision of all this class

    @classmethod
    def __prepare__(metacls, clsname, bases, enableClasstools=True):
        if enableClasstools:
            proxy = Section.proxy = ClassDictProxy()
            return proxy
        else:
            return {}

    @activateSetupMode
    def __new__(metacls, clsname, bases, clsdict: Union[ClassDictProxy, dict], **kwargs):

        # ▼ Use tags that are already in clsdict if no parents found
        if hasattr(clsdict, 'tags') and bases:
            clsdict['__tags__'] = metacls.mergeTags(bases, clsdict.tags)
            clsdict['__attrs__'] = metacls.mergeParentDicts(bases, '__attrs__', clsdict.attrs)

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

    @staticmethod
    def mergeParentDicts(parents, dictName, currentDict):
        dicts = attachItem(
                filter(None, (parent.__dict__.get(dictName) for parent in reversed(parents))), currentDict)
        newDict = dicts.__next__().copy()
        for attrDict in dicts: newDict.update(attrDict)
        return newDict


tag = Option('tag', default=None, flag=False)
const = Option('const', default=False, flag=True)
lazy = Option('lazy', default=False, flag=None)

# If adding new option, add it to:
#     1) Option() objects above
#     2) __options__ global variable
#     3) Attr.__slots__ ('..., *__options__' is not used there
#         because PyCharm fails to resolve attributes that way round)
#     4) Attr.__str__ option icons
#     5) Attr() initialization in AnnotationProxy.__setitem__
#     6) ClassDictProxy.resetOptions() options list

OPTIONS = Section()
TAG = Section()






if __name__ == '__main__':


    class A(metaclass=TaggedAttrsTitledType):
        a: int = 4

    print(formatDict(A.__attrs__))
    print(A.__tags__)
    print(A().a)
    exit()

    from contextlib import contextmanager

    @contextmanager
    def TAG(tagname):
        print(f"tagname is {tagname}")
        yield
        print(f"cleared tagname {tagname}")

    @contextmanager
    def OPTIONS(): yield

    class Const:
        def __rrshift__(self, other): return other
        def __lt__(self, other): return other
        def __rmatmul__(self, other): return other
        def __matmul__(self, other): return self
        def __ror__(self, other): return other
        def __or__(self, other): return self
        def __neg__(self): return self
        def __call__(self, *args, **kwargs): return self

    const = Const()
    lazy = Const()
    tag = Const()

    class T:
        a = 1
        b = 3 |const
        c: int
        d: int = 2
        e: int = 4 |lazy
        f: ClassVar[int]
        g: ClassVar[int] = 6
        h: ClassVar[int] = 7 |const

        with TAG('x') |const |lazy:
            a1 = 1
            b1 = 3 |const
            c1: int
            d1: int = 2
            e1: int = 4 |lazy
            f1: ClassVar[int]
            g1: ClassVar[int] = 6
            h1: ClassVar[int] = 7 |const
            i1: int = 8 |tag('error')         # error: already under tag

        with OPTIONS |tag('test') |const:
            i = 8
            j = 9 |-const

    print(dir(T()))
