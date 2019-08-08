from __future__ import annotations as annotations_feature

from itertools import chain, groupby
from operator import itemgetter
from sys import getsizeof as size
from typing import ClassVar, Tuple, Optional

from ..Utils import VoidDict, formatDict, legacy, attachItem


# TODO: Add option to auto-init empty class variables (like 'd: ClassVar[str]') with None

# TODO: document all this stuff!

# CONSIDER: Add tagging via 'with' block

# CONSIDER: prevent creation of unused classes

# TODO: implement lookups diving into mro classes when searching for defaults to initialize slots
#           just like normal attrs lookup is performed instead of creating cumulative _defaults_ in each class

# CONSIDER: lazy attrs evaluation (problem is with conflicting names to access and store attr value)

# CONSIDER:

# TODO: Create wrapper descriptor for __slots__ to:
#           1. make lookups for a _defaults_, don't assign it to a slot;
#           2. allow for 'frozen' sections via (SECTION['name', const])


@legacy
class ClearAnnotationsType(type):

    def __new__(metacls, clsname, bases, clsdict, **kwargs):
        annotations = getAnnotations(clsdict)
        for attr, typeval in annotations.items():
            if isClassVar(typeval): continue
            try: del clsdict[attr]
            except KeyError: pass
        return super().__new__(metacls, clsname, bases, clsdict)


@legacy
class TaggedAttrsInAnnotationsType(ClearAnnotationsType):  # NOTE: not working, see comment below

    def __new__(metacls, clsname, bases, clsdict, tagging: str = 'after annotation', **kwargs):
        if tagging != 'after annotation':
            raise NotImplementedError(f"Tagging mode '{tagging}' is not supported")
        annotations = getAnnotations(clsdict)
        tagLists = {}
        for attr, annotation in annotations.items():
            typeval, tag = metacls.splitTag(clsname, attr, annotation)
            if tag is not None:
                if isClassVar(typeval): continue
                metacls.placeTag(tagLists, tag, attr)
                annotations[attr] = typeval
        for listname, tags in tagLists:
            clsdict[listname.join('_')] = tuple(tags)
        return super().__new__(metacls, clsname, bases, clsdict)

    @staticmethod
    def splitTag(clsname: str, attr: str, annotation: str) -> Tuple[str, Optional[str]]:
        try: tag, typeval = annotation.rsplit(maxsplit=1)  # FIXME: no spaces in annotations, this won't work
        except ValueError: return annotation, None
        if tag.startswith('(') and tag.endswith(')'):
            tag = tag[1:-1]
            if tag.isidentifier(): return tag, typeval
        raise SyntaxError(f"{clsname}.{attr}: unacceptable tag '{tag}'")

    @staticmethod
    def placeTag(tagLists, tagname, attr):
        try: tagLists[tagname].append(attr)
        except KeyError: tagLists[tagname] = [attr, ]

# -------------------------------------------------------------------------------------------------------------------- #


class CodeDesignError(TypeError):
    """ Class is used incorrectly by higher-level code """


def getAnnotations(clsdict):
    return clsdict.get('__annotations__', VoidDict())


def isDunderAttr(attrname: str) -> bool:
    return attrname.startswith('__') and attrname.endswith('__')


def isClassVar(annotation: str) -> bool:
    return annotation.startswith('ClassVar[') and annotation.endswith(']')


class ClassModifier(type):
    """ Used to allow **kwargs in super().__new__() calls """
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, *args)


class TagType(type):
    _instance_ = None

    def __new__(metacls, clsname, bases, clsdict, **kwargs):
        clsdict['__slots__'] = ()

        # ▼ register tag only when inherited from base class (bases contains it)
        if len(bases) > 1:
            return clsdict  # ◄ return dict instead of class to ↓ size, identify tag later by __name__ and __class__

        # ▼ Only base class needs to be actually created
        else: return super().__new__(metacls, clsname, bases, clsdict)

    def __call__(cls, *args, **kwargs):
        if not cls._instance_: cls._instance_ = super().__call__(*args, **kwargs)
        return cls._instance_


class TAG(dict, metaclass=TagType):

    def __new__(cls, *attrs):
        raise RuntimeError(f"Class {cls.__name__} is not intended be instantiated!")


