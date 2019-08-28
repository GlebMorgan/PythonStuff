from __future__ import annotations as annotations_feature

from collections import defaultdict
from functools import partial
from itertools import starmap
from operator import setitem
from re import findall
from typing import Any, ClassVar, Union, Dict

from Utils import auto_repr, Null, Logger, attachItem, formatDict, legacy
from orderedset import OrderedSet

__options__ = 'tag', 'const', 'lazy'

__all__ = 'Attr', 'TAG', 'OPTIONS', *__options__

log = Logger('Classtools')
log.setLevel('INFO')


# TODO: check for duplicating tags inside TAG SectionTitle object (store list of used tags and compare on __call__())

# GENERAL CONFIG:

ATTR_ANNOTATION = 'attr'
EMPTY_ANNOTATION = ''

# ▼ Allow usage of ATTR_ANNOTATION inside generic structures in type annotations (e.g. ClassVar[attr])
ALLOW_ATTR_ANNOTATIONS_INSIDE_GENERICS = False

# ▼ Allow __dunder__ names to be processed by Classtools machinery and annotated with ATTR_ANNOTATION
ALLOW_DUNDER_ATTRS = False

# ▼ Create class variable for each attr with default value assigned.
#   Else, instance variable will be assigned with its default only if auto init option is set
#   Note: slots option overrides this config option, slots injection forbids class variables with same name
STORE_DEFAULTS = True

# ▼ Add option definition objects (those used with '|option' syntax) to class dict
#   to make their names available (only) inside class body, thus avoiding extra imports
#   These objects will be removed from class dict as soon as class statement is fully executed
INJECT_OPTIONS = False

# CONSIDER: always deny non-annotated attrs for now
# ▼ Allow non-function attr is declared without annotation.
#   Else — treat non-annotated attrs as class attrs (do not process them with class tools routine)
ALLOW_BARE_ATTRS = True


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

        clsdict = self.owner.clsdict
        default = None if self.owner.autoInit else Null
        var = clsdict.get(attrname, default)

        # ▼ Skip dunder attrs, if configured accordingly
        if not ALLOW_DUNDER_ATTRS:
            if attrname.startswith('__') and attrname.endswith('__'):
                # ▼ CONSIDER: check not only for Attr, but for all other service Classtools classes
                #             (may use kind of AbcMeta here for isinstance check): here + non-annotated attrs check
                if isinstance(var, Attr) or annotation == ATTR_ANNOTATION:
                    raise ClasstoolsError(f"Classtools is configured to deny __dunder__ Attr()s")
                return super().__setitem__(attrname, annotation)

        # ▼ Skip and remove ignored attrs from class dict
        if var is Attr.IGNORED:
            del clsdict[attrname]
            if annotation == ATTR_ANNOTATION:
                raise ClasstoolsError(f"Cannot use '{ATTR_ANNOTATION}' annotation with ignored attrs")
            return super().__setitem__(attrname, annotation)

        # ▼ Convert to Attr if not already
        if isinstance(var, Attr): var.name = attrname
        else: var = Attr(attrname, var)

        # ▼ Do not allow ATTR_ANNOTATION in nested structures, if configured accordingly
        if not ALLOW_ATTR_ANNOTATIONS_INSIDE_GENERICS:
            if len(findall(rf'\W({ATTR_ANNOTATION})\W', annotation)) > 0:
                raise ClasstoolsError(f"Annotation '{ATTR_ANNOTATION}' is reserved "
                                      f"and cannot be used inside generic structures to avoid confusion")

        # ▼ Put annotation on its place, skip ATTR_ANNOTATION
        if annotation == ATTR_ANNOTATION: annotation = EMPTY_ANNOTATION
        else: super().__setitem__(attrname, annotation)

        # CONSIDER: ▼ parse generic annotations correctly (use re, dedicated module or smth)
        # ▼ Set attr as classvar and strip annotation, if that's the case
        if annotation.startswith('ClassVar'):
            var.classvar = True
            annotation = annotation.strip('ClassVar')
            if annotation.startswith('[') and annotation.endswith(']'):
                annotation = annotation[1:-1]
            elif annotation == '':
                annotation = EMPTY_ANNOTATION
            else:
                raise ClasstoolsError(f"Invalid ClassVar annotation: ClassVar{annotation}")
        else:
            var.classvar = False

        # ▼ Set .type with removed 'ClassVar' and 'attr'
        var.type = annotation

        if var.default is Null or (var.classvar is False and (self.owner.injectSlots or not STORE_DEFAULTS)):
            if attrname in clsdict: del clsdict[attrname]
        else:
            clsdict[attrname] = var.default

        # NOTE: Alternative version
        # if var.default is Null \
        # or (self.owner.injectSlots and var.classvar is False) \
        # or (not STORE_DEFAULTS and var.classvar is False):

        # ▼ Set options which was not defined earlier by option definition objects / Attr kwargs
        for option in (__options__):
            if not hasattr(var, option):
                setattr(var, option, self.owner.currentOptions[option])

        # NOTE: 'None' is a valid tag key (to allow for an easy sample of all non-tagged attrs)
        self.owner.tags[var.tag].add(attrname)
        self.owner.attrs[attrname] = var

    def setitem(self, key, value):
        """ __setitem__ for internal use """
        return super().__setitem__(key, value)


