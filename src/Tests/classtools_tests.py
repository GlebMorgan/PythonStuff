from __future__ import annotations as annotations_feature

from typing import ClassVar, Callable

from ..Experiments.attr_tagging import *
import unittest
from orderedset import OrderedSet
from attr import attrs, attr


def clsdict(**kwargs):
    d = defaultdict(OrderedSet, **kwargs)
    for tag, namesSet in d.items():
        d[tag] = OrderedSet(namesSet)
    return d

def test(a): return f'{a} keks'

@unittest.skip("Old attrs-related tests")
class Test_TaggedType_with_attrs(unittest.TestCase):


    @attrs(auto_attribs=True)
    class ConvClass(metaclass=TaggedType):
        i = 'no ann'
        a: int
        b: str = 5

        SECTION('test')
        c: bool = False
        d = 8

        SECTION('empty')

        def __str__(self):
            return super().__str__() + ' [test]'

    def test_conv(self):
        c = self.ConvClass(a=0)
        self.assertEqual(self.ConvClass.__tags__, clsdict(test=('c', 'd'), empty=()))
        self.assertEqual(self.ConvClass.__annotations__, dict(a='int', b='str', c='bool'))
        self.assertEqual(c.a, 0)
        self.assertEqual(c.i, 'no ann')

    @attrs(auto_attribs=True, slots=True)
    class SlotsClass(metaclass=TaggedType):
        i = 'no ann'
        a: int
        b: str = 5

        SECTION('test')
        c: bool = False
        d = 8

        SECTION('empty')

        def __str__(self):
            return super().__str__() + ' [test]'

    def test_slots(self):
        s = self.SlotsClass(a=0)
        self.assertEqual(self.ConvClass.__tags__, clsdict(test=('c', 'd'), empty=()))
        self.assertEqual(self.ConvClass.__annotations__, dict(a='int', b='str', c='bool'))
        self.assertEqual(s.a, 0)
        self.assertEqual(s.i, 'no ann')

    @attrs(auto_attribs=True, slots=True)
    class BaseClass(metaclass=TaggedType):
        class Nested: pass

        i = 'no ann'
        a: int
        b: str = 5

        SECTION('test')
        c: bool = False
        d = 8

        SECTION('empty')

        def __str__(self):
            return super().__str__() + ' [test]'

        def m(self): print(f"{self.__name__} method")

    @attrs(auto_attribs=True, slots=True)
    class ChildClass(BaseClass):
        j = 'no ann'
        e: int = None
        f: str = 5

        SECTION('test')
        g: bool = False
        _h = 8

        SECTION('empty')
        k: Test_TaggedType_with_attrs.BaseClass.Nested = None

        def __str__(self):
            return super().__str__() + ' [test]'

    def test_inheritance(self):
        ch = self.ChildClass(a=0, e=99)
        self.assertTrue(hasattr(ch, '__slots__'))
        self.assertFalse(hasattr(ch, '__dict__'))
        self.assertEqual(ch.__class__.__tags__, clsdict(test=('c', 'd', 'g', '_h'), empty=('k',)))
        self.assertEqual(ch.__class__.__annotations__, dict(e='int', f='str', g='bool', k=ch.Nested.__qualname__))


    class NameConflict(BaseClass):
        b: str = 7

        SECTION('test')
        c: bool = True

    def test_name_conflict(self):
        nc = self.NameConflict(a=0)
        self.assertEqual(nc.__class__.__tags__, clsdict(test=('c', 'd')))
        self.assertEqual(nc.__class__.__annotations__, dict(c='bool'))
        self.assertEqual(nc.c, True)


