from __future__ import annotations as annotations_feature

from collections import defaultdict
from functools import partial
from itertools import starmap, chain
from operator import setitem
from re import findall
from typing import Any, ClassVar, Union, Dict, DefaultDict

from Utils import auto_repr, Null, Logger, attachItem, formatDict
from orderedset import OrderedSet

__options__ = 'tag', 'init', 'const', 'lazy'

__all__ = 'attr', 'TAG', 'OPTIONS', *__options__

log = Logger('Classtools')
log.setLevel('DEBUG')

# ——————————————————————————————————————————————————— KNOWN ISSUES ——————————————————————————————————————————————————— #

# FIXME: |const breaks pickling

# FIXME: options state is saved until ror is called, no control over isolated option config and its application to attr

# —————————————————————————————————————————————————————— TODOs ——————————————————————————————————————————————————————— #

# ✓ Disallow Option attribute setting from inside class body, but allow inside this module

# ✓ Validate option argument when implementing necessary adjustments to attr (i.e. when using that argument)

# ✓ Attr(default, **options) attr initialization syntax

# ✓ Section['arg'] syntax

# ✓ Inject slots, const and lazy implementations

# TODO: Document all this stuff!

# TODO: Metaclass options setting through same |option syntax

# ———————————————————————————————————————————————————— ToCONSIDER ———————————————————————————————————————————————————— #

# ✓ Factory option: is it needed? ——► stick with searching for .copy attr

# CONSIDER: Rename __tags__ ——► _tags_ (may break some dunder checks, needs investigation)

# CONSIDER: Create a __owner__ variable in metaclass referencing to outer class, in which current class is defined;
#           this way inner classes and variables may be visible in child class, which is always very convenient

# CONSIDER: Implement lookups diving into mro classes when searching for __tags__ and __attrs__ to initialize slots
#           just like normal attrs lookup is performed instead of creating cumulative dicts in each class

# CONSIDER: metaclass options are accessible from instance class — eliminate this somehow

# ▼ CONSIDER: check non-annotated attrs not only for being Attr instances, but for all other service Classtools classes
#             (may use kind of AbcMeta here for isinstance check): here + non-annotated attrs check

# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #


# GENERAL CONFIG:

ATTR_ANNOTATION = 'attr'
EMPTY_ANNOTATION = ''

# ▼ Allow usage of ATTR_ANNOTATION marker in type annotations (+ inside generic structures e.g. ClassVar[attr])
ALLOW_ATTR_ANNOTATIONS = False

# ▼ Allow __dunder__ names to be processed by Classtools machinery and be annotated with ATTR_ANNOTATION
ALLOW_DUNDER_ATTRS = False

# ▼ Create class variable for each attr with default value assigned
#   Else, instance variable will be assigned with its default only if Classtools |autoinit option is set
#   Note: Classtools |slots option overrides STORE_DEFAULTS config option as slots injection will cause name collisions
STORE_DEFAULTS = True

# ▼ Add Attr option definition objects (those used with '|option' syntax) to created class's dict
#   It will make their names available (only) inside class body, thus avoiding extra imports
#   These objects will be removed from class dict as soon as class statement is fully executed
INJECT_OPTIONS = False

# TODO: comment to 'ALLOW_SERVICE_OBJECTS'
ALLOW_SERVICE_OBJECTS = False

# NOTE: Option is not used — always denying non-annotated Attr()s for now
# ▼ Allow non-function attr is declared without annotation.
#   Else — treat non-annotated attrs as class attrs (do not process them with class tools routine)
ALLOW_BARE_ATTRS = True


class ClasstoolsError(RuntimeError):
    """ Error: Classtools functionality is used incorrectly when defining class """


class GetterError(RuntimeError):
    """ Error: Lazy attribute getter function failed to compute attr value """


