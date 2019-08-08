from __future__ import annotations

from collections import defaultdict
from functools import partial
from itertools import groupby, chain
from operator import itemgetter, setitem
from typing import Union, Tuple
from orderedset import OrderedSet
from ..Utils import attachItem


class const:
    """ Marker class to denote immutable attrs """

class SectionTitle:
    proxy: ClassdictProxy = None

    def __getitem__(self, tagname: Union[str, Tuple[str, const]], option=None):
        if not isinstance(tagname, str): raise ValueError(f"Tag name is not a string: {tagname}")
        if option is None: return self.proxy.setNewTag(tagname.lower())
        elif option is not const and option != 'const': raise ValueError(f"Unsupported option: {option}")
        else: return self.proxy.setNewTag(tagname.lower(), frozen=True)

    def __call__(self, *args):
        return self.__getitem__(*args)


class AnnotationProxy(dict):

    def __init__(self, clsdictProxy):
        super().__init__()
        self.target = clsdictProxy

    def __setitem__(self, attrname, value):
        self.target.get('__annotations__')[attrname] = value
        if not (attrname.startswith('__') and attrname.endswith('__')) and self.target.currentTag is not None:
            self.target.tags[self.target.currentTag].add(attrname)


class ClassdictProxy(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set('__tags__', defaultdict(OrderedSet))
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

    def setNewTag(self, tagname, frozen=False):
        # TODO: frozen attrs
        self.currentTag = tagname
        self.tags[self.currentTag] = OrderedSet()


class TaggedAttrsTitledType(type):
    """ Variables defined without annotations are not tagged
    """

    __tags__ = {}

    @classmethod
    def __prepare__(metacls, clsname, bases, baseClass=False):
        if not baseClass:
            SECTION.proxy = ClassdictProxy()
            return SECTION.proxy
        else: return {}

    def __new__(metacls, clsname, bases, clsdict, **kwargs):  # TESTME!!!
        args = (metacls, clsname, bases, clsdict)  # CONSIDER: should I explicitly do 'dict(clsdict)' here?

        if hasattr(clsdict, 'tags'):
            # ▼ Use tags that are already in clsdict if no parents found
            if not bases: return super().__new__(*args)

            # ▼ Collect all base class tags dicts + current class tags dict
            tagsDicts = attachItem(filter(None, (parent.__dict__.get('__tags__') for parent in bases)), clsdict.tags)

            # ▼ Take main parent's tags as base tags dict
            try: newTags = clsdict['__tags__'] = tagsDicts.__next__()

            # ▼ Use current tags if no single parent defines any
            except StopIteration: return super().__new__(*args)

            # ▼ Merge all tags by tag name
            for tagsDict in tagsDicts:
                map(partial(setitem, newTags), (tagname, namesSet for tagname, namesSet in tagsDict.items()))

        return super().__new__(*args)


SECTION = SectionTitle()

TaggedType = TaggedAttrsTitledType


if __name__ == '__main__':
    ...