class Attr:
    """
        Attrs objects are created from all ANNOTATED variables defined inside class body
            Exceptions are:
                • __service_var__ = smth  – dunder variables
                • var: type = Attr.ignore() – explicitly marked to be ignored
            ...
        ... TODO
    """

    # ▼ ' ... , *__options__' is not used here because PyCharm fails to resolve attributes this way round
    __slots__ = 'name', 'default', 'type', 'classvar', 'tag', 'const', 'lazy'

    IGNORED = type("ATTR_IGNORE_MARKER", (), dict(__slots__=()))()

    def __new__(cls, varname=Null, value=Null, vartype=Null, *options):
        this = super().__new__(cls)
        this.name = varname
        this.default = value
        this.type = vartype

        # TODO: handle options

        return this

    def __str__(self):
        return f"Attr '{self.name}' [{self.default}] <{self.type}>" \
               f"{' C'*self.classvar}{f' ⚑{self.tag}'*(self.tag is not None)}" \
               f"{' 🔒'*self.const}{' 🕓'*(self.lazy is not False)}"

    def __repr__(self): return auto_repr(self, self.name)

    def __neg__(self): return self.IGNORED

    @property
    def options(self): return {name: getattr(self, name) for name in __options__}

    @classmethod
    def ignore(cls): return cls.IGNORED


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

    def __ror__(self, other):

        # ▼ Set .value to appropriate default if option used with no modifiers
        if self.value is Null:
            if self.flag is False:
                raise ClasstoolsError(f"Option '{self.name}' requires an argument")
            else:
                self.value = True if self.flag is True else self.default

        # ▼ If applied to Section, change section-common defaults via Section.classdict
        if isinstance(other, Section):
            other.owner.currentOptions[self.name] = self.value

        # ▼ Else, convert 'other' to Attr() and apply option to it
        else:
            if not isinstance(other, Attr):
                other = Attr(value=other)
            setattr(other, self.name, self.value)

        # ▼ Reset .value if altered by modifiers
        self.value = Null
        return other

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

    currentOptions: Dict[str, Any]
    clsdict: dict
    tags: defaultdict
    attrs: dict
    annotations: dict

    @classmethod
    def __prepare__(metacls, clsname, bases, enable=True, slots=False, init=False):
        if enable is False: return {}

        metacls.injectSlots = slots
        metacls.autoInit = init  # CONSIDER: autoInit value option (opportunity to supply argument)

        metacls.clsdict = {}
        metacls.tags: defaultdict = metacls.clsdict.setdefault('__tags__', defaultdict(OrderedSet))
        metacls.attrs: dict = metacls.clsdict.setdefault('__attrs__', {})
        metacls.annotations: dict = metacls.clsdict.setdefault('__annotations__', AnnotationSpy(metacls))

        metacls.currentOptions: Dict[str, Any] = {}

        # ▼ Initialize options
        metacls.resetOptions()

        if INJECT_OPTIONS:  # TESTME
            # ▼ TODO: adjustable names below
            metacls.clsdict['attr'] = attr
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

        newClass.__slots__ = ()

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

    owner = ClasstoolsType

    def __init__(self, sectionType: str = None):
        self.type = sectionType

    def __enter__(self): pass

    def __exit__(self, *args):
        self.owner.resetOptions()

    def __call__(self, *args):
        if self.type == 'tagger':
            if len(args) != 1:
                raise TypeError(f"Section '{self.type}' requires single argument: 'tag'")
            self.owner.currentOptions[tag.name] = args[0]
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

attr = Attr()
OPTIONS = Section()
TAG = Section('tagger')






def test_concise_tagging_basic():
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

def test_concise_tagging_concept():

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
        c: int = attr |const
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

        with OPTIONS() |tag('test') |const:
            i = 8
            j = 9 |-const

    print(dir(T()))
    print(T.__annotations__)

def test_all_types():

    class AllTypes:
        a1 = any                    # __class__.a (not processed by classtools)
        __dunder1__ = any

        h1 = Attr()   # # # # # # # # ERROR (Attr)
        h2 = TAG, OPTIONS   # # # # # ERROR (Attr)
        h3 = attr   # # # # # # # # # ERROR (Attr)
        h4 = lazy, tag, const   # # # ERROR (Attr)

        b1: int                     # Attr(Null/None) + int
        b2: int = Attr()

        c1: attr                    # Attr(Null/None)
        c2: attr = Attr()

        d1: int = any               # Attr(any) + int + __class__.d = any
        d2: int = Attr(any)

        e1: attr = any              # Attr(any) + <no_ann> + __class__.e = any
        e2: attr = Attr(any)

        g1: int = Null              # ? — like Attr()
        g2: attr = Null

        i1: int = Attr.IGNORED      # (not processed by classtools) + int/ClassVar[int]
        i2: int = Attr().IGNORED
        i3: ClassVar[int] = -Attr()
        __dunder7__: int = Attr().ignore()
        __dunder8__: ClassVar[int] = Attr.ignore()

        k1: attr = Attr.ignore()  # # ERROR (attr)
        k2: ClassVar[attr]  # # # # # ERROR (attr)

        f1: ClassVar                # Attr(Null/None) + <no_ann> + .classvar + __class__.j = /None/
        f2: ClassVar = Attr()

        j1: ClassVar = any          # Attr(any) + <no_ann> + .classvar + __class__.k = any
        j3: ClassVar = Attr(any)

        m1: ClassVar[int] = any     # Attr(any) + int + .classvar + __class__.l = any
        m2: ClassVar[int] = Attr(any)

        __dunder2__: attr   # # # # # # ERROR (dunder)
        __dunder6__: int = Attr(any)  # ERROR (dunder)

        __dunder3__: int            # __class__.__dunder__ = ... (not processed by classtools, just like IGNORED) + int
        __dunder4__: int = any
        __dunder5__: ClassVar[int] = any

    test = AllTypes()





if __name__ == '__main__':
    test_concise_tagging_basic()
    # test_all_types()

