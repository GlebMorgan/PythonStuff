from __future__ import annotations as annotations_feature

from collections import defaultdict
from functools import partial
from itertools import starmap, chain
from operator import setitem
from re import findall
from typing import Any, ClassVar, Union, Dict, DefaultDict

from Utils import auto_repr, Null, Logger, attachItem, formatDict, isDunder, legacy
from orderedset import OrderedSet

__options__ = 'tag', 'skip', 'const', 'lazy', 'kw'

__all__ = 'Classtools', 'Attr', 'attr', 'TAG', 'OPTIONS', *__options__

log = Logger('Classtools')
log.setLevel('DEBUG')

# ——————————————————————————————————————————————————— KNOWN ISSUES ——————————————————————————————————————————————————— #

# FIXME: pickle does not work

# FIXME: options state is saved until ror is called, no control over isolated option config and its application to attr

# —————————————————————————————————————————————————————— TODOs ——————————————————————————————————————————————————————— #

# ✓ Disallow Option attribute setting from inside class body, but allow inside this module

# ✓ Validate option argument when implementing necessary adjustments to attr (i.e. when using that argument)

# ✓ Attr(default, **options) attr initialization syntax

# ✓ Section['arg'] syntax

# ✓ Inject slots, const and lazy implementations

# TODO: Document all this stuff!

# ✓ Init injection disabling option

# TODO: Metaclass options setting through same |option syntax

# ✗ Change |lazy descriptor logic to this:
#           class SNPTest:
#               ''' Same name property test '''
#               @property
#               def b(self):
#                   try: return self.__dict__['b']
#                   except KeyError:
#                       print('computing result...')
#                       result = 43
#                       self.__dict__['b'] = result
#                       return result

# TODO: Way to define api/internal methods and fields (other than by naming conventions)

# TODO: remove OrderedSet dependency

# TODO: add |type option to check types

# ———————————————————————————————————————————————————— ToCONSIDER ———————————————————————————————————————————————————— #

# ✓ Factory option: is it needed? ——► stick with searching for .copy attr

# ✗ Rename __tags__ ——► _tags_ (may break some dunder checks, needs investigation)

# CONSIDER: Create a __owner__ variable in metaclass referencing to outer class, in which current class is defined;
#           this way inner classes and variables may be visible in child class, which is always very convenient

# CONSIDER: Implement lookups diving into mro classes when searching for __tags__ and __attrs__ to initialize slots
#           just like normal attrs lookup is performed instead of creating cumulative dicts in each class

# ✓ Metaclass options are accessible from instance class — eliminate this somehow

# CONSIDER: Check non-annotated attrs not only for being Attr instances, but for all other service Classtools classes
#           (may use kind of AbcMeta here for isinstance check): here + non-annotated attrs check

# CONSIDER: Add to __init__ only those args that are required for .init()
#           initSig = signature(clsdict['init']) ... bla bla bla

# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #


# GENERAL CONFIG:

ATTR_ANNOTATION = 'attr'
EMPTY_ANNOTATION = ''

# Allow usage of ATTR_ANNOTATION marker in type annotations (+ inside generic structures e.g. ClassVar[attr])
ALLOW_ATTR_ANNOTATIONS = False

# Allow __dunder__ names to be processed by Classtools machinery and be annotated with ATTR_ANNOTATION
ALLOW_DUNDER_ATTRS = False

# Create class variable for each attr with default value assigned
#   Else, instance variable will be assigned with its default only if Classtools |autoinit option is set
#   Note: Classtools |slots option overrides STORE_DEFAULTS config option as slots injection will cause name collisions
STORE_DEFAULTS = True

# Add Attr option definition objects (those used with '|option' syntax) to created class's dict
#   It will make their names available (only) inside class body, thus avoiding extra imports
#   These objects will be removed from class dict as soon as class statement is fully executed
INJECT_OPTIONS = False

# Allow Classtools service objects (Option, Section, etc.) to exist inside class as class variables or attrs defaults
ALLOW_SERVICE_OBJECTS = False

# NOTE: Option is not used — always denying non-annotated Attr()s for now
# Allow non-function attr is declared without annotation.
#   Else — treat non-annotated attrs as class attrs (do not process them with class tools routine)
ALLOW_BARE_ATTRS = True


class ClasstoolsError(RuntimeError):
    """ Error: Classtools functionality is used incorrectly when defining class """