class Test_AttrTagging(unittest.TestCase):

    log.setLevel('INFO')  # set this to 'DEBUG' to debug classDict manipulations

    class Tagged(metaclass=TaggedType):
        class Nested: pass

        i = 'no ann i'
        a: int
        b: str = 5

        SECTION('test')
        c: bool = False
        d = clsdict

        class ShouldNotTag(Nested): pass

        SECTION('empty')

        def m(self): print(f"{self.__name__} method")

        print(d.__qualname__)
        print(m.__qualname__)


        def __str__(self):
            return super().__str__() + ' [test]'

    log.setLevel('INFO')

    def test_tagging(self):
        c = self.Tagged()
        self.assertEqual(self.Tagged.__tags__, clsdict(test=('c', 'd')))
        self.assertEqual(self.Tagged.__annotations__, dict(a='int', b='str', c='bool'))
        self.assertFalse(any('m' in tags for tags in Tagged.__tags__.values()))
        self.assertFalse('ShouldNotTag' in Tagged.__tags__.values())
        self.assertIn('i', self.Tagged.__dict__)
        self.assertIn('d', self.Tagged.__dict__)
        self.assertIn('m', self.Tagged.__dict__)
        self.assertTrue(hasattr(self.Tagged, 'Nested'))
        self.assertFalse(hasattr(c, 'a'))
        self.assertEqual(c.b, 5)
        self.assertEqual(c.i, 'no ann i')


    class ChildTagged(Tagged):
        j = 'no ann j'
        e: int = None
        f: str = 5
        tuple()  # just for ClsdictProxy tests

        SECTION('test')
        g: bool = False
        _h: int = 8  # make this alphabetically preceding
        h = 8

        SECTION('empty')
        k: Test_AttrTagging.Tagged.Nested = None

        SECTION('new')
        m: str  # overrides method
        n: str = 'bla'

    def test_inheritance(self):
        ch = self.ChildTagged()
        self.assertEqual(self.ChildTagged.__tags__, clsdict(test=('c', 'd', 'g', '_h', 'h'), empty=('k',), new=('m', 'n')))
        self.assertEqual(self.ChildTagged.__annotations__, dict(
                e='int', f='str', g='bool', _h='int', k='Test_AttrTagging.Tagged.Nested', m='str', n='str'))
        self.assertTrue(hasattr(self.ChildTagged, 'Nested'))
        self.assertEqual(self.ChildTagged.h, 8)
        self.assertFalse(hasattr(ch, 'a'))
        self.assertEqual(ch.n, 'bla')
        self.assertEqual(ch.i, 'no ann i')
        self.assertEqual(ch.j, 'no ann j')


    class OverridingChild(ChildTagged):
        e: int = 42  # overrides direct parent
        b: int = 33  # overrides grandparent

        SECTION['test']  # use another syntax; also override tag completely
        g: float = 1.1  # overrides direct parent
        c: float = 3.3  # overrides grandparent

        SECTION['new']
        m: str = "lol"  # value didn't exist earlier

        SECTION['override_class_var']
        f: str = 'ovrd_var'
        o: str = 'new_var'

    def test_overrides(self):
        o = self.OverridingChild()
        self.assertEqual(self.OverridingChild.__tags__,
                clsdict(test=('c', 'd', 'g', '_h', 'h'), empty=('k',), new=('m', 'n'), override_class_var=('f', 'o')))
        self.assertEqual(self.OverridingChild.__annotations__, dict(
                e='int', b='int', g='float', c='float', m='str', f='str', o='str'))
        self.assertEqual(o.f, 'ovrd_var')
        self.assertEqual(o.e, 42)
        self.assertEqual(o.b, 33)
        self.assertAlmostEqual(o.g, 1.1)
        self.assertAlmostEqual(o.c, 3.3)
        self.assertEqual(o.m, 'lol')
        self.assertEqual(o.f, 'ovrd_var')
        self.assertEqual(o.o, 'new_var')


    class SecondParent(metaclass=TaggedType):
        p: ClassVar[str] = 'new_cls_var'
        b: int = 77  # overrides b
        q = list  # new class var

        SECTION('test')
        g: bool = True  # overrides g
        r: int = -3  # new
        s: int = -100  # one more new

        SECTION('secondparent')
        t: bool = True
        t: int = 4   # should just overwrite
        u: str = 'kek'

        SECTION('empty')
        k: Test_AttrTagging.Tagged.Nested = ...  # same annotation

        SECTION('big')
        v: int
        w: int
        x: int
        y: int
        z: int

    class MultipleInheritanceEmptyChild(SecondParent, ChildTagged): pass

    def test_multiple_inheritance_simple(self):
        me = self.MultipleInheritanceEmptyChild()
        self.assertEqual(self.MultipleInheritanceEmptyChild.__tags__, clsdict(
                test=('g', 'r', 's', 'c', 'd', '_h', 'h'), empty=('k',), new=('m', 'n'),
                secondparent=('t', 'u'), big=('v', 'w', 'x', 'y', 'z')))
        self.assertEqual(self.MultipleInheritanceEmptyChild.__annotations__, {})
        self.assertTrue(hasattr(self.MultipleInheritanceEmptyChild, 'Nested'))
        self.assertFalse(hasattr(me, 'a'))

        self.assertEqual(me.i, 'no ann i')
        self.assertEqual(me.b, 77)
        self.assertEqual(me.c, False)
        self.assertTrue(isinstance(me.m, Callable))
        self.assertEqual(me.j, 'no ann j')
        self.assertEqual(me.e, None)
        self.assertEqual(me.f, 5)
        self.assertEqual(me.g, True)
        self.assertEqual(me._h, 8)
        self.assertEqual(me.h, 8)
        self.assertEqual(me.n, 'bla')
        self.assertEqual(me.p, 'new_cls_var')
        self.assertEqual(me.q, list)
        self.assertEqual(me.r, -3)
        self.assertEqual(me.s, -100)
        self.assertEqual(me.t, 4)
        self.assertEqual(me.u, 'kek')
        self.assertEqual(me.k, ...)

    class MultipleInheritanceChild(SecondParent, ChildTagged):
        # no untagged attrs here

        SECTION('test')
        c: int = 999
        g: ClassVar = 'g_is_now_ClassVar'  # overrides SecondParent
        l = 'azaza'

        SECTION('new_in_mult_inheritance')
        m1 = 'm1v'
        m2 = 'm2v'

        SECTION('big')  # no additions, should not delete tag

    @unittest.skip
    def test_multiple_inheritance_extended(self):
        m = self.MultipleInheritanceChild()
        self.assertEqual(self.MultipleInheritanceEmptyChild.__tags__, clsdict(
                test=('g', 'r', 's', 'c', '_h', 'l'), empty=('k',), new=('m', 'n'),
                secondparent=('t', 'u'), big=('v', 'w', 'x', 'y', 'z'), new_in_mult_inheritance=('m1', 'm2')))
        self.assertEqual(self.MultipleInheritanceEmptyChild.__annotations__, dict(c='int', g='ClassVar'))
        self.assertTrue(hasattr(self.MultipleInheritanceEmptyChild, 'Nested'))
        self.assertFalse(hasattr(m, 'a'))

        self.assertEqual(m.i, 'no ann i')
        self.assertEqual(m.b, 77)
        self.assertEqual(m.c, 999)
        self.assertTrue(isinstance(m.m, Callable))
        self.assertEqual(m.j, 'no ann j')
        self.assertEqual(m.e, None)
        self.assertEqual(m.f, 5)
        self.assertEqual(m.g, 'g_is_now_ClassVar')
        self.assertEqual(m._h, 8)
        self.assertEqual(m.h, 8)
        self.assertEqual(m.n, 'bla')
        self.assertEqual(m.p, 'new_cls_var')
        self.assertEqual(m.q, list)
        self.assertEqual(m.r, -3)
        self.assertEqual(m.s, -100)
        self.assertEqual(m.t, 4)
        self.assertEqual(m.u, 'kek')
        self.assertEqual(m.k, ...)
        self.assertEqual(m.l, 'azaza')
        self.assertEqual(m.m1, 'm1v')
        self.assertEqual(m.m2, 'm2v')

    def test_multiple_inheritance_trivial(self):
        class A(metaclass=TaggedType):
            p = '3'
            SECTION('test')
            a: int = 1
            b: int = 2
            c: int = 3

        class B(metaclass=TaggedType):
            p = '4'
            SECTION('test')
            a: int = 4
            b: int = 5
            d: int = 6

        class C(A, B):
            SECTION('test')
            e: int = 7

        c = C()

        self.assertEqual(C.__tags__, clsdict(test=('a', 'b', 'c', 'd', 'e')))
        self.assertEqual(c.p, '3')
        self.assertEqual(c.a, 1)
        self.assertEqual(c.b, 2)
        self.assertEqual(c.c, 3)
        self.assertEqual(c.d, 6)
        self.assertEqual(c.e, 7)

    def test_duplicate_section_definitions(self):
        with self.assertRaises(CodeDesignError, msg="Section 's': found duplicate definition"):
            class DuplicateSectionsDefinitions(metaclass=TaggedType):
                a = 4

                SECTION('s')
                b: int = 5
                c: int = 4

                SECTION('p')
                d: str = 'aaa'

                SECTION('s')
                e: int = 99

            DuplicateSectionsDefinitions()

    def test_reset_tag(self):
        class ResetTag(metaclass=TaggedType):
            a: int
            SECTION('smth')
            b: str = 'gg'
            c: str = 'lol'
            SECTION('other')
            d: int = 0
            SECTION(None)
            e: str = 'pp'

        r = ResetTag()
        self.assertEqual(ResetTag.__tags__, clsdict(smth=('b', 'c'), other=('d',)))
        self.assertFalse(any('e' in tags for tags in ResetTag.__tags__.values()))
        self.assertEqual(r.e, 'pp')


class Test_NewTaggedAttrs(unittest.TestCase):

    def test_basic(self):
        ...


if __name__ == '__main__':
    unittest.main()
    # import dataclasses