class AnnotationSpy(dict):
    """
        Dict-like class that intercepts annotation assignments and processes all newly defined
            annotated class variables with __attrs__ creation machinery
        General conceptual mechanics:
            1. variable value is converted to Attr(), if not already
            2. attr.default is auto-assigned with fallback default, if provided via |autoinit
            3. considering that default value is provided, it is stored in class dict if:
                • attr is marked as ClassVar
                • both Classtools |slots option is False and STORE_DEFAULTS config option is True
            4. attr options that have not been set are assigned with their respective defaults
            5. attr is added to __tags__ and __slots__ dicts
        Pay attention:
            • Dunder attrs are ignored (left alone as class attrs), if ALLOW_DUNDER_ATTRS config option is False
            • Attr.IGNORED attrs are completely removed from class as if there were only type-annotated name
            • ClassVar annotation is not included into attr.type, annotations is left unchanged
            • If annotated with ATTR_ANNOTATION: name is not added to annotations, attr.type is left empty
            • Annotations must be strings, error is raised otherwise
    """

    def __init__(self, metaclass):
        self.owner: ClasstoolsType = metaclass
        super().__init__()

    def __setitem__(self, attrname, annotation):
        # ▼ Value is readily Null, if autoInit is disabled
        default = self.owner.autoInit

        clsdict = self.owner.clsdict
        var = clsdict.get(attrname, default)

        # ▼ Deny non-string annotations
        if not isinstance(annotation, str):
            raise ClasstoolsError(f"Attr '{attrname}': annotation must be a string; "
                                  f"use quotes or 'from __future__ import annotations'")

        # ▼ Skip dunder attrs, if configured accordingly
        if not ALLOW_DUNDER_ATTRS:
            if attrname.startswith('__') and attrname.endswith('__'):
                return super().__setitem__(attrname, annotation)

        # ▼ Skip and remove ignored attrs from class dict
        if var is Attr.IGNORED:
            del clsdict[attrname]
            if annotation == ATTR_ANNOTATION:
                raise ClasstoolsError(f"Attr '{attrname}': cannot use '{ATTR_ANNOTATION}' "
                                      f"annotation with ignored attrs")
            return super().__setitem__(attrname, annotation)

        # ▼ Convert to Attr if not already
        if isinstance(var, Attr): var.name = attrname
        else: var = Attr(attrname, var)

        # ▼ Put annotation on its place, skip ATTR_ANNOTATION
        if annotation == ATTR_ANNOTATION: annotation = EMPTY_ANNOTATION
        else: super().__setitem__(attrname, annotation)

        # CONSIDER: ▼ Parse generic annotations correctly (use re, dedicated module or smth)
        # ▼ Set attr as classvar and strip annotation, if that's the case
        if annotation.startswith('ClassVar'):
            var.classvar = True
            annotation = annotation.strip('ClassVar')
            if annotation.startswith('[') and annotation.endswith(']'):
                annotation = annotation[1:-1]
            elif annotation == '':
                annotation = EMPTY_ANNOTATION
            else:
                raise ClasstoolsError(f"Attr '{attrname}': invalid ClassVar annotation 'ClassVar{annotation}'")
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
        Mutable defaults must provide .copy() method (no-args) that is used to initialize object attrs;
            otherwise all objects will refer to one-and-the-same object stored in __attrs__.default
        ... TODO: Attr docstring
        Repr icons:  # CONSIDER: change to ascii because of console does not support utf-8 and monospaced font breaks
            Attr      instance attr
            ClassAttr class attr
            [...]     default value
            <...>     declared type
            ⚑...      tag
            ⛔        NO init
            🔒        const
            🕓        lazy
    """

    # ▼ ' ... , *__options__' is not used here because PyCharm fails to resolve attributes this way round
    __slots__ = 'name', 'default', 'type', 'classvar', 'tag', 'init', 'const', 'lazy'

    IGNORED = type("ATTR_IGNORE_MARKER", (), dict(__slots__=()))()

    def __init__(self, varname=Null, value=Null, vartype=Null, **options):
        self.name = varname
        self.default = value
        self.type = vartype
        for name, value in options.items():
            setattr(self, name, value)

    def __str__(self):
        return f"{'Class' if self.classvar else ''}Attr '{self.name}' [{self.default}] <{self.type or ' '}>" \
               f"{f' ⚑{self.tag}'*(self.tag is not None)}{' ⛔'*(not self.init)}{' 🔒'*self.const}" \
               f"{' 🕓'*(self.lazy is not False)}"

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
                            (Null will be used as a value in this case)
        ... TODO: Option docstring
    """

    __slots__ = 'name', 'default', 'flag', 'incompatibles'

    # ▼ Stores current value (changed by modifiers, reset after applying to attr)
    value = Null

    class setupMode:
        """ Decorator that allows __setattr__ inside the decorated method """
        def __init__(self, method):
            self.method = method
        def __get__(self, instance, owner):
            self.instance = instance
            return self
        def __call__(self, *args, **kwargs):
            self.instance.__class__.__setattr__ = super(self.instance.__class__, self.instance).__class__.__setattr__
            self.method(self.instance, *args, **kwargs)
            self.instance.__class__.__setattr__ = self.instance.__class__.denyAttrAccess

    @setupMode
    def __init__(self, name, *, default, flag: Union[bool, None], hates=None):
        self.name = name
        self.default = default  # default value, <bool> if .flag == True
        self.flag = flag  # require/allow/deny argument
        # ▼ TODO: Option.incompatibles (on demand)
        self.incompatibles = hates  # option(s) that cannot be applied before current one

    def __ror__(self, other):

        # ▼ Set .value to appropriate default if option used with no modifiers
        if self.value is Null:
            if self.flag is False:
                raise ClasstoolsError(f"Option '{self.name}' requires an argument")
            elif self.flag is True:
                self.__class__.value = True
            # else: value remains Null

        # ▼ If applied to Section, change section-common defaults via Section.classdict
        if isinstance(other, Section):
            other.owner.currentOptions[self.name] = self.value

        # ▼ Else, convert 'other' to Attr() and apply option to it
        else:
            if not isinstance(other, Attr):
                other = Attr(value=other)
            if hasattr(other, self.name):
                raise ClasstoolsError(f"Duplicate option '{self.name}'; "
                                      f"was already set to {getattr(other, self.name)}")
            setattr(other, self.name, self.value)

        # ▼ Reset .value if altered by modifiers
        self.__class__.value = Null
        return other

    def __call__(self, arg):
        if self.flag is True:
            raise ClasstoolsError(f"Option '{self.name}' is not callable")
        self.__class__.value = arg
        return self

    def __neg__(self):
        # NOTE: disabling an option with assigned argument will reset it
        self.__class__.value = False if self.flag is True else None
        return self

    def __repr__(self): return auto_repr(self, self.name)

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

    __tags__: DefaultDict[str, OrderedSet]
    __attrs__: Dict[str, Attr]

    enabled: bool

    currentOptions: Dict[str, Any]
    clsdict: Dict[str, Any]
    tags: DefaultDict[str, OrderedSet]
    attrs: Dict[str, Attr]
    annotations: Dict[str, str]

    @classmethod
    def __prepare__(metacls, clsname, bases, enable=True, slots=False, autoinit=Null):

        metacls.enabled = enable
        if enable is False: return {}

        metacls.injectSlots = slots
        metacls.autoInit = autoinit

        metacls.clsdict = {}
        metacls.tags = metacls.clsdict.setdefault('__tags__', defaultdict(OrderedSet))
        metacls.attrs = metacls.clsdict.setdefault('__attrs__', {})
        metacls.annotations = metacls.clsdict.setdefault('__annotations__', AnnotationSpy(metacls))

        metacls.currentOptions: Dict[str, Any] = {}

        # ▼ Initialize options
        metacls.resetOptions()

        if INJECT_OPTIONS:  # TESTME
            # ▼ CONSIDER: adjustable names below
            metacls.clsdict['attr'] = attr
            metacls.clsdict['tag'] = tag
            metacls.clsdict['init'] = init
            metacls.clsdict['const'] = const
            metacls.clsdict['lazy'] = lazy

        return metacls.clsdict

    def __new__(metacls, clsname, bases, clsdict: dict, **kwargs):

        if metacls.enabled is False:
            return super().__new__(metacls, clsname, bases, clsdict)

        # ▼ Use tags and attrs that are already in clsdict if no parents found
        if hasattr(metacls, 'clsdict') and bases:
            clsdict['__tags__'] = metacls.mergeTags(bases, metacls.tags)
            clsdict['__attrs__'] = metacls.mergeParentDicts(bases, '__attrs__', metacls.attrs)

        # ▼ Deny explicit/implicit Attr()s assignments to non-annotated variables
        for attrname, value in clsdict.items():
            if isinstance(value, Attr):
                raise ClasstoolsError(f"Attr '{attrname}' is used without type annotation!")
            if isinstance(value, Attr.IGNORED.__class__):
                raise ClasstoolsError(f"Attr.IGNORED marker could be used only with annotated variables")

        # ▼ Deny ATTR_ANNOTATION in annotations and generic structures, if configured accordingly
        if not ALLOW_ATTR_ANNOTATIONS:
            if ATTR_ANNOTATION in metacls.annotations:
                raise ClasstoolsError(f"Classtools is configured to deny '{ATTR_ANNOTATION}' annotations")
            for attrname, annotation in metacls.annotations.items():
                if len(findall(rf'\W({ATTR_ANNOTATION})\W', annotation)) > 0:
                    raise ClasstoolsError(f"Attr '{attrname}: {annotation}': Classtools is configured to deny "
                                          f"'{ATTR_ANNOTATION}' annotations inside generic structures")

        # ▼ Deny Classtools service objects assignments to class variables or attrs, if configured accordingly
        if not ALLOW_SERVICE_OBJECTS:
            for value in chain(clsdict.values(), (attrobj.default for attrobj in metacls.attrs.values())):
                if isinstance(value, (Section, Option)):
                    raise ClasstoolsError(f"Classtools is configured to deny "
                                          f"'{value.__class__.__name__}' objects in user classes")

        # ▼ Check for cls.init() argument names and attr names conflicts
        # CONSIDER: do I actually need this check?
        # if 'init' in clsdict and isinstance(clsdict['init'], Callable):
        #     if any(varname in metacls.attrs for varname in clsdict['init'].__code__.co_varnames):
        #         raise ClasstoolsError(f"{clsname}.init() argument names "
        #                               f"conflict with {clsname} attr names")

        # ▼ Inject slots from all non-classvar attrs, if configured accordingly
        if metacls.injectSlots:
            clsdict['__slots__'] = tuple(attrobj.name for attrobj in metacls.attrs.values() if not attrobj.classvar)

        # ▼ Generate __init__() function, 'init()' is used to further initialize object
        clsdict['__init__'] = metacls.__init_attrs__

        # ▼ Convert annotation spy to normal dict
        clsdict['__annotations__'] = dict(metacls.annotations)

        return super().__new__(metacls, clsname, bases, clsdict)

    def __init_attrs__(attr, *a, **kw):
        """ This is gonna be new class's __init__ method """

        attrsls = attr.__class__
        log.debug(f"__init_attrs__: self={attrsls.__name__}, args={a}, kwargs={kw}")

        for name, currAttr in attr.__attrs__.items():
            if currAttr.classvar is True: continue

            # ▼ Get attr value from arguments or .default
            try:
                value = kw.pop(name)
            except KeyError:
                try: value = currAttr.default.copy()
                except AttributeError: value = currAttr.default
            else:
                if currAttr.init is False:
                    raise ClasstoolsError(f"Attr '{name}' is configured no-init")

            if currAttr.default is Null and currAttr.lazy is False:
                continue  # ◄ NOTE: attr is not initialized at all, options are ignored

            # ▼ Analyze options and modify value if necessary
            elif currAttr.lazy is not False:
                getter = currAttr.lazy
                if getter is Null: getter = f'get_{name}'
                if not isinstance(getter, str):
                    raise ClasstoolsError(f"Attr '{name}': invalid lazy attr getter "
                                          f"(expected <str>, got {type(getter)}")
                if not hasattr(attr, getter):
                    raise ClasstoolsError(f"Class '{attrsls.__name__}' does not have "
                                          f"getter method '{getter}' for '{name}' attr")
                if currAttr.const is True:
                    # noinspection PyArgumentList
                    setattr(attrsls, name, LazyConstDescriptor(value, getter))
                else:
                    setattr(attrsls, name, LazyDescriptor(value, getter))
            elif currAttr.const is True:
                setattr(attrsls, name, ConstDescriptor(value))
            else:
                setattr(attr, name, value)

        # CONSIDER: move configuration code in a separate function if it will take a lot of place
        # self.__class__._configureAttrs_()

        # ▼ TODO: handle arguments-related errors here
        if hasattr(attr, 'init'): attr.init(*a, **kw)

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
        metacls.currentOptions.update({option.name: option.default for option in (tag, init, const, lazy)})


