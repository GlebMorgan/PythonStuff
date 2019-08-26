from __future__ import annotations as annotations_feature

from collections import defaultdict
from functools import partial
from itertools import starmap
from operator import setitem
from typing import Any, ClassVar, Union, Dict

from Utils import auto_repr, Null, Logger, attachItem, formatDict, legacy
from orderedset import OrderedSet

__options__ = 'tag', 'const', 'lazy'

__all__ = 'Attr', 'TAG', 'OPTIONS', *__options__

log = Logger('Classtools')
log.setLevel('INFO')


# TODO: check for duplicating tags inside TAG SectionTitle object (store list of used tags and compare on __call__())

# GENERAL CONFIG:

# Add option definition objects (those used with '|option' syntax) to class dict
# to make their names available (only) inside class body, thus avoiding extra imports
# These objects will be removed from class dict as soon as class statement is fully executed
INJECT_OPTIONS = False

# CONSIDER: always deny non-annotated attrs for now
# Raise error if non-function attr is declared without annotation,
# else — treat non-annotated attrs as class attrs (do not process them with class tools routine)
# Note: non-annotated attrs inside SECTION blocks are not allowed
DENY_BARE_ATTRS = False


class ClasstoolsError(RuntimeError):
    """ Error: class is used incorrectly by higher-level code """


# TODO: disallow attribute setting from inside class body, but allow inside this module
@legacy
def setupMode(function):
    def setupModeWrapper(*args, **kwargs):
        Option.__setattr__ = object.__setattr__
        result = function(*args, **kwargs)
        Option.__setattr__ = Option.denyAttrAccess
        return result
    return setupModeWrapper


class AnnotationSpy(dict):
    """
        ... TODO
    """

    def __init__(self, metaclass):
        self.owner: ClasstoolsType = metaclass
        super().__init__()

    def __setitem__(self, attrname, annotation):
        log.debug(f'[__annotations__][{attrname}] ◄—— {annotation}')

        # ▼ Put annotation on its place
        super().__setitem__(attrname, annotation)

        default = None if self.owner.autoinit else Null

        # ▼ If slots are injected, remove conflicting class variable
        if self.owner.injectSlots:
            value = self.owner.clsdict.pop(attrname, default)
        else:
            value = self.owner.clsdict.get(attrname, default)

        # ▼ Skip dunder attrs
        if attrname.startswith('__') and attrname.endswith('__'):
            # TODO
            return

        # ▼ Skip and remove ignored attrs from class dict
        if value is Attr.IGNORE:
            del self.owner.clsdict[attrname]
            return

        if isinstance(value, Attr):
            attr = value
            attr.name = attrname
            if not self.owner.injectSlots:
                # ▼ Replace class variable with default value
                self.owner.clsdict[attrname] = attr.default
        # ▼ Create Attr() even if variable had no value assigned
        else: attr = Attr(attrname, value)

        # CONSIDER: ▼ parse annotations correctly (use module or smth)
        # ▼ Set attr as classvar, if that's the case
        if annotation.startswith('ClassVar'):
            attr.classvar = True
            annotation = annotation.strip('ClassVar')
            # ▼ NOTE: if annotation was just 'ClassVar' with no generics, type will be ''
            if annotation.startswith('[') and annotation.endswith(']'):
                annotation = annotation[1:-1]
        else:
            attr.classvar = False

        # ▼ Apply type with removed ClassVar, if that's the case
        attr.type = annotation

        # ▼ Set options which was not defined earlier by option definition objects
        for option in (__options__):
            if not hasattr(attr, option):
                setattr(attr, option, self.owner.currentOptions[option])

        # NOTE: 'None' is a valid tag key (to allow for an easy sample of all non-tagged attrs)
        self.owner.tags[attr.tag].add(attrname)
        self.owner.attrs[attrname] = attr


    def setitem(self, key, value):
        """ __setitem__ for internal use """
        return super().__setitem__(key, value)