class GetterError(RuntimeError):
    """ Error: Lazy attribute getter function failed to compute attr value """


class AnnotationSpy(dict):
    """
        Dict-like class that intercepts annotation assignments and processes all
            newly defined annotated class variables with __attrs__ creation machinery

        General conceptual mechanics of adding new attr to class:
            • Variable value is converted to Attr(), if not already
            • If fallback default is provided via |autoinit option,
                it is automatically assigned to attr.default
            • Considering that attr.default is provided, attr is stored in class dict if either:
                • attr is annotated as ClassVar
                • both Classtools |slots option is False and STORE_DEFAULTS config option is True
            • Attr options that have not been set are assigned with their respective defaults
            • Attr is added to __tags__ and __slots__ dicts

        Detail:
            • If ALLOW_DUNDER_ATTRS config option is False,
                dunder attrs are ignored (are left alone as class attrs)
            • Attr.IGNORED attrs are completely removed from class
                as if they were only type-annotated names
            • ClassVar annotation is not included into attr.type,
                though annotations are left unchanged (except for ATTR_ANNOTATION)
            • If variable is annotated with ATTR_ANNOTATION,
                variable is not added to annotations and attr.type is left empty
            • Annotations must be strings, error is raised otherwise,
                this encourages using 'from __future__ import annotations'
    """

    def __init__(self, metaclass):
        self.owner: Classtools = metaclass
        super().__init__()

    def __setitem__(self, attrname, annotation):
        # Value is readily Null, if attrs auto-initialization is disabled
        default = self.owner.attrsDefault

        clsdict = self.owner.clsdict

        # Get assigned value or default
        var = clsdict.get(attrname, default)

        # Deny non-string annotations
        if not isinstance(annotation, str):
            raise ClasstoolsError(f"Attr '{attrname}' - annotation must be a string. "
                                  f"Use quotes or 'from __future__ import annotations'")

        # Skip dunder attrs, if configured accordingly
        if not ALLOW_DUNDER_ATTRS and isDunder(attrname):
            return super().__setitem__(attrname, annotation)

        # Skip and remove ignored attrs from class dict
        if var is Attr.IGNORED:
            if annotation == ATTR_ANNOTATION:
                raise ClasstoolsError(f"Attr '{attrname}' - cannot use '{ATTR_ANNOTATION}' "
                                      f"annotation with ignored attrs")
            del clsdict[attrname]
            return super().__setitem__(attrname, annotation)

        # Convert to Attr if not already
        if var is Ellipsis: var = Attr()
        elif not isinstance(var, Attr): var = Attr(var)

        # The only place attr name is being set
        object.__setattr__(var, 'name', attrname)

        # Put annotation on its place, skip ATTR_ANNOTATION
        if annotation == ATTR_ANNOTATION: annotation = EMPTY_ANNOTATION
        else: super().__setitem__(attrname, annotation)

        # CONSIDER: Parse generic annotations correctly (use re, dedicated module or smth)
        # Set attr as classvar and strip annotation, if that's the case
        if annotation.startswith('ClassVar'):
            object.__setattr__(var, 'classvar', True)
            annotation = annotation.strip('ClassVar')
            if annotation.startswith('[') and annotation.endswith(']'):
                annotation = annotation[1:-1]
            elif annotation == '':
                annotation = EMPTY_ANNOTATION
            else:
                raise ClasstoolsError(f"Attr '{attrname}': invalid ClassVar annotation 'ClassVar{annotation}'")
        else:
            object.__setattr__(var, 'classvar', False)

        # Set .type with removed 'ClassVar[...]' and 'attr'
        object.__setattr__(var, 'type', annotation)

        # Set options which was not defined earlier by option definition objects / Attr kwargs
        for option in (__options__):
            if not hasattr(var, option):
                object.__setattr__(var, option, self.owner.sectionOptions[option])

        # NOTE: 'None' is a valid tag key (to allow for an easy sample of all non-tagged attrs)
        self.owner.tags[var.tag].add(attrname)
        self.owner.attrs[attrname] = var


