from __future__ import annotations as annotations_feature

from typing import ClassVar, Any

import pytest
from orderedset import OrderedSet
from Utils import Logger

from Experiments.attr_tagging_concise import Attr, Classtools, TAG, OPTIONS, attr, tag, lazy, skip, const, kw


log = Logger('Classtools.tests')
log.setLevel('DEBUG')


class TestSlots:
    def test_annotations(self):
        class A(metaclass=Classtools, slots=True):
            none = 'conventional class variable'
            a: int = 1
            b: ClassVar = 'b'
            c: ClassVar[str] = 'c'
            d: attr = 'd'
            e: Any = 'e'
        a = A()
        assert not hasattr(a, '__dict__')
        assert a.__slots__ == ('a', 'd', 'e')
        assert a.__annotations__ == dict(a='int', b='ClassVar', c='ClassVar[str]', e='Any')

    def test_init(self):
        class B(metaclass=Classtools, slots=True):
            b: int
            a: int = 10
            c: str = 'c'
            d: ClassVar = 'd'
            def init(self, e=-1): self.a += e

        b1 = B(42)
        assert (b1.a, b1.b, b1.c, b1.d) == (9, 42, 'c', 'd')

        b2 = B(77, c='test', e=3)
        assert (b2.a, b2.b, b2.c, b2.d) == (13, 77, 'test', 'd')

    def test_section(self):
        class C(metaclass=Classtools, slots=True):
            with OPTIONS(tag='test'):
                e: int
            with TAG('test'):
                d: attr = None
            with OPTIONS |tag('test'):
                c: tuple = (1, 2, 3)
            no_tag: attr = 1
            b: int = -8 |tag('test')
            a: int = Attr(-8, tag='test')

        c = C(e=None)
        assert tuple(C.__attrs__.keys()) == ('e', 'd', 'c', 'no_tag', 'b', 'a')
        assert C.__tags__ == {
                None: OrderedSet(('no_tag',)),
                'test': OrderedSet(('e', 'd', 'c', 'b', 'a'))
        }
        assert all((attr.tag == 'test' for attr in C.__attrs__.values() if attr.name != 'no_tag'))

    # def test_copy(self):
    #     ...

    def test_skip(self):
        class D(metaclass=Classtools, slots=True):
            none = 'conventional class variable'
            a: ClassVar = Attr(skip=True)
            c: attr
            b: ClassVar[str] = Attr('b', skip=1)
            d: int = 1 |skip
            e: Any = 'e'

        d = D(c='c')
        assert d.c == 'c'
        assert d.d == 1
        assert d.e == 'e'

        class D1(metaclass=Classtools, slots=True):
            with pytest.raises(TypeError):
                with OPTIONS('wrong syntax'):
                    a: int = 3
            with pytest.raises(TypeError):
                with TAG(tag='wrong syntax'):
                    b: int = 3