class LazyDescriptor:
    """
        TODO: Descriptors docstrings
        If getter raises GetterError, default is returned (on current attr access)
    """

    __slots__ = 'value', 'default', 'getter'

    def __init__(self, value, getter):
        self.getter: str = getter
        self.default = value
        self.value = Null

    def __get__(self, instance, owner):
        # ▼ Access descriptor itself from class
        if instance is None: return self
        if self.value is Null:
            try: self.value = getattr(instance, self.getter)()
            except GetterError:
                if self.default is Null:
                    raise ClasstoolsError("Failed to fallback to .default as it is not provided")
                return self.default
        return self.value

    def __set__(self, instance, value):
        self.value = value

    # CONSIDER: __delete__ — ?


class ConstDescriptor:
    __slots__ = 'value'

    def __init__(self, value):
        self.value = value

    def __get__(self, instance, owner):
        # ▼ Access descriptor itself from class
        if instance is None: return self
        return self.value

    def __set__(self, instance, value):
        # ▼ Access descriptor itself from class
        if instance is None: return self
        raise AttributeError("Cannot change constant attr")


class LazyConstDescriptor:
    __slots__ = LazyDescriptor.__slots__
    __init__ = LazyDescriptor.__init__
    __get__ = LazyDescriptor.__get__
    __set__ = ConstDescriptor.__set__


