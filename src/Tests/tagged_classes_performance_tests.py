from __future__ import annotations

from ..Utils import add_slots, Timer
from ..Experiments.attr_tagging import TaggedSlots, SECTION, TaggedAttrsTitledType
from typing import ClassVar, Callable
from timeit import timeit

import attr
from pympler.asizeof import asizeof as size



if __name__ != '__main__':
    with Timer("Class Dict", 100):
        for i in range(10000):
            try: del D
            except: pass

            class D(metaclass=TaggedAttrsTitledType):
                a = 1
                b: int
                c: int = 2
                h: bool = True

                SECTION['service']
                d: ClassVar[str]
                e: ClassVar[str] = 'azaza'

                SECTION['test']

                SECTION['other']
                f: int = 99
                g: str
                i = dir

                def __init__(self, par=''):
                    super().__init__()
                    self.b = par
                    self.g = 'lol'
                    self.__class__.d = 0


if __name__ != '__main__':
    with Timer("Class TaggedSlots", 100):
        for i in range(10000):
            try: del S
            except: pass

            class S(TaggedSlots):
                a = 1
                b: int
                c: int = 2
                h: bool = True

                SECTION['service']
                d: ClassVar[str]
                e: ClassVar[str] = 'azaza'

                SECTION['test']

                SECTION['other']
                f: int = 99
                g: str
                i = dir

                def __init__(self, par=''):
                    super().__init__()
                    self.b = par
                    self.g = 'lol'
                    self.__class__.d = 0


if __name__ != '__main__':
    with Timer("Class NoDefaultsSlots", 100):
        for i in range(10000):
            try: del NS
            except: pass

            class NS(TaggedSlots):
                a = 1
                b: int
                c: int
                h: bool

                SECTION['service']
                d: ClassVar[str]
                e: ClassVar[str] = 'azaza'

                SECTION['test']

                SECTION['other']
                f: int
                g: str
                i = dir

                def __init__(self, par=''):
                    super().__init__()
                    self.b = par
                    self.g = 'lol'
                    self.h = True
                    self.__class__.d = 0


if __name__ != '__main__':
    with Timer("Class SimpleSlots", 100):
        for i in range(10000):
            try: del SS
            except: pass

            class SS:
                __slots__ = ('b', 'c', 'f', 'g', 'h')
                a = 1
                e: str = 'azaza'
                i = dir

                def __init__(self, par=''):
                    super().__init__()
                    self.b = par
                    self.c = 2
                    self.f = 99
                    self.g = 'lol'
                    self.h = True
                    self.__class__.d = 0


if __name__ != '__main__':
    with Timer("Class AddSlots", 100):
        for i in range(10000):
            try: del AS
            except: pass

            @add_slots
            class AS:
                a = 1
                b: int
                c: int
                h: bool

                d: ClassVar[str]
                e: ClassVar[str] = 'azaza'

                f: int
                g: str
                i = dir

                def __init__(self, par=''):
                    object.__init__(self)
                    self.b = par
                    self.c = 2
                    self.f = 99
                    self.g = 'lol'
                    self.h = True
                    self.__class__.d = 0


if __name__ != '__main__':
    with Timer("Class Attr.s", 1000):
        for i in range(1000):
            try: del AT
            except: pass

            @attr.s(slots=True, auto_attribs=True)
            class AT:
                a: int = attr.ib(default=1, init=False)
                b: str
                c: int

                d: ClassVar[str] = 0
                e: ClassVar[str] = 'azaza'

                f: int = attr.ib(init=False)
                g: int

                h: bool
                i: Callable = dir

            def __str__(self):
                return 'azaza'


def main():

    print("\nCreation:")
    print(f"Dict: {timeit(stmt='D()', setup='from tests import D')}")
    print(f"Slots: {timeit(stmt='S()', setup='from tests import S')}")
    print(f"NoDefaultsSlots: {timeit(stmt='NS()', setup='from tests import NS')}")
    print(f"SimpleSlots: {timeit(stmt='SS()', setup='from tests import SS')}")
    print(f"AddSlots: {timeit(stmt='AS()', setup='from tests import AS')}")
    print(f"Attr.s: {timeit(stmt='AT(b=str(), c=2, g=99, h=True)', setup='from tests import AT')}")

    print("\nAccess:")
    print(f"Dict: {timeit(stmt='t.a; t.b; t.c = t.d * t.e; t.f = t.g*10; t.h; t.i()', setup='from tests import D; t = D()')}")
    print(f"Slots: {timeit(stmt='t.a; t.b; t.c = t.d * t.e; t.f = t.g*10; t.h; t.i()', setup='from tests import S; t = S()')}")
    print(f"NoDefaultsSlots: {timeit(stmt='t.a; t.b; t.c = t.d * t.e; t.f = t.g*10; t.h; t.i()', setup='from tests import NS; t = NS()')}")
    print(f"SimpleSlots: {timeit(stmt='t.a; t.b; t.c = t.d * t.e; t.f = t.g*10; t.h; t.i()', setup='from tests import SS; t = SS()')}")
    print(f"AddSlots: {timeit(stmt='t.a; t.b; t.c = t.d * t.e; t.f = t.g*10; t.h; t.i()', setup='from tests import AS; t = AS()')}")
    print(f"Attr.s: {timeit(stmt='t.a; t.b; t.c = t.d * t.e; t.f = t.g*10; t.h; t.i()', setup='from tests import AT; t = AT(b=str(), c=2, g=99, h=True)')}")

    print("\nSize:")
    from tests import D, S, NS, SS, AS, AT
    print(f"Dict: {size(D())}")
    print(f"Slots: {size(S())}")
    print(f"NoDefaultsSlots: {size(NS())}")
    print(f"SimpleSlots: {size(SS())}")
    print(f"AddSlots: {size(AS())}")
    print(f"Attr.s: {size(AT(b=str(), c=2, g=99, h=True))}")

    print(D.__dict__)
    print(D().__dict__)


def test_update_nested_dicts():
    setup = 'from itertools import groupby, chain; r = {}; ' \
            'tags = {1: (1, 2, 3, 4), 2: ("a", "b"), 3: ()}; ' \
            'tags2 = {2: ("c",), 4: (77, 11, 99)}'
    stmt1 = 'l = list(chain(tags.items(), tags2.items()))\n' \
            'for k, g in groupby(sorted(l), lambda item: item[0]): r[k] = tuple(chain.from_iterable((i[1] for i in g)))'
    stmt2 = 'l = list(chain(tags.items(), tags2.items()))\n' \
            'for k, v in l: r[k] = tuple(v) if k not in r else tuple(chain(r[k], v))'
    print(f"1: {timeit(stmt1, setup, number=10000)}")
    print(f"2: {timeit(stmt2, setup, number=10000)}")


if __name__ == '__main__':
    main()