class ClsdictTagNestedProxy(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self['__tags__'] = {}

    def __setitem__(self, key: str, value):
        assert isinstance(TAG, type), type(TAG)
        if isinstance(value, type) and value.__bases__[0] is TAG:
            self.updateFromNested(key.lower(), value.__dict__)
        else: return super().__setitem__(key, value)

    def updateFromNested(self, tagname, nestedDict):
        annotations = getAnnotations(nestedDict)
        taggedList = list(annotations.keys())
        self['__annotations__'].update(annotations)
        for attr, value in nestedDict.items():
            if not isDunderAttr(attr):
                self[attr] = value
                if attr not in taggedList: taggedList.append(attr)
        self['__tags__'][tagname] = tuple(taggedList)


class InjectedSlotsType(ClassModifier):

    def __new__(metacls, clsname, bases, clsdict, **kwargs):
        if not kwargs.get('baseClass'):
            annotations = getAnnotations(clsdict)
            slots = []
            defaults = {}
            for attr, annotation in annotations.items():
                if isDunderAttr(attr): continue
                if isClassVar(annotation): continue
                slots.append(attr)
                try: defaults[attr] = clsdict[attr]
                except KeyError: pass
                else: del clsdict[attr]
            if defaults:
                # ▼ if subclassed from class of this metaclass => subclassed from InjectedSlots
                if bases and type(bases[0]) is metacls:
                    clsdict['_defaults_'] = metacls.collectDefaults(bases, defaults)
                else:
                    # ▼ InjectedSlots.__new__ should initialize defaults
                    raise CodeDesignError(f"In '{clsname}' class signature: {metacls.__name__} metaclass "
                                          f"could not initialize slots with defaults defined in class. "
                                          f"Inherit from corresponding base class")
            clsdict['__slots__'] = tuple(slots)
        return super().__new__(metacls, clsname, bases, clsdict)

    @staticmethod
    def collectDefaults(bases, currentDefaults):
        dicts = attachItem(
                iterable=filter(None, (parent.__dict__.get('_defaults_') for parent in reversed(bases))),
                append=currentDefaults
        )
        newDefaults = dicts.__next__()
        for defaults in dicts: newDefaults.update(defaults)
        return newDefaults


class InjectedSlots(metaclass=InjectedSlotsType, baseClass=True):
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        if isinstance(super(), object):
            instance = object.__new__(cls)
        else:
            instance = super().__new__(cls, *args, **kwargs)

        if hasattr(cls, '_defaults_'):
            for attr, value in cls._defaults_.items():
                if not hasattr(instance, attr): setattr(instance, attr, value)
        return instance


class TaggedAttrsNestedType(ClassModifier):

    @classmethod
    def __prepare__(metacls, name, bases, baseClass=False):
        if not baseClass: return ClsdictTagNestedProxy()
        else: return {}

    def __new__(metacls, clsname, bases, clsdict, **kwargs):
        clsdict['__slots__'] = ()
        # FIXME: consider subclass (inherit __tags__)
        super().__new__(metacls, clsname, bases, dict(clsdict))


class TaggedAttrsNested(metaclass=TaggedAttrsNestedType, baseClass=True):
    __slots__ = ()


class AnnotationProxy(dict):

    def __init__(self, clsdictProxy):
        super().__init__()
        self.target = clsdictProxy

    def __setitem__(self, attrname, value):
        self.target.get('__annotations__')[attrname] = value
        if not isDunderAttr(attrname) and self.target.currentTag is not None:
            self.target.tags[self.target.currentTag].append(attrname)


class ClsdictTagTitledProxy(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set('__tags__', {})
        self.set('__annotations__', {})
        self.tags = self.get('__tags__')
        self.spy = AnnotationProxy(self)
        self.currentTag: str = None

    def __getitem__(self, key):
        if key == '__annotations__':
            return self.spy
        else: return super().__getitem__(key)

    def set(self, key, value):
        """ __setitem__ for internal use """
        return super().__setitem__(key, value)

    def setNewTag(self, tagname):
        self.currentTag = tagname
        self.tags[self.currentTag] = []


class TaggedAttrsTitledType(ClassModifier):

    @classmethod
    def __prepare__(metacls, name, bases, baseClass=False):
        if not baseClass:
            SECTION.proxy = ClsdictTagTitledProxy()
            return SECTION.proxy
        else: return {}

    def __new__(metacls, clsname, bases, clsdict, **kwargs):
        if hasattr(clsdict, 'tags'):
            # ▼ Collect all base class tag dicts + current class tag dict
            tagDicts = filter(None, (parent.__dict__.get('__tags__') for parent in bases))
            tagsItems = (item for tagsDict in attachItem(tagDicts, clsdict.tags) for item in tagsDict.items())

            # ▼ Merge all tags by tag name
            newTags = {}
            getIndex = itemgetter(0)
            for k, g in groupby(sorted(tagsItems, key=getIndex), getIndex):
                newTags[k] = tuple(chain.from_iterable((i[1] for i in g)))

            # ▼ Check for name collisions
            for tagname, tags in newTags.items():
                if len(set(tags)) < len(tags):
                    raise AttributeError(f"Class {clsname} has attr name conflict with base class in category {tagname}"
                                         f" (test. name is: {(tag for tag in tags if tag not in set(tags)).__next__()}")
            clsdict['__tags__'] = newTags
        return super().__new__(metacls, clsname, bases, dict(clsdict), **kwargs)


class TaggedAttrsTitled(metaclass=TaggedAttrsTitledType, baseClass=True):
    __slots__ = ()


class SectionTitle:  # CONSIDER: maybe, redefine it a bit nicer somehow ...
    proxy = None

    def __getitem__(self, tagname):
        self.proxy.setNewTag(tagname)


SECTION = SectionTitle()

class NestedTagsAndSlotsType(TaggedAttrsNestedType, InjectedSlotsType):
    pass

class TitledTagsAndSlotsType(TaggedAttrsTitledType, InjectedSlotsType):
    pass

class TaggedSlots(TaggedAttrsTitled, InjectedSlots, metaclass=TitledTagsAndSlotsType, baseClass=True):
    __slots__ = ()

Tagged = TaggedAttrsTitled

Slots = InjectedSlots


# -------------------------------------------------------------------------------------------------------------------- #


if __name__ == '__main__':

    def func(self, par=None) -> None:
        pass


    class Test_DefaultsInit(TaggedSlots):
        SECTION['test']
        a: int = 4
    t = Test_DefaultsInit()
    assert t.a == 4, 'init defaults with subclass'

    try:
        class Test_DefaultsInitFail(metaclass=TitledTagsAndSlotsType):
            SECTION['test_fail']
            b: int = 5
        t = Test_DefaultsInitFail()
    except CodeDesignError as e: print(e); print('OK')
    else: assert t.b == 5, 'init defaults with metaclass'

    class Test_TaggedSlots(TaggedSlots):

        class Nested:
            a = 'nested_var'

            def __init__(self, p):
                self.p = p

            def __eq__(self, other):
                return self.p == other.p

        a = 1
        b: int
        c: int = 2
        d: bool = True
        e: Nested = Nested('nested_par')

        SECTION['service']
        f: ClassVar[str]
        g: ClassVar[str] = 'azaza'

        SECTION['test']

        SECTION['other']
        h: int = 99
        i: str

        def __init__(self, par):
            super().__init__()
            self.b = par
            self.c = 3
            self.__class__.f = 1.1

    t = Test_TaggedSlots('a_var')
    assert not hasattr(t, '__dict__'), '__dict__'
    assert hasattr(t, '__slots__'), '__slots__'
    assert hasattr(t, '__annotations__'), '__annotations__'
    assert hasattr(t, '__tags__'), '__tags__'
    assert hasattr(t, '_defaults_'), '_defaults_'
    assert set(t.__class__.__tags__.keys()) == {'service', 'test', 'other'}, f'tags: {t.__class__.__tags__.keys()}'
    assert not hasattr(t, 'i'), 'i'
    assert (t.a, t.b, t.c, t.d, t.e, t.f, t.g, t.h) == \
           (1, 'a_var', 3, True, Test_TaggedSlots.Nested('nested_par'), 1.1, 'azaza', 99), 'attrs'


    class Test_Tagged(Tagged):
        class Nested:
            a = 'nested_var'

            def __init__(self, p):
                self.p = p

            def __eq__(self, other):
                return self.p == other.p

        a = 1
        b: int
        c: int = 2
        d: bool = True
        e: Nested = Nested('nested_par')

        SECTION['service']
        f: ClassVar[str]
        g: ClassVar[str] = 'azaza'

        SECTION['test']

        SECTION['other']
        h: int = 99
        i: str

        def __init__(self, par):
            super().__init__()
            self.b = par
            self.c = 3
            self.__class__.f = 1.1


    t = Test_Tagged('a_var')
    assert hasattr(t, '__dict__'), '__dict__'
    assert set(t.__class__.__tags__.keys()) == {'service', 'test', 'other'}, 'tags'
    assert (t.a, t.b, t.c, t.d, t.e, t.f, t.g, t.h) == \
           (1, 'a_var', 3, True, Test_TaggedSlots.Nested('nested_par'), 1.1, 'azaza', 99), 'attrs'


    class Test_TaggedSlots(Slots):

        class Nested:
            a = 'nested_var'

            def __init__(self, p):
                self.p = p

            def __eq__(self, other):
                return self.p == other.p

        a = 1
        b: int
        c: int = 2
        d: bool = True
        e: Nested = Nested('nested_par')

        f: ClassVar[str]
        g: ClassVar[str] = 'azaza'

        h: int = 99
        i: str

        def __init__(self, par):
            super().__init__()
            self.b = par
            self.c = 3
            self.__class__.f = 1.1

    t = Test_TaggedSlots('a_var')
    assert not hasattr(t, '__dict__'), '__dict__'
    assert hasattr(t, '__slots__'), '__slots__'
    assert hasattr(t, '__annotations__'), '__annotations__'
    assert hasattr(t, '_defaults_'), '_defaults_'
    assert not hasattr(t, 'i'), 'i'
    assert (t.a, t.b, t.c, t.d, t.e, t.f, t.g, t.h) == \
           (1, 'a_var', 3, True, Test_TaggedSlots.Nested('nested_par'), 1.1, 'azaza', 99), 'attrs'


    class Test_BaseClass(TaggedSlots):
        a = 1
        c: int = 2

        SECTION['service']
        f: ClassVar[str]

        SECTION['test']

        SECTION['other']
        h: int = 99

        def __init__(self, par):
            super().__init__()
            self.c = 3
            self.__class__.f = 1.1


    class Test_SubclassedTaggedSlots(Test_BaseClass):

        class Nested:
            a = 'nested_var'

            def __init__(self, p):
                self.p = p

            def __eq__(self, other):
                return self.p == other.p

        b: int
        d: bool = True
        e: Nested = Nested('nested_par')

        SECTION['service']
        g: ClassVar[str] = 'azaza'

        SECTION['other']
        i: str

        def __init__(self, par):
            super().__init__(par)
            self.b = par


    t = Test_SubclassedTaggedSlots('a_var')
    # assert not hasattr(t, '__dict__'), '__dict__'
    # assert hasattr(t, '__slots__'), '__slots__'
    # assert hasattr(t, '__annotations__'), '__annotations__'
    # assert hasattr(t, '__tags__'), '__tags__'
    # assert hasattr(t, '_defaults_'), '_defaults_'
    # assert tuple(t.__class__.__tags__.keys()) == ('service', 'test', 'other'), 'tags'
    # assert not hasattr(t, 'i'), 'i'
    # assert (t.a, t.b, t.c, t.d, t.e, t.f, t.g, t.h) == \
    #        (1, 'a_var', 3, True, Test_TaggedSlots.Nested('nested_par'), 1.1, 'azaza', 99), 'attrs'






    print('—'*120)

    print(f"Class.__dict__: {formatDict(Test_SubclassedTaggedSlots.__dict__)}")

    print(f"Has __slots__? {hasattr(t, '__slots__')}")
    if hasattr(t, '__slots__'):  print(f"t.__slots__: {t.__slots__}")

    print(f"Has __annotations__? {hasattr(t, '__annotations__')}")
    if hasattr(t, '__annotations__'): print(f"t.__annotations__: {t.__annotations__}")

    print(f"Has __tags__? {hasattr(t, '__tags__')}")
    if hasattr(t, '__tags__'): print(formatDict(t.__tags__))

    print(f"Has __dict__? {hasattr(t, '__dict__')}")
    if hasattr(t, '__dict__'): print(formatDict(t.__dict__))

    print(f"Attrs of t:")
    for attr in ('abcdefgh'):
        print(f"{attr} = {getattr(t, attr, '<No attr>')}")

    print(f"Size of t object: {size(t)}")

