class Section:
    """
        TODO: Section docstring
    """

    __slots__ = 'type'

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

    def __getitem__(self, *args):
        return self.__call__(*args)

    def __repr__(self): return auto_repr(self, self.type or '')


def classtools(cls):
    """ Just to shut down PyCharm code inspection considering __init__ arguments """
    return cls


# TODO: Move all options to options.py, define __all__ there and import options as 'from options import *'
tag = Option('tag', default=None, flag=False)
init = Option('init', default=True, flag=True)
const = Option('const', default=False, flag=True)
lazy = Option('lazy', default=False, flag=None)

# TODO: review this in the end
# If adding new option, add it to:
#     1) Option() objects above
#     2) __options__ global variable
#     3) Attr.__slots__
#     4) Attr.__str__ option icons
#     6) ClasstoolsType.resetOptions()
#     7) ClassDict name injections in ClasstoolsType.__prepare__
#     8) Option __doc__

attr = Attr()
OPTIONS = Section()
TAG = Section('tagger')







def test_pickle():
    B = ...  # SomeClass
    import pickle as p
    print(formatDict(B.__attrs__))
    print(B().d)
    pA = p.dumps(B(e_arg=88))
    print(pA)
    print(f"Unpickled same 'a' attr? - {p.loads(pA).a == B().a}")
    exit()


