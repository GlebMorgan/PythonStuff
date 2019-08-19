from collections import defaultdict

from orderedset._orderedset import OrderedSet
from src.Utils import auto_repr


class ClassDictProxy(dict):

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

class Attr:
    """ Options must have bool values (no 'None's or whatever) """

    __slots__ = 'name', 'default', 'type', 'tag', 'const', 'lazy'

    def __str__(self):
        return f"Attr '{self.name}' [{self.default}] <{self.type}> ⚑{self.tag}" \
               f"{' 🔒'*self.const}{' 🕓'*self.lazy}"

    def __repr__(self): auto_repr(self, self.name)


class OptionBroadcaster:
    def __enter__(self): pass

    def __exit__(self, *args): pass


options = OptionBroadcaster()



if __name__ == '__main__':

    from contextlib import contextmanager

    @contextmanager
    def TAG(tag):
        print(f"tag is {tag}")
        yield
        print(f"cleared tag {tag}")

    @contextmanager
    def options(): yield

    class Const:
        def __rrshift__(self, other): return other
        def __lt__(self, other):  return other
        def __rmatmul__(self, other):  return other
        def __matmul__(self, other):  return self
        def __ror__(self, other):  return other
        def __or__(self, other):  return self
        def __call__(self, *args, **kwargs): return self

    const = Const()
    lazy = Const()
    tag = Const()

    class T:
        a = 1
        b = 2

        with TAG('x') |const |lazy:
            c: int = 5
            d: int = 7 |const |lazy

        with options |tag('test') |const :
            e = 8
            f = 9

    print(dir(T()))
