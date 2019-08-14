from __future__ import annotations

from collections import defaultdict
from functools import partial
from itertools import starmap
from operator import setitem
from typing import Optional, Dict, Any

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
class Option:
    _instance_ = None  # Make singleton as class just provides syntax

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance_, cls):
            cls._instance_ = object.__new__(cls)
        return cls._instance_

    def __init__(self, optionname):
        self.attrobject = None  # attrobject attr object
        self.name = optionname

    def __call__(self, par):
        setattr(self.attrobject, self.name, par)  # set option with parameter
        return self.attrobject

    def __get__(self, instance, owner):
        log.debug("Get option")  # set option without parameters
        self.attrobject = instance
        setattr(self.attrobject, self.name, True)
        return self.attrobject


class Attr:
    """ Mutable default values must define .copy() method """
    _options_ = dict.fromkeys(('const', 'lazy',), False)  # TODO: 'factory'
    __slots__ = 'name', 'default', 'type', *_options_.keys()

    owner = None  # class containing this attrs

    # TESTME: support 3 syntax variations:
    #           a: str = attr(3) .lazy('meth') .const
    #           b: str = attr[3] .lazy('meth') .const
    #           c: str = attr(3, lazy='meth', const=True)
    # CONSIDER: d: int = 3 <attr> 'lazy const -init'
    # CONSIDER: d: int = attr > 3 > 'lazy const -init'
    # CONSIDER: d: int = attr > 'lazy const -init'          # no default

    # CONSIDER: default_factory issue: is it still relevant
    #           when defaults are assigned to each instance individually?

    def __init__(self, value, **options):
        self.default = value
        # ▼ stores current option name to allow parameter assignments via __call__()
        self._current_ = None
        if options:
            # ▼ Called using syntax #3
            self.get('parseOptions')(options)

    def __getitem__(self, item):
        if hasattr(self, '_current_'):
            # ▼ [...] is used somewhere among options definition
            raise SyntaxError("[...] syntax is used only to define default value")
        self.__init__(item)

    def __getattribute__(self, item):
        # ▼ Called using syntax #2
        if item not in self.get('_options_').keys():
            raise ValueError(f"Invalid option: {item}")
        setattr(self, item, True)
        self._current_ = item
        return self

    def __call__(self, par):
        # ▼ Option is provided with parameter
        if self.get('_current_'):
            setattr(self, self.get('_current_'), par)
            self._current_ = None  # Allow no more calls
            return self
        else: raise SyntaxError("Double parenthesis")

    def __str__(self):
        return f"Attr '{self.name}' {{{self.default}}} <{self.type}> " \
            f"{'|'.join(option for option in self.get('_options_').keys() if self.get(option) is not False)}"

    def get(self, item):
        """ Attribute getter for internal use """
        return super().__getattribute__(self, item)

    def parseOptions(self, options: Dict[str, Any]):
        for optionname, default in self.get('_options_'):
            setattr(self, optionname, options.pop(optionname, default))  # TODO: assign to what SECTION defines, not default
        if options: raise ValueError(f"Invalid option(s): {', '.join(options.keys())}")


class SectionTitle:
    """ New section marker. Tells ClsdictProxy when new tag is defined.
        Usages (in class body) (options can be omitted, if not needed):
            • SECTION('tag_name', option1, optionN)
            • SECTION['tag_name', option1, optionN]
            • SECTION('tag_name') .option1 .optionN
            • SECTION['tag_name'] .option1 .optionN  # TODO: alternative syntax for SECTION
            (PyCharm highlights square bracket statement nicely :)
        Supported options:
            • 'const' — all attrs in current section will be immutable
                        value may be changed though by accessing '_attrname_slot' attribute
                        (it's Python, babie)
    """

    proxy: ClsdictProxy = None

    def __getitem__(self, tagname: Optional[str], **options):

        Attr(tagname)

        if tagname is None:
            if options: raise ValueError("SECTION options could not be set when resetting tag")
            else:
                ...  # TODO: reset Attr._options_ defaults
                return self.proxy.resetTag()
        elif not isinstance(tagname, str):
            raise ValueError(f"Tag name is not a string: {tagname}")



        # TODO:
        PROBLEM : how to describe here the same syntax as Attr uses?
        Better to implement option assignments via descriptors and use them in both classes
        Creating a fork here to try it.


        Created new branch.



        self.proxy.setNewTag(tagname.lower())

        elif not options:
            return self.proxy.setNewTag(tagname.lower())
        elif option is not const:
            raise ValueError(f"Unsupported option: {option}")
        else:
            return self.proxy.setNewTag(tagname.lower(), frozen=True)
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

        # ▼ assign tag if attr has no value, only annotation
        #       (duplicate assignments won't be performed since .tags is a set)
        self.target.assignTag(attrname)


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
        if not isMemberFunction(self, value): self.assignTag(key)
        return super().__setitem__(key, value)

    def assignTag(self, attrname):
        """ Set tag to attr: dunders and member methods are ignored """
        if not isDunderAttr(attrname) and self.currentTag is not None:
            self.tags[self.currentTag].add(attrname)
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
            # TODO: Attr.attrobject = SECTION.proxy
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
        # TODO: Attr.attrobject = None not to disrupt future Attr class use
        return super().__new__(*args)


SECTION = SectionTitle()

# TODO: move all these shortcuts to a separate file (for ex., classtools.py)

TaggedType = TaggedAttrsTitledType

class Tagged(TaggedType): pass


if __name__ == '__main__':
    ...
