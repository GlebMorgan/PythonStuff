from __future__ import annotations

from collections import defaultdict
from functools import partial
from itertools import starmap
from operator import setitem
from typing import Optional

from orderedset import OrderedSet

from Utils import attachItem, Logger

log = Logger('AttrTagging')
log.setLevel('INFO')


class CodeDesignError(TypeError):
    """ Error: class is used incorrectly by higher-level code """


class const:
    """ Marker class to denote immutable attrs """


class SectionTitle:
    """ New section marker. Tells ClsdictProxy when new tag is defined.
        Usage (in class body): SECTION('tag_name', [option]) or SECTION['tag_name', [option]]
            (PyCharm highlights square bracket statement nicely :)
        Supported options:
            • 'const' — all attrs in current section will be immutable
                        value may be changed though by accessing '_attrname_slot' attribute (it's Python, babie)
    """

    proxy: ClsdictProxy = None

    def __getitem__(self, tagname: Optional[str], option=None):
        if tagname is None:
            return self.proxy.resetTag()
        elif not isinstance(tagname, str):
            raise ValueError(f"Tag name is not a string: {tagname}")
        elif option is None:
            return self.proxy.setNewTag(tagname.lower())
        elif option is not const:
            raise ValueError(f"Unsupported option: {option}")
        else:
            return self.proxy.setNewTag(tagname.lower(), frozen=True)

    def __call__(self, *args):
        return self.__getitem__(*args)


class AnnotationProxy(dict):

    def __init__(self, clsdictProxy):
        super().__init__()
        self.target = clsdictProxy

    def __setitem__(self, attrname, value):
        log.debug(f'[__annotations__][{attrname}] ◄—— {value}')

        # ▼ Put annotation on its place
        self.target.get('__annotations__')[attrname] = value

        # ▼ Set tag to attr: dunders are ignored; current tag should be defined
        if (not (attrname.startswith('__') and attrname.endswith('__'))
                and self.target.currentTag is not None):
            self.target.tags[self.target.currentTag].add(attrname)


class ClsdictProxy(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set('__tags__', defaultdict(OrderedSet))
        self.set('__annotations__', {})
        self.tags = self.get('__tags__')  # alias for self['__tags__']
        self.spy = AnnotationProxy(self)
        self.currentTag: str = None

    def __getitem__(self, key):
        log.debug(f'[{key}] ——►')
        if key == '__annotations__':
            return self.spy
        else: return super().__getitem__(key)

    def __setitem__(self, key, value):
        log.debug(f'[{key}] ◄—— {value}')
        return super().__setitem__(key, value)

    def set(self, key, value):
        """ __setitem__ for internal use """
        return super().__setitem__(key, value)

    def resetTag(self):
        self.currentTag = None

    def setNewTag(self, tagname, frozen=False):
        if frozen is True: NotImplemented  # TODO: frozen attrs
        # ▼ check for duplicating section
        if tagname in self.tags.keys():
            raise CodeDesignError(f"Section '{tagname}': found duplicate definition")
        self.currentTag = tagname


class TaggedAttrsTitledType(type):
    """ TODO: TaggedAttrsTitledType docstring
        Variables defined without annotations are not tagged
        SECTION without any attrs inside is not created
        Tag names are case-insensitive
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

        return super().__new__(*args)


SECTION = SectionTitle()

# TODO: move all these shortcuts to a separate file (for ex., classtools.py)

TaggedType = TaggedAttrsTitledType

class Tagged(TaggedType): pass


if __name__ == '__main__':
    ...
