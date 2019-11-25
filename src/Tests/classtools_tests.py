from __future__ import annotations as annotations_feature

import logging
import re
from typing import ClassVar, Any

import pytest
from orderedset import OrderedSet
from Utils import Logger

from Experiments.attr_tagging_concise import Attr, Classtools, TAG, OPTIONS, attr, tag, lazy, skip, const, kw
from Experiments.attr_tagging_concise import ConstDescriptor, ClasstoolsError, GetterError


log = Logger('Classtools.tests')
log.setLevel('DEBUG')

logging.getLogger('Classtools').disabled = False

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
            with OPTIONS:
                b: int = -8 |tag('test')
            a: int = Attr(-8, tag='test')

        c = C(e=None)
        assert tuple(C.__attrs__.keys()) == ('e', 'd', 'c', 'no_tag', 'b', 'a')
        assert C.__tags__ == {
                None: OrderedSet(('no_tag',)),
                'test': OrderedSet(('e', 'd', 'c', 'b', 'a'))
        }
        assert all((attr.tag == 'test' for attr in C.__attrs__.values() if attr.name != 'no_tag'))

        class C_ERRORS(metaclass=Classtools, slots=True):
            with pytest.raises(TypeError):
                with OPTIONS('wrong syntax'):
                    a: int = 3
            with pytest.raises(TypeError):
                with TAG(tag='wrong syntax'):
                    b: int = 3

    def test_copy(self):
        class ClassCopy():
            def __init__(self, var='var'):
                self.var = var

            def copy(self):
                return self.__class__(self.var)

            def __eq__(self, other):
                if not hasattr(other, 'var'):
                    return False
                return self.__class__ is other.__class__ and self.var == other.var

        class ClassNoCopy():
            def __init__(self, var='var'):
                self.var = var

            def __copy__(self):
                return self.__class__(self.var)

            def __eq__(self, other):
                if not hasattr(other, 'var'):
                    return False
                return self.__class__ is other.__class__ and self.var == other.var

        class K(metaclass=Classtools, slots=True):
            none = 'conventional class variable'
            a: Any = ...
            b: attr = ... |skip
            p: attr = ... |const
            j: attr = ... |lazy('get_j')
            c: attr = [1, 2, 3]
            d: ClassVar[str] = Attr({1: 'a'})
            e: int = 'will be replaced with []'
            f: attr = ClassCopy()
            g: attr = ClassNoCopy()
            h: Any = Attr('replace', tag='tag_h')
            m: attr = {} |tag('max options') |lazy('get_m') |const |kw
            n: ClassVar[list] = []
            def get_m(self): return ['m_value']
            def get_j(self): return ['j_value']

        k = K(a='a', p='p', e=[], h=ClassCopy())
        kk = K(a='a', p='p', e=[], h=ClassCopy())

        assert k.a == kk.a == 'a'

        assert k.p == kk.p == 'p'
        with pytest.raises(AttributeError): k.p = 2

        assert k.j == kk.j == ['j_value']
        assert k.j is not kk.j

        assert k.c == kk.c == K['c'].default == [1, 2, 3]
        assert k.c is not kk.c and k.c is not K['c'].default and kk.c is not K['c'].default
        k.c = [1]
        kk.c = [2]
        assert k.c != kk.c != K['c'].default

        assert k.d is kk.d is K['d'].default

        assert k.e == kk.e == []
        assert k.e is not kk.e and k.e is not [] and kk.e is not []
        k.e = {}
        kk.e = set()
        assert k.e != kk.e != []

        assert k.f == kk.f == K['f'].default == ClassCopy()
        assert k.f is not kk.f and k.f is not ClassCopy() and kk.f is not ClassCopy()
        k.f = ClassCopy('k_var')
        kk.f = ClassCopy('kk_var')
        assert k.f != kk.f != K['f'].default

        assert k.g == kk.g == K['g'].default == ClassNoCopy()
        assert k.g is kk.g and k.g is not ClassNoCopy() and kk.g is not ClassNoCopy()

        assert k.h is not kk.h
        k.h = ClassCopy()
        assert k.h is not kk.h
        k.h = ClassCopy('other')
        assert k.h != kk.h

        assert k.m is not kk.m
        assert k.n is kk.n

    def test_skip(self):
        class D(metaclass=Classtools, slots=True):
            none = 'conventional class variable'
            k: attr = ... |skip
            b: attr
            d: int = 1 |skip
            e: attr = 8 /skip
            f: Any = 'f'
            g: attr = Attr('replace', skip=None)

        d = D('b', e='e', g='g')

        with pytest.raises(AttributeError, match=re.escape('')): d.k
        d.k = 'k'
        assert d.k == 'k'
        assert d.b == 'b'
        assert d.d == 1
        assert d.e == 'e'
        assert d.f == 'f'
        assert d.g == 'g'

        with pytest.raises(ClasstoolsError,
                           match=re.escape("ClassAttr 'a' has incompatible options: |skip")):
            class D_ERROR_CLASSVAR_SKIP(metaclass=Classtools, slots=True):
                a: ClassVar[str] = Attr('a', skip=1)

    def test_const(self):
        class E(metaclass=Classtools, slots=True):
            none = 'conventional class variable'
            a: Any = ...
            b: bool = ... |const |skip
            c: attr
            d: ClassVar[str] = Attr('d', tag=None)
            e: int = 1 |const
            with OPTIONS |const:
                f: attr = 8
                g: bool = True /const
            h: Any = Attr('replace', const=True)

        e = E(a='a', c='c', h='h')

        consts = ('b', 'e', 'f', 'h')

        for name, attr in E.__attrs__.items():
            if name in consts: assert attr.const is True, name
            else: assert attr.const is False, name
        assert set(consts) & set(e.__slots__) == set()

        assert hasattr(E, 'e')
        assert isinstance(E.e, ConstDescriptor)
        assert e.e == 1
        with pytest.raises(AttributeError, match=re.escape("Attr 'e' is declared constant")):
            e.e = 4

        assert hasattr(E, 'b')
        assert isinstance(E.b, ConstDescriptor)
        with pytest.raises(AttributeError, match=re.escape("b_slot")):
            e.b
        e.b = 3
        assert isinstance(E.b, ConstDescriptor)
        assert e.b == 3
        with pytest.raises(AttributeError, match=re.escape("Attr 'b' is declared constant")):
            e.b = 'will fail'

    def test_lazy(self):
        class F(metaclass=Classtools, slots=True):
            none = 'conventional class variable'
            a: Any = ...
            b: attr = 0 |lazy('get_b')
            c: attr = 1 |lazy('get_c')
            d: ClassVar[str] = Attr('d', lazy=False)
            e: int = 1 |lazy('get_e') |skip
            with OPTIONS |lazy('get_section'):
                f: attr = 8
                g: bool = True /lazy
            h: Any = Attr('replace', lazy='get_h')
            k: attr = ... |lazy('get_k') |const
            m: attr = () |lazy('get_m') |const |skip
            n: ClassVar[tuple] = () /lazy('dont_care')

            def get_b(self): raise GetterError
            def get_c(self): return 'c_value'
            def get_section(self): return 'section_value'
            def get_e(self): raise GetterError
            def get_h(self): return 'h_value'
            def get_k(self): return 'k_value'
            def get_m(self): return ('m_value', )*3

        f = F(a='a')

        lazies = ('c', 'b', 'e', 'f', 'h', 'k', 'm')

        for name, attr in F.__attrs__.items():
            if name in lazies: assert isinstance(attr.lazy, str), name
            else: assert attr.lazy is False, name
        for name in lazies[:-2]:  # 'k' and 'm' are not in __slots__ <= they are |const
            assert name in f.__slots__, name

        assert F['a'].lazy is False
        assert f.a == 'a'

        with pytest.raises(AttributeError, match=re.escape('')):
            F.c.__get__(f, F)
        assert f.c == 'c_value'

        assert f.e == 1
        assert f.b == 0

        assert f.f == 'section_value'
        assert f.g is True
        assert f.h == 'h_value'

        assert hasattr(F, 'k_slot')
        with pytest.raises(AttributeError): f.k_slot
        assert f.k == 'k_value'
        assert f.k_slot == 'k_value'
        with pytest.raises(AttributeError, match=re.escape("Attr 'k' is declared constant")):
            f.k = 'will fail'
        assert f.k == 'k_value'

        assert f.m == ('m_value', )*3
        assert f.m is f.m_slot

        with pytest.raises(ClasstoolsError,
                           match=re.escape("ClassAttr 'a' has incompatible options: |const, |lazy")):
            class F_CONST_ERROR(metaclass=Classtools, slots=True):
                a: ClassVar[int] = -1 |lazy('get_n') |const

    def test_tag(self):
        class G(metaclass=Classtools, slots=True):
            none = 'conventional class variable'
            a: Any = ...
            b: attr = ... |tag(object) |skip
            k: attr = ... |tag('tag_k') |const
            c: attr = 1 |tag('tag_c')
            d: ClassVar[str] = Attr('b', tag=None)
            e: int = 1 |tag('tag_e') |skip
            with TAG('tag_section'):
                f: attr = 8
                g: bool = True /tag
            h: Any = Attr('replace', tag='tag_h')
            m: attr = () |tag('tag_m') |lazy('get_m') |const |skip
            n: ClassVar[tuple] = () /tag('dont_care')

            def get_m(self): return 'm_value'

        g = G(a='a', k='k')
        tags = ('b', 'c', 'e', 'f', 'h', 'k', 'm')

        for name, attr in G.__attrs__.items():
            if name == 'b': assert attr.tag is object
            elif name == 'f': assert attr.tag == 'tag_section'
            elif name in tags: assert attr.tag == f'tag_{name}', name
            else: assert attr.tag is None, name
        for name in tags[:-2]:  # 'k' and 'm' are not in __slots__ <= they are |const
            assert name in g.__slots__, name

        assert G.__tags__ == {
                None: OrderedSet(('a', 'd', 'g', 'n')),
                object: OrderedSet(('b',)),
                'tag_k': OrderedSet(('k',)),
                'tag_c': OrderedSet(('c',)),
                'tag_e': OrderedSet(('e',)),
                'tag_section': OrderedSet(('f',)),
                'tag_h': OrderedSet(('h',)),
                'tag_m': OrderedSet(('m',)),
        }

    def test_kw(self):
        class H(metaclass=Classtools, slots=True):
            none = 'conventional class variable'
            a: Any = ...
            b: attr = ... |kw
            e: ClassVar[str] = Attr('e_classvar', kw=False)
            f: int = 1 /kw |skip
            with OPTIONS(kw=True):
                g: attr = 8
                h: bool = True /kw
            k: Any = Attr('replace', tag='tag_h')
            m: attr = () |tag('tag_m') |lazy('get_m') |const |skip
            n: ClassVar[ClassVar] = 'n_classvar'

            def get_m(self): return 'm_value'

        h = H('a', 'h', b='b')
        assert (h.a, h.b, h.h) == ('a', 'b', 'h')

        h2 = H('a', 'h', 'k', b='b', g='g')
        assert (h2.a, h2.b, h2.e, h2.f, h2.g, h2.h, h2.k, h2.m, h2.n) == \
               ('a', 'b', 'e_classvar', 1, 'g', 'h', 'k', 'm_value', 'n_classvar')

        assert H['k'].tag == 'tag_h'

        with pytest.raises(AttributeError, match=re.escape("Attr 'm' is declared constant")):
            h2.m = 5
        assert h2.m_slot == 'm_value'
        assert H['m'].tag == 'tag_m'

        with pytest.raises(TypeError,
                           match=re.escape("__init__() missing 1 required keyword-only argument: 'b'")):
            fail = H('a', 'b')

        with pytest.raises(ClasstoolsError,
                           match=re.escape("Attr 'a' has incompatible options: |kw")):
            class H_KW_CLASSVAR_ERROR(metaclass=Classtools, slots=True):
                a: ClassVar = 1 |kw

        with pytest.raises(ClasstoolsError,
                           match=re.escape("Attr cannot have both '|skip' and '|kw' options set")):
            class H_SKIPPED_KW_ATTR_ERROR(metaclass=Classtools, slots=True):
                a: attr = ... |kw |skip

    def test_option_syntax(self):
        class J_ERRORS(metaclass=Classtools, slots=True):
            with pytest.raises(ClasstoolsError,
                               match=re.escape("Option '|const' takes no arguments")):
                a: attr = 1 |const('arg')
            with pytest.raises(ClasstoolsError,
                               match=re.escape("Duplicate option '|const' - was already set to 'False'")):
                b: attr = ... /const |const
            with pytest.raises(ClasstoolsError,
                               match=re.escape("Option '|lazy' requires an argument")):
                c: attr = ... |lazy

    def test_no_init(self):
        class M(metaclass=Classtools, slots=True, init=False):

            none = 'conventional class variable'
            a: Any = ...
            b: attr = ... |skip
            p: attr = ... |const
            j: attr = ... |lazy('get_j')
            c: attr = [1, 2, 3]
            d: ClassVar[str] = {1: 'a'}
            e: str = 'e'
            f: attr = Attr() |kw
            g: attr = 'g' |kw
            h: Any = Attr(42, tag='tag_h')
            m: attr = {} |tag('max options') |lazy('get_m') |const |kw
            n: ClassVar[list] = []
            def get_m(self): return 'm_value'
            def get_j(self): return 'j_value'

        m = M()
        checkAttrs = tuple(name for name, attr in M.__attrs__.items() if attr.lazy is False and attr.classvar is False)
        print(checkAttrs)
        for name in checkAttrs:
            with pytest.raises(AttributeError): getattr(m, name)
        assert m.d == {1: 'a'}
        assert m.j == 'j_value'



    # def test_option_apply_order(self):
    #     ...