class Attr:
    """
        Attrs objects are created from all ANNOTATED variables defined inside class body
            Exceptions are:
                • __service_var__ = smth  – dunder variables
                • var: type = Attr.ignore – explicitly marked to be ignored
            ...
        ... TODO
    """

    # ▼ ' ... , *__options__' is not used here because PyCharm fails to resolve attributes this way round
    __slots__ = 'name', 'default', 'type', 'classvar', 'tag', 'const', 'lazy'

    IGNORE = type("IGNOREMARKER", (), {})()

    def __init__(self, name=Null, value=Null, vartype=Null):
        if name is not Null: self.name = name
        self.default = value
        self.type = vartype

    def __str__(self):
        return f"Attr '{self.name}' [{self.default}] <{self.type}>" \
               f"{' C'*self.classvar}{f' ⚑{self.tag}'*(self.tag is not None)}" \
               f"{' 🔒'*self.const}{' 🕓'*(self.lazy is not False)}"

    def __repr__(self): return auto_repr(self, self.name)

    def __neg__(self): return self.IGNORE

    @property
    def options(self): return {name: getattr(self, name) for name in __options__}

    @classmethod
    def ignore(cls): return cls.IGNORE


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
        TODO: add option icons to documentation
    """

    __slots__ = 'name', 'default', 'flag', 'incompatibles', 'value'

    def __init__(self, name, *, default, flag: Union[bool, None], hates=None):
        self.name = name
        self.default = default  # default value, <bool> if .type == True
        self.flag = flag  # require, allow or deny argument
        # ▼ TODO: Option.incompatibles (on demand)
        self.incompatibles = hates  # option(s) that cannot be applied before current one
        # ▼ Stores current value (changed by modifiers, reset after applying to attr)
        self.value = Null

    def __ror__(self, value):  # CONSIDER: rename value to smth more suitable

        # ▼ Set .value to appropriate default if option used with no modifiers
        if self.value is Null:
            if self.flag is False:
                raise ClasstoolsError(f"Option '{self.name}' requires an argument")
            else:
                self.value = True if self.flag is True else self.default

        # ▼ If applied to Section, change section-common defaults via Section.classdict
        if isinstance(value, Section):
            value.metaclass.currentOptions[self.name] = self.value

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
            raise ClasstoolsError(f"Option {self.name} is not callable")
        # TODO: check argument type
        self.value = arg
        return self

    def __neg__(self):
        # NOTE: disabling an option with assigned argument will reset it
        self.value = False if self.flag is True else None
        return self

    def __repr__(self): return auto_repr(self, f'{self.name}')

    def denyAttrAccess(self, name, value):
        raise AttributeError(f"'{self.name}' object is not intended to use beyond documented syntax")


class ClasstoolsType(type):  # CONSIDER: Classtools
    """ TODO: ClasstoolsType docstring
        Variables defined without annotations are not tagged
        SECTION without any attrs inside is not created
        Tag names are case-insensitive
        Member methods (class is direct parent in __qualname__) are not tagged,
            even if they are assigned not using 'def'
        • slots ——► auto inject slots from __attrs__
        • init ——► auto-initialize all __attrs__ defaults to 'None'
    """

    # __tags__ = {}  # FIXME: move this to cls.__new__ !
    # __attrs__ = {}  # FIXME: move this to cls.__new__ !

    currentOptions: Dict[str, Any] = {}
    clsdict = {}


    @classmethod
    def __prepare__(metacls, clsname, bases, enable=True, slots=False, init=False):
        if enable is False: return {}

        metacls.injectSlots = slots
        metacls.autoinit = init

        metacls.tags: defaultdict = metacls.clsdict.setdefault('__tags__', defaultdict(OrderedSet))
        metacls.attrs: dict = metacls.clsdict.setdefault('__attrs__', {})
        metacls.annotations: dict = metacls.clsdict.setdefault('__annotations__', AnnotationSpy(metacls))

        # ▼ Initialize options
        metacls.resetOptions()

        if INJECT_OPTIONS:  # TESTME
            # ▼ TODO: adjustable names below
            metacls.clsdict['tag'] = tag
            metacls.clsdict['const'] = const
            metacls.clsdict['lazy'] = lazy

        return metacls.clsdict

    def __new__(metacls, clsname, bases, clsdict: dict, **kwargs):

        newClass = super().__new__(metacls, clsname, bases, clsdict)

        # ▼ Use tags and attrs that are already in clsdict if no parents found
        if hasattr(metacls, 'clsdict') and bases:
            newClass.__tags__ = metacls.mergeTags(bases, metacls.tags)
            newClass.__attrs__ = metacls.mergeParentDicts(bases, '__attrs__', metacls.attrs)

        # ▼ Verify no explicit/implicit Attr() was assigned to non-annotated variable
        for attr, value in clsdict.items():
            if isinstance(value, Attr):
                raise ClasstoolsError(f"Attr '{attr}' is used without type annotation!")

        # CONSIDER: defaults for slots could be taken from __attrs__

        # ▼ Convert annotation spy to normal dict
        newClass.__annotations__ = dict(metacls.annotations)

        return newClass


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

    @classmethod
    def resetOptions(metacls):
        metacls.currentOptions.update({option.name: option.default for option in (tag, const, lazy)})
        # CONSIDER: unresolved attr .currentOptions? Why?


class Section:

    metaclass = ClasstoolsType

    def __init__(self, sectionType: str = None):
        self.type = sectionType

    def __enter__(self): pass

    def __exit__(self, *args):
        self.metaclass.resetOptions()

    def __call__(self, *args):
        if self.type == 'tagger':
            if len(args) != 1:
                raise TypeError(f"Section '{self.type}' requires single argument: 'tag'")
            self.metaclass.currentOptions['tag'] = args[0]
        else: raise ClasstoolsError("Section does not support arguments")
        return self


# TODO: Move all options to options.py, define __all__ there and import options as 'from options import *'
tag = Option('tag', default=None, flag=False)
const = Option('const', default=False, flag=True)
lazy = Option('lazy', default=False, flag=False)

# TODO: review this in the end
# If adding new option, add it to:
#     1) Option() objects above
#     2) __options__ global variable
#     3) Attr.__slots__
#     4) Attr.__str__ option icons
#     6) ClassDictProxy.resetOptions()
#     7) ClassDict name injections in ClasstoolsType.__prepare__
#     8) Option __doc__

OPTIONS = Section()
TAG = Section('tagger')



# CONSIDER: ALWAYS CREATE ATTRS FROM ANNOTATED VARIABLES DEFINED IN CLASS BODY, NEVER USE ATTR THERE INSTEAD



if __name__ == '__main__':


    class A(metaclass=ClasstoolsType):

        a0: str = -Attr()
        a: int = 4 |tag("test") |lazy('set_a') |const
        c: Any = 3

        with OPTIONS |lazy('tag_setter'):
            e: str
            f: int = 0 |const

        with TAG('tag') |lazy('tag_setter'):
            b: str = 'loool'
            d: int = 0 |const

    print(formatDict(A.__attrs__))
    print(formatDict(A.__tags__))
    print(formatDict(A.__dict__))
    print(A().a)
    print(A().b)
    print(A().c)
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