class Attr:
    """
        Attrs objects are created from all ANNOTATED variables defined inside class body
            Exceptions are:
                • __service_var__ = smth – dunder variables
                • var: type = Attr.ignore() – explicitly marked to be ignored
            ...
        Mutable defaults must provide .copy() method (no-args) that is used to initialize object attrs;
            otherwise all objects will refer to one-and-the-same object stored in __attrs__.default
        ... TODO: Attr docstring
        Repr icons:  # CONSIDER: change to ascii because console does not support utf-8 and monospaced font breaks
            Attr      instance attr
            ClassAttr class attr
            [...]     default value
            <...>     declared type
            ⚑...      tag
            ∅         skip
            🔒         const
            🕓         lazy
    """

    # Params
    name: str
    default: Any
    type: str
    classvar: bool

    # Service
    _annotation_: str
    _typespec_: Union[type, Tuple[type, ...]]

    # Options
    tag: Optional[str]
    skip: bool
    const: bool
    lazy: str
    kw: bool

    # ' ... , *__options__' is not used here because PyCharm fails to resolve attributes this way round
    __slots__ = ('name', 'default', 'type', 'classvar',   # params
                 '_annotation_', '_typespec_',            # service
                 'tag', 'skip', 'const', 'lazy', 'kw')    # options

    IGNORED: ClassVar = type("ATTR_IGNORE_MARKER", (), dict(__slots__=()))()

    def __init__(self, value=Null, **options):
        assign = super().__setattr__
        assign('name', Null)  # just to get __str__() to work
        assign('type', Null)  # just to get __str__() to work
        assign('default', value)
        for name, value in options.items():
            assign(name, value)

    def __str__(self):
        return (
            f"{'Class'*(self.classvar)}Attr '{self.name or '<Unknown>'}'"
            + f" [{self.default}]"
            + f" <{self.type or ' '}>"
            + f' ⚑{self.tag}' * (self.tag is not None)
            + f' 🕓{self.lazy}' * (self.lazy is not False)
            + ' 🔒' * self.const
            + ' ∅' * self.skip
            + ' =' * self.kw
        )

    def __repr__(self): return auto_repr(self, self.name)

    def __setattr__(self, key, value):
        raise AttributeError(f"'{self.__class__.__name__}' object is immutable")

    @property
    def options(self): return {name: getattr(self, name) for name in __options__}

    @classmethod
    def ignore(cls): return cls.IGNORED


class Option:
    """ TODO: Option docstring
        Syntax:
            |option       – enable option (if supported)
            |option(arg)  – set option value to arg (if supported)
            /option       – disable option (or reset value to default)
        Arguments:
            • default - option notset value
            • flag - option type:
                flag=True  – option is True/False only, no parameters are accepted               - True|False
                flag=False – option stores a value, that must be provided as an argument         - arg|default
                flag=None  – option stores a value, but argument could be omitted (uses default) - True|False|arg
    """

    __slots__ = 'name', 'default', 'value', 'flag'

    def __init__(self, name, *, default: Any = False, flag: Union[bool, None]):
        assign = super().__setattr__
        assign('name', name)
        assign('default', default)
        assign('flag', flag)
        # for attr in ('name', 'default', 'flag', 'init'):
        #     super().__setattr__(attr, locals()[attr])

    def __ror__(self, other):
        if not hasattr(self, 'value'):
            if self.flag is False:
                raise ClasstoolsError(f"Option '|{self.name}' requires an argument")
            super().__setattr__('value', True)
        return self.__apply__(other)

    def __rtruediv__(self, other):
        # NOTE: disabling an option with assigned argument will reset it
        super().__setattr__('value', False if self.flag is True else self.default)
        return self.__apply__(other)

    def __call__(self, arg):
        if self.flag is True:
            raise ClasstoolsError(f"Option '|{self.name}' takes no arguments")
        option = self.__class__(self.name, default=self.default, flag=self.flag)
        super(type(option), option).__setattr__('value', arg)
        return option

    def __apply__(self, target):

        # Skip ignored attrs
        if target is Attr.IGNORED:
            return target

        # If applied to Section, change section-common defaults via Section.classdict
        if isinstance(target, Section):
            target.owner.sectionOptions[self.name] = self.value

        # Else, convert 'target' to Attr() and apply option to it
        else:
            if target is Ellipsis:
                target = Attr()
            if not isinstance(target, Attr):
                target = Attr(target)
            if hasattr(target, self.name):
                raise ClasstoolsError(f"Duplicate option '|{self.name}' - "
                                      f"was already set to '{getattr(target, self.name)}'")
            object.__setattr__(target, self.name, self.value)

        del self.value
        return target

    def __repr__(self): return auto_repr(self, self.name)

    def __setattr__(self, name, value):
        raise AttributeError(f"'{self.name}' object is not intended to be used beyond documented syntax")