def test_concise_tagging_basic():

    @classtools
    class A(metaclass=ClasstoolsType, slots=True):

        a0: str = -Attr()
        a: int = 4 |tag("test") |lazy('set_a') |const
        c: Any = 3

        with OPTIONS |lazy('tag_setter'):
            e: attr
            f: int = Attr(0, const=True) |tag('classic')

        with TAG['tag'] |-init:
            b: str = 'loool' |init
            d: ClassVar[int] = 0 |const
            g: ClassVar[int] = 42 |lazy
            k: ClassVar[str] = 'clsvar'

        h: list = []

        def set_a(self): return 'a_value'

        def tag_setter(self): return 'tag_value'

        def get_g(self): return 33

        def init(self, e_arg=88):
            self.e = e_arg

    print(formatDict(A.__attrs__))
    print(formatDict(A.__tags__))
    print(formatDict(A.__dict__))
    print(hasattr(A(), '__dict__'))
    print(f".a = {A().a}")
    print(f".b = {A().b}")
    print(f".c = {A(c=9).c}")
    print(f".d = {A().d}")
    print(f".g = {A().g}")  # CONSIDER: why A().g does not raise AttributeError? g is not in __slots__!
    print(f".k = {A().k}")
    print(f".__slots__ = {A().__slots__}")
    print(f"Are ints equal? - {A().a is A().a}")
    print(f"Are lists equal? - {A().h is A().h}")
    print(f".e (with e_arg) = {A(e_arg=4).e}")
    print(f".e = {A().e}")


def test_inject_slots():
    class B(metaclass=ClasstoolsType, slots=True):
        a: attr = 7
        b: int = 0 |const |lazy('set_b')

    b = B()
    print(f"Has dict? {hasattr(b, '__dict__') and b.__dict__}")
    print(b.__slots__)

    class C(metaclass=ClasstoolsType, slots=True):

        a0: str = -Attr()
        a: int = 4 |tag("test") |lazy('set_a') |const
        c: Any = 3

        with OPTIONS |lazy('tag_setter'):
            e: attr
            f: int = Attr(0, const=True) |tag('Attr')

        with TAG['tag'] |lazy:
            b: str = 'loool'
            d: ClassVar[int] = 0 |const

    c = C()
    print(f"Has dict? {hasattr(c, '__dict__') and c.__dict__}")
    print(f"Has slots? {hasattr(c, '__slots__') and c.__slots__}")


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
    # test_inject_slots()
    test_concise_tagging_basic()
    # test_all_types()
    # test_pickle()

