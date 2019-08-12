from __future__ import annotations as annotations_feature
from ..Experiments.attrs_tools import *
import unittest
from orderedset import OrderedSet
from attr import attrs, attr

# TODO: define how to verify that user-side code executes 'from __future__ import annotations'


class Test_TaggedType_with_attrs(unittest.TestCase):

    @staticmethod
    def clsdict(**kwargs):
        d = defaultdict(OrderedSet, **kwargs)
        for tag, namesSet in d.items():
            d[tag] = OrderedSet(namesSet)
        return d

    @attrs(auto_attribs=True)
    class ConvClass(metaclass=TaggedType):
        i = 'no ann'
        a: int
        b: str = 5

        SECTION('test', const)
        c: bool = False
        d = 8

        SECTION('empty')

        def __str__(self):
            return super().__str__() + ' [test]'

    def test_conv(self):
        c = self.ConvClass(a=0)
        self.assertEqual(self.ConvClass.__tags__, self.clsdict(test=('c',), empty=()))
        self.assertEqual(self.ConvClass.__annotations__, dict(a='int', b='str', c='bool'))
        self.assertEqual(c.a, 0)
        self.assertEqual(c.i, 'no ann')

    @attrs(auto_attribs=True, slots=True)
    class SlotsClass(metaclass=TaggedType):
        i = 'no ann'
        a: int
        b: str = 5

        SECTION('test', const)
        c: bool = False
        d = 8

        SECTION('empty')

        def __str__(self):
            return super().__str__() + ' [test]'

    def test_slots(self):
        s = self.SlotsClass(a=0)
        self.assertEqual(self.ConvClass.__tags__, self.clsdict(test=('c',), empty=()))
        self.assertEqual(self.ConvClass.__annotations__, dict(a='int', b='str', c='bool'))
        self.assertEqual(s.a, 0)
        self.assertEqual(s.i, 'no ann')

    @attrs(auto_attribs=True, slots=True)
    class BaseClass(metaclass=TaggedType):
        class Nested: pass

        i = 'no ann'
        a: int
        b: str = 5

        SECTION('test', const)
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

        SECTION('test', const)
        g: bool = False
        _h = 8

        SECTION('empty')
        k: Test_TaggedType_with_attrs.BaseClass.Nested = None

        # print(Nested)  # CONSIDER: modify classdict so that outer scope variables/classes will be visible here

        def __str__(self):
            return super().__str__() + ' [test]'

    def test_inheritance(self):
        ch = self.ChildClass(a=0, e=99)
        self.assertTrue(hasattr(ch, '__slots__'))
        self.assertFalse(hasattr(ch, '__dict__'))
        self.assertEqual(ch.__class__.__tags__, self.clsdict(test=('c', 'g'), empty=('k',)))
        self.assertEqual(ch.__class__.__annotations__, dict(e='int', f='str', g='bool', k=ch.Nested.__qualname__))


    class NameConflict(BaseClass):
        b: str = 7

        SECTION('test')
        c: bool = True

    def test_name_conflict(self):
        nc = self.NameConflict(a=0)

    # FIXME: STOPPED HERE: finish with these ▲ tests


if __name__ == '__main__':
    unittest.main()