class Classtools(type):  # CONSIDER: Classtools
    """ TODO: Classtools docstring
        Variables defined without annotations are not tagged
        SECTION without any attrs inside is not created
        Tag names are case-insensitive
        Member methods (class is direct parent in __qualname__) are not tagged,
            even if they are assigned not using 'def'
        Supports `ClassName['attr']` syntax for accessing attr objects
        • slots ——► auto inject slots from __attrs__
        • init ——► auto-initialize all __attrs__ defaults to 'None'
    """

    __tags__: DefaultDict[str, OrderedSet]
    __attrs__: Dict[str, Attr]

    enabled: bool

    sectionOptions: Dict[str, Any]
    addSlots: bool
    addInit: bool

    clsname: str
    clsdict: Dict[str, Any]
    tags: DefaultDict[str, OrderedSet]
    attrs: Dict[str, Attr]
    annotations: Dict[str, str]

    @classmethod
    def __prepare__(metacls, clsname, bases, enable=True, slots=False, init=True, initattrs=Null):

        metacls.enabled = enable
        if enable is False: return {}

        metacls.attrsDefault = initattrs
        metacls.addSlots = slots
        metacls.addInit = init

        metacls.clsname = clsname
        metacls.clsdict = {}
        metacls.tags = metacls.clsdict.setdefault('__tags__', defaultdict(OrderedSet))
        metacls.attrs = metacls.clsdict.setdefault('__attrs__', {})
        metacls.annotations = metacls.clsdict.setdefault('__annotations__', AnnotationSpy(metacls))

        metacls.sectionOptions: Dict[str, Any] = {}

        # Initialize options
        metacls.resetOptions()

        if INJECT_OPTIONS:  # TESTME
            # CONSIDER: adjustable names below
            metacls.clsdict['attr'] = attr
            metacls.clsdict['tag'] = tag
            metacls.clsdict['skip'] = skip
            metacls.clsdict['const'] = const
            metacls.clsdict['lazy'] = lazy
            metacls.clsdict['kw'] = kw

        return metacls.clsdict

    def __new__(metacls, clsname, bases, clsdict: dict, **kwargs):

        if metacls.enabled is False:
            return super().__new__(metacls, clsname, bases, clsdict)

        # Cleanup class __dict__
        for name, attr in metacls.attrs.items():
            if attr.default is Null or (attr.classvar is False and (metacls.addSlots or not STORE_DEFAULTS)):
                if name in clsdict: del clsdict[name]
            else:
                clsdict[name] = attr.default

        # NOTE: Alternative version
        # if attr.default is Null
        # or self.owner.slots and attr.classvar is False
        # or not STORE_DEFAULTS and attr.classvar is False:

        # Use tags and attrs that are already in clsdict if no parents found
        # CONSIDER: why do I need first condition here???
        if hasattr(metacls, 'clsdict') and bases:
            clsdict['__tags__'] = metacls.mergeTags(bases, metacls.tags)
            clsdict['__attrs__'] = metacls.mergeParentDicts(bases, '__attrs__', metacls.attrs)

        # Deny explicit/implicit Attr()s assignments to non-annotated variables
        for attrname, value in clsdict.items():
            if isinstance(value, Attr):
                raise ClasstoolsError(f"Attr '{attrname}' is used without type annotation!")
            if isinstance(value, Attr.IGNORED.__class__):
                raise ClasstoolsError(f"Attr.IGNORED marker could be used only with annotated variables")

        # Deny ATTR_ANNOTATION in annotations and generic structures, if configured accordingly
        if not ALLOW_ATTR_ANNOTATIONS:
            for attrname, annotation in metacls.annotations.items():
                if len(findall(rf'\W({ATTR_ANNOTATION})\W', annotation)) > 0:
                    raise ClasstoolsError(f"Attr '{attrname}: {annotation}' - Classtools is configured to deny "
                                          f"'{ATTR_ANNOTATION}' annotations inside generic structures")

        # Deny Classtools service objects assignments to class variables or attrs, if configured accordingly
        if not ALLOW_SERVICE_OBJECTS:
            for value in chain(clsdict.values(), (attrobj.default for attrobj in metacls.attrs.values())):
                if isinstance(value, (Section, Option)):
                    raise ClasstoolsError(f"Classtools is configured to deny "
                                          f"'{value.__class__.__name__}' objects in user classes")

        # Check options compatibility
        metacls.verifyOptions()

        # Inject slots from all non-classvar attrs, if configured accordingly
        if metacls.addSlots is True:
            metacls.injectSlots(clsdict)

        # Configure attr descriptors based on options being set
        metacls.setupDescriptors(clsdict)

        # Generate __init__() function, 'init()' is used to further initialize object
        if metacls.addInit is True:
            metacls.injectInit(clsdict)

        # Generate __getattr__ function handling first access to lazy evaluated attrs
        metacls.injectGetattr(clsdict)

        # Convert annotation spy to normal dict
        clsdict['__annotations__'] = dict(metacls.annotations)

        del metacls.enabled
        del metacls.sectionOptions
        del metacls.addSlots
        del metacls.addInit
        del metacls.clsname
        del metacls.clsdict
        del metacls.tags
        del metacls.attrs
        del metacls.annotations

        return super().__new__(metacls, clsname, bases, clsdict)

    def __getitem__(cls, item):
        return cls.__attrs__[item]

    @classmethod
    def verifyOptions(metacls):
        for name, attr in metacls.attrs.items():
            if attr.classvar:
                errorOptions = tuple(option.name for option in (const, lazy, kw, skip)
                                if attr.options[option.name] is not False)
                if errorOptions:
                    raise ClasstoolsError(f"ClassAttr '{name}' has incompatible options: "
                                          + ', '.join((f'|{option}' for option in errorOptions)))
            if attr.kw and attr.skip:
                # TODO: make this options combination to create attr only if it is provided in constructor arguments
                raise ClasstoolsError("Attr cannot have both '|skip' and '|kw' options set")

    @classmethod
    def injectSlots(metacls, clsdict):
        slots = []
        for name, attr in metacls.attrs.items():
            if attr.classvar is True:
                continue
            if attr.const is True:
                slots.append(f'{name}_slot')
            else:
                slots.append(name)
        clsdict['__slots__'] = tuple(slots)

    @classmethod
    def injectInit(metacls, clsdict):

        metDefaultAttr = False
        args = []
        kwargs = []
        lines = []

        for name, attr in metacls.attrs.items():

            # Skip attrs that do not need initialization
            if attr.classvar is True or attr.lazy is not False:
                continue

            # Create __init__ argument entry string of the form <attrname>: <annotation> = <default>
            entryStr = name
            defaultStr = f"__attrs__['{name}'].default"

            # Append type annotation, if provided
            if name in metacls.annotations:
                entryStr += ': ' + metacls.annotations[name]

            # Append default value assignment, if provided
            if attr.default is not Null:
                metDefaultAttr = True
                entryStr += ' = ' + defaultStr

            # Provide more accurate error if non-default argument appears after default one
            elif attr.kw is False and metDefaultAttr is True:
                raise ClasstoolsError(f"Non-default attr '{name}' is found after one with default")

            # Add assignment to args or kwargs section
            if not attr.skip:
                getattr(kwargs if attr.kw is True else args, 'append')(entryStr)

            # Provide distinct references for mutable objects
            if hasattr(attr.default, 'copy') and hasattr(attr.default.copy, '__call__'):
                copyStr = '.copy()'
            else:
                copyStr = ''

            # Add attr initializer statement
            if attr.skip is True:
                if attr.default is not Null:
                    lines.append(f'self.{name} = {defaultStr}{copyStr}')
            elif attr.const:
                lines.append(f"self.{name}_slot = {name}")
            else:
                lines.append(f'self.{name} = {name}{copyStr}')

        # Call .init(), if provided
        try:
            clsdict.get('init').__call__
        except AttributeError:
            if kwargs: args.append('*')
            log.spam(f'init() is not provided')
        else:
            args.append('*args')
            kwargs.append('**kwargs')
            lines.append('self.init(*args, **kwargs)')

        # Skip if nothing to init
        if not lines: return

        # Format and compile __init__ function
        globs = {'__attrs__': metacls.attrs}
        template = f"def __init__(self, {', '.join(args)}, {', '.join(kwargs)}):\n    " + '\n    '.join(lines)
        log.debug(f"Generated {metacls.clsname}.__init__():\n"+template)
        eval(compile(template, '<classtools generated __init__>', 'exec'), globs, clsdict)

    @classmethod
    def injectGetattr(metacls, clsdict):

        # Define closure cache dict for future __getattr__ method
        lazyAttrs = {name: attr.lazy for name, attr in metacls.attrs.items() if attr.lazy is not False}

        # Skip injecting __getattr__ if no lazy attrs are present
        if not lazyAttrs:
            return

        # Check all lazy attrs have their respective getters
        for name, getter in lazyAttrs.items():
            try:
                clsdict.get(getter).__call__
            except AttributeError:
                raise ClasstoolsError(f"Cannot find lazy evaluation method "
                                      f"'{getter}' for attr '{name}'")

        # Generate future __getattr__ method
        def evalLazyAttrs(self, name):
            if name in lazyAttrs:
                try:
                    result = getattr(self, lazyAttrs[name])()
                except GetterError:
                    result = self.__attrs__[name].default
                    if result is Null:
                        raise ClasstoolsError(f"Failed to compute '{name}' value, "
                                              f".default is not provided")
                setattr(self, name, result)
                return result
            # Will definitely fail, but with standard error message
            return getattr(super(self.__class__, self), name)

        # Fuse with existing __getattr__ method, if defined
        if '__getattr__' in clsdict:
            def __getattr_combined__(self, item):
                self.evalLazyAttrs(item)
                return clsdict['__getattr__'](item)
            clsdict['__getattr__'] = __getattr_combined__
        else:
            clsdict['__getattr__'] = evalLazyAttrs

    @classmethod
    def setupDescriptors(metacls, clsdict):
        for attr in metacls.attrs.values():
            if attr.const is True:
                clsdict[attr.name] = ConstDescriptor(attr.name)


    @staticmethod
    def mergeTags(parents, currentTags):
        # Collect all base class tags dicts + current class tags dict
        tagsDicts = attachItem(filter(None, (parent.__dict__.get('__tags__') for parent in parents)), currentTags)

        # Take main parent's tags as base tags dict
        try: newTags = tagsDicts.__next__().copy()

        # Use current tags if no single parent defines any
        except StopIteration: return currentTags

        # Merge all tags by tag name into 'newTags'
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
        metacls.sectionOptions.update(
                {option.name: option.default for option in (tag, skip, const, lazy, kw)})


