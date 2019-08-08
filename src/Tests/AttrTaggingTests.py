from __future__ import annotations
from Utils import formatDict


class TagMeta(type):
    # TODO: make this a singleton
    tagLists = {}

    def __new__(metacls, clsname, bases, clsdict, **kwargs):
        clsdict['__slots__'] = ()
        metacls.tagLists[clsname.lower()] = clsdict
        return object  # this will be garbage collected immediately


class Tag(metaclass=TagMeta): pass


class M(type):
    def __prepare__(name, bases, **kwargs):
        return {'TAG': Tag}

    def __new__(metacls, clsname, bases, clsdict, **kwargs):
        clsdict['__slots__'] = []
        for attr, typeval in clsdict.get('__annotations__', {}).items():
            clsdict['__slots__'].append(attr)
        print(metacls, clsname, bases, clsdict, **kwargs, sep='\n')
        return super().__new__(metacls, clsname, bases, clsdict)


class K(metaclass=M): pass


class TestTags(K):
    a: str
    b: str = 'lol'
    c: str

    class Service(TAG):
        d: list
        e: int = 5

    f: str = 'azaza'

    def __init__(self):
        self.a = 'avar'
        self.c = 'cvar'
        self.d = [1, 2, 3]







if __name__ == '__main__':


    t = TestTags()
    print(f"t.__slots__: {t.__slots__}")
    print(f"t.__annotations__: {t.__annotations__}")
    print(f"Has dict? {hasattr(t, '__dict__')}")
    if hasattr(t, '__dict__'): print(formatDict(t.__dict__))
    print(f"Attrs of t:")
    print(t.a, t.b, t.c, t.d, t.e, t.f)
    print(f"Test.__dict__: {formatDict(TestTags.__dict__)}")