class ConstDescriptor:
    __slots__ = 'name', 'slot'

    def __init__(self, name):
        self.name = f'{name}_slot'

    def __get__(self, instance, owner):
        # Access descriptor itself from class
        if instance is None: return self
        return getattr(instance, self.name)

    def __set__(self, instance, value):
        if hasattr(instance, self.name):
            raise AttributeError(f"Attr '{self.name.rstrip('_slot')}' is declared constant")
            # CONSIDER: when using __slots__, this msg is not printed --► need to make unified?
        else:
            setattr(instance, self.name, value)


class Section:
    """
        TODO: Section docstring
    """

    __slots__ = ()

    owner = Classtools

    def __enter__(self): pass

    def __exit__(self, *args):
        self.owner.resetOptions()

    def __getitem__(self, *args, **kwargs):
        return self.__apply__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        return self.__apply__(*args, **kwargs)

    def __apply__(self, *args, **kwargs):
        raise NotImplementedError


class OptionSection(Section):
    def __apply__(self, **kwargs):
        for name, value in kwargs.items():
            if name not in __options__:
                raise ClasstoolsError(f"Invalid option '{name}'")
            self.owner.sectionOptions[name] = value
        return self


class TagSection(Section):
    def __apply__(self, *args):
        if len(args) != 1:
            raise TypeError(f"{self.__class__.__name__} requires single positional argument 'tag'")
        self.owner.sectionOptions[tag.name] = args[0]
        return self


def classtools(cls):
    """ Just to shut down PyCharm code inspection considering __init__ arguments """
    return cls


# TODO: Move all options to options.py, define __all__ there and import options as 'from options import *'
""" Assign a tag to attr and adds it to __tags__ dict """
tag = Option('tag', default=None, flag=False)

""" Exclude attr from initialization machinery """
skip = Option('skip', flag=True)

""" Deny value assignments (uses descriptor) """
const = Option('const', flag=True)

""" Evaluate value on first access, store it and return 
    stored value on all subsequent queries (uses descriptor) """
lazy = Option('lazy', flag=False)

""" Use attr as keyword-only argument in __init__ """
kw = Option('kw', flag=True)


# TODO: review this in the end
# If adding new option, add it to:
#     1) Option() objects above
#     2) __options__ global variable
#     3) Attr.__slots__
#     4) Attr.__str__ option icons
#     6) Classtools.resetOptions()
#     7) ClassDict name injections in Classtools.__prepare__
#     8) Option __doc__
#     9) Check whether it is needed to add variable with new option
#        to __slots__ in Classtools.__new__
#     10) Is it needed to skip attr initialization with new option set in Classtools.__init_attrs__

attr = ATTR_ANNOTATION  # placeholder for empty annotation
OPTIONS = OptionSection()
TAG = TagSection()


# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #


def test_pickle():
    class PT(metaclass=Classtools, slots=True):
        """ Pickle test, slots """
        void: attr
        e: attr = 'e_attr'
        conv: int = 0
        classAttr: ClassVar[str] = 'class_attr'
        tag: attr = 7 |tag('test')
        const: int = 42 |const
        lazy: str = ... |lazy('getLazy')
        kw: attr = ... |kw
        skip: attr = 'skip_attr' |skip
        def getLazy(self): return 'lazy_value'
        def init(self, e=88): self.e = e
    import pickle as p
    print(formatDict(PT.__attrs__))
    print(PT('void_attr', kw='kw_attr').lazy)
    pA = p.dumps(PT('void_attr', e=88, kw='kw_attr'))
    print(pA)
    print(f"Unpickled same 'e' attr? - {p.loads(pA).e == PT().e}")
    exit()


def test_pickle_simple():
    class PTS(metaclass=Classtools, slots=True):
        """ Pickle test simple, slots"""
        a: attr = 1
    import pickle as p
    pClass = p.dumps(PTS)
    print(pClass)
    print(f"Unpickled same 'a' attr? - {p.loads(pClass).a == PTS().a}")


def test_concise_tagging_basic():

    @classtools
    class A(metaclass=Classtools, slots=True):

        a0: str = -Attr() |tag('a')
        a: int = 4 |tag("a_var") |lazy('set_a') |const
        c: Any = 3
        lazy('will_be_ignored')
        test: attr = 'works!' /const

        with OPTIONS |lazy('tag_setter'):
            e: attr
            f: int = Attr(0, const=True) |tag('classic')
            m: attr = 7 |lazy('get_m')

        with TAG['tag'] |skip:
            b: str = 'loool' /skip
            d: ClassVar[int] = 0 |kw
            g: ClassVar[int] = 42 |tag(None)
            k: ClassVar[str] = 'clsvar'

        h: list = []

        def set_a(self): return 'a_value'

        def tag_setter(self): return 'tag_value'

        def get_g(self): return 33

        def get_m(self): return 'm_value'

        def get_test(self): return 'test_value'

        def init(self, e_arg=88): self.e = e_arg

    print(formatDict(A.__dict__))
    print(formatDict(A.__tags__))
    print(hasattr(A(), '__dict__'))
    print(f".a = {A().a}")
    print(f".b = {A().b}")
    print(f".c = {A(c=9).c}")
    print(f".d = {A().d}")
    try: A().d = 'will_fail'
    except AttributeError as e: print(f"Attempt to assign to const: {e}")
    else: print("Const descriptor does not work!")
    print(f".f = {A().f}")
    print(f".g = {A().g}")
    print(f".k = {A().k}")
    print(f".m = {A().m}")
    print(f".e (with e_arg) = {A(e_arg=4).e}")
    print(f".e = {A().e}")
    print(f".test = {A().test}")
    print(f".__slots__ = {A().__slots__}")
    print(f"Are ints equal? - {A().a is A().a}")
    print(f"Are lists equal? - {A().h is A().h}")


def test_inject_slots():
    class B(metaclass=Classtools, slots=True):
        a: attr = 7
        b: int = 0 |const |lazy('set_b')

    b = B()
    print(f"Has dict? {hasattr(b, '__dict__') and b.__dict__}")
    print(b.__slots__)

    class C(metaclass=Classtools, slots=True):

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
    # test_pickle_simple()

