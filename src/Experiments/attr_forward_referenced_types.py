from __future__ import annotations as annotations_feature

import typing
from types import CodeType
from typing import Union, Optional, ClassVar, Any, TypeVar, Generic, _Protocol
from typing import Collection, Callable, Dict, Tuple, List, Type, MutableMapping
from typing import _GenericAlias as GenericAlias
from typing import _SpecialForm as SpecialForm
from typing import ForwardRef

from Utils import auto_repr, Null


class TypeDescriptor:
    def __get__(self, instance, owner):
        if instance is None: return self

        try:
            return instance._type_var_
        except AttributeError: pass

        typestr = instance._type_str_

        if typestr == '':  # TODO: EMPTY_ANNOTATION
            instance._type_var_ = object
        else:
            try:
                typevar = eval(typestr, globals(), vars(typing))
            except NameError as e:
                raise RuntimeError(f"Cannot resolve type '{typestr}' - {e}")
            except SyntaxError as e:
                raise RuntimeError(f"Cannot evaluate annotation '{typestr}' - {e}")

            if typevar.__class__ is SpecialForm:
                instance._type_var_ = object

            else:
                while True:
                    if typevar.__class__ is GenericAlias:
                        if typevar.__origin__ is Union:
                            typevar = typevar.__args__
                        elif typevar.__origin__ is ClassVar:
                            typevar = typevar.__args__[0]
                        else:
                            instance._type_var_ = typevar.__origin__
                            break
                    else:
                        instance._type_var_ = typevar
                        break
        return instance._type_var_

    def __set__(self, instance, value):
        if instance is None:
            return self
        if not isinstance(value, str):
            raise RuntimeError(f"Type must be a string, got {value}")
        del instance._type_var_
        instance._type_str_ = value


class OldAttr:
    name: str
    type = TypeDescriptor()
    _type_var_: Union[type, Collection[type]]
    _type_str_: str

    def __init__(self, name, type):
        self.name = name
        self._type_str_ = type

    def __repr__(self):
        return auto_repr(self, self.name)


def test_old_FRef():
    import pytest
    import re

    a = OldAttr('a', 'Test')
    with pytest.raises(RuntimeError, match=re.escape("Cannot resolve type 'Test'")):
        print(a.type)

    class Test():  # will not get to globals()
        pass

    globals().update(Test=Test)
    assert a.type is Test

    res = OldAttr('b', 'Any').type
    assert res is object, res

    res = OldAttr('c', 'object').type
    assert res is object, res

    res = OldAttr('d', 'int').type
    assert res is int, res

    res = OldAttr('e', 'Union').type
    assert res is object, res

    res = OldAttr('f', 'Union[tuple]').type
    assert res is tuple, res

    res = OldAttr('g', 'Union[str, list]').type
    assert res == (str, list), res

    res = OldAttr('h', 'Union[str, Any]').type
    assert res == (str, object), res  # BUG

    res = OldAttr('i', 'Union[Union[bool, int], str, int]').type
    assert res == (bool, int, str), res

    res = OldAttr('j', 'Optional[str]').type
    assert res == (str, type(None)), res

    res = OldAttr('k', 'Callable').type
    assert res is Callable, res

    res = OldAttr('l', 'type').type
    assert res is type, res

    res = OldAttr('m', 'Attr').type
    assert res is OldAttr, res

    res = OldAttr('n', 'ClassVar[float]').type
    assert res is float, res

    res = OldAttr('p', 'ClassVar[Optional[Union[int, Union[int, type(3), int("1").__class__], int]]]').type
    assert res == (int, type(None)), res

    res = OldAttr('q', 'Tuple[int, ...]').type
    assert res is tuple, res

    res = OldAttr('r', 'Dict[Union[str, int], Tuple[Optional[bool], Optional[float], Optional[str]]]').type
    assert res is dict, res

    with pytest.raises(RuntimeError, match=re.escape("Cannot evaluate annotation ' '")):
        res = OldAttr('y', ' ').type

    with pytest.raises(RuntimeError, match=re.escape("Cannot resolve type 'Error'")):
        res = OldAttr('z', 'Error').type


# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #


EMPTY_ANNOTATION = ''


class AttrTypeDescriptor:
    """ Get attr typespec form its annotation

        • 'typespec' is a type / tuple of types, which are valid
            for the owner variable according to its annotation
        • 'annotation' is type or GenericAlias object that is
            acquired by evaluating annotation string

        'typespec' and 'annotation' attributes are assigned to an owner Attr object
            attributes, provided in constructor.
    """
    __slots__ = '_code_', 'typeSlot', 'annotationSlot'

    def __init__(self, typeSlot: str, annotationSlot: str):
        self.typeSlot: str = typeSlot
        self.annotationSlot: str = annotationSlot
        # Compiled annotation expressions cache
        self._code_: Dict[Attr, CodeType] = {}

    def parse(self, attr: Attr, annotation: str = Null, *, strict: bool = False):
        """ Parse annotation string and set generated typespec to attr's `.typeSlot` attribute
                and evaluated annotation - to `.annotationSlot`

            'strict' - defines what to do in case of name resolution failure during annotation evaluation
                       True - raise NameError (used in postponed type evaluation)
                       False - cache annotation expression code and exit (used in Attr initialization)

            If 'annotation' is not provided, it is considered to be stored in cache

            Details:
                If some element inside annotation expression allows for arbitrary type,
                    typespec will contain the most general `object` type
                `None` type annotation is converted to `NoneType`
                `ForwardRef`s are evaluated in-place, name resolution failures are treated
                    the same way as if all annotation expression itself was just name of a type
        """

        # Get annotation expression code from cache, if annotation string is not provided
        if annotation is Null:
            try:
                code = self._code_[attr]
            except KeyError:
                raise TypeError("Annotation cache is missing - 'annotation' string needs to be provided")

        # Pre-compile annotation expression
        else:
            if annotation is EMPTY_ANNOTATION:
                setattr(attr, self.annotationSlot, None)
                setattr(attr, self.typeSlot, object)
                return
            try:
                code = compile(annotation, '<annotation>', 'eval')
            except SyntaxError as e:
                raise SyntaxError(f"Attr '{attr.name}' - cannot evaluate annotation '{annotation}' - {e}")

        # Parse expression to typespec
        globs = globals()
        locs = vars(typing)  # TODO: evaluation scope
        try:
            typeval = eval(code, globs, locs)
            setattr(attr, self.annotationSlot, typeval)

            if isinstance(typeval, type):
                setattr(attr, self.typeSlot, typeval)
                return

            if typeval is None:
                setattr(attr, self.typeSlot, type(None))
                return

            if typeval is Any or typeval is ClassVar:
                setattr(attr, self.typeSlot, object)
                return

            if isinstance(typeval, GenericAlias) and typeval.__origin__ is ClassVar:
                spec = list(typeval.__args__)
            else:
                spec = [typeval]

            i = 0
            while True:
                try: item = spec[i]
                except IndexError: break

                if isinstance(item, GenericAlias):
                    if item.__origin__ is Union:
                        spec.extend(item.__args__)
                        del spec[i]
                    else:
                        spec[i] = item.__origin__
                        i += 1
                elif item is object or item is Any:
                    spec = (object,)
                    break
                elif isinstance(item, type):
                    i += 1
                elif item is Ellipsis and len(spec) > 1:
                    # Allow only nested Ellipsis
                    del spec[i]
                elif isinstance(item, TypeVar):
                    if item.__bound__ is not None:
                        spec[i] = item.__bound__
                    elif item.__constraints__:
                        spec.extend(item.__constraints__)
                        del spec[i]
                    else:
                        spec = (object,)
                        break
                elif isinstance(item, ForwardRef):
                    # TESTME: does ForwardRef._evaluate() would work properly here?
                    spec[i] = item._evaluate(globs, locs)
                else:
                    raise ValueError(f"Attr '{attr.name}' - "
                                     f"annotation '{typeval}' is invalid type")
            spec = tuple(set(spec))

        # Handle the case when annotation contains forward reference
        except NameError as e:
            if strict:
                raise NameError(f"Attr '{attr.name}' - cannot resolve annotation - {e}")
            else:
                self._code_[attr] = code  # cache bytecode
                return  # postpone evaluation
        else:
            setattr(attr, self.typeSlot, spec if len(spec) > 1 else spec[0])
        finally:
            if hasattr(attr, self.typeSlot):
                print(f"{attr.name}.{self.typeSlot}: {getattr(attr, self.typeSlot)}")
            else:
                print(f"{attr.name}.{self.typeSlot} - NOT ASSIGNED")

    def __get__(self, instance: Attr, owner: Type[Attr]) -> Union[type, Tuple[type, ...], AttrTypeDescriptor]:
        if instance is None: return self
        try:
            return getattr(instance, self.typeSlot)
        except AttributeError:
            self.parse(instance, strict=True)
            return getattr(instance, self.typeSlot)


class Attr:
    __slots__ = 'name', 'ann', '_typespec_', '_annotation_'

    type = AttrTypeDescriptor(typeSlot='_typespec_', annotationSlot='_annotation_')

    def __init__(self, name, annotation):
        print(f"Attr.__init__(name={name}, annotation={annotation})")
        self.name = name
        self.ann = annotation
        self.__class__.type.parse(self, annotation)

    def __repr__(self):
        return auto_repr(self, self.name)


def test_FRef():
    import pytest
    import re

    print("@")

    print("\n\nTest forward references\n")

    with pytest.raises(NameError, match=re.escape("name 'Resolved' is not defined")):
        res = Attr('b', 'Resolved').type

    with pytest.raises(NameError, match=re.escape("name 'Resolved' is not defined")):
        res = Attr('b', 'Union["Resolved", Tuple["Resolved", ...]]').type

    class Resolved: pass

    globals()['Resolved'] = Resolved

    res = Attr('b', 'Resolved').type
    assert res == Resolved, res

    res = Attr('b', 'Union["Resolved", Tuple["Resolved", ...]]').type
    assert set(res) == {tuple, Resolved}, set(res)

    T = TypeVar('T')
    TInt = TypeVar('TInt', bound=int)
    TAny = TypeVar('TAny', bound=Any)
    TColl = TypeVar('TColl', tuple, set, list)
    K = TypeVar('K', bound=Union[Tuple[int, ...], List[int], None])
    globals().update({typevar.__name__: typevar for typevar in (T, TInt, TColl, TAny, K)})

    types = {
        'Any': object,
        'object': object,
        'int': int,
        'ClassVar': object,
        'Union[str, str, type("s")]': str,
        'Union[tuple]': tuple,
        'Union[str, list]': (list, str),
        'Union[str, int, "Resolved", Any]': object,
        'Union[Union[bool, int], str, int]': (bool, str, int),
        'Optional[str]': (type(None), str),
        'Callable': Callable.__origin__,
        'type': type,
        'Attr': Attr,
        'ClassVar[float]': float,
        'ClassVar[Optional[Union[int, Union[int, type(3), int("1").__class__], int]]]': (type(None), int),
        'Tuple[int, ...]': tuple,
        'Dict[Union[str, int], Tuple[Optional[bool], Optional[float], Optional[str]]]': dict,
        '': object,
        'None': type(None),
        'Tuple[int]': tuple,
        'Dict[str, int]': dict,
        'Union[None]': type(None),
        'ClassVar[None]': type(None),
        'ClassVar[Union[Tuple[int, ...], Tuple[str, ...], tuple]]': tuple,
        'Union["Resolved", int]': (Resolved, int),
        'Union[Tuple[str, int], Tuple[bool, int], Tuple[bytes, int]]': tuple,
        'Union[Collection[MutableMapping[str, Optional[Attr]]], "Resolved", Tuple[str, ...], Tuple[int, ...], None]':
            (type(None), tuple, Resolved, Collection.__origin__),
        'Union["Tuple[int]", "Tuple[str]"]': tuple,
        'Tuple[Tuple]': tuple,
        'T': object,
        'TInt': int,
        'TAny': object,
        'TColl': (tuple, set, list),
        'K': (tuple, list, type(None)),
        'Union[TColl, K]': (tuple, set, list, type(None)),
        'Optional[K]': (tuple, list, type(None)),
        'Optional[T]': object,
    }

    print("\n\nBasic test\n")
    for i, (ann, spec) in enumerate(types.items()):
        res = Attr(f'attr{i}', ann).type
        is_valid = res == spec if isinstance(spec, type) else set(res) == set(spec)
        assert is_valid, f'{ann} - expected {spec}, got {res}'

    print("\n\nTest ClassVar[...]\n")
    for i, (ann, spec) in enumerate(types.items()):
        if ann.startswith('ClassVar') or not ann: continue
        else: ann = f'ClassVar[{ann}]'

        res = Attr(f'classvar{i}', ann).type

        is_valid = res == spec if isinstance(spec, type) else set(res) == set(spec)
        assert is_valid, f'{ann} - expected {spec}, got {res}'

    print("\n\nTest Optional[...]\n")
    for i, (ann, spec) in enumerate(types.items()):
        if ann.startswith('Optional') or not ann:
            continue
        elif ann == 'ClassVar':
            ann = 'ClassVar[Optional[Any]]'
        elif ann.startswith('ClassVar'):
            ann = f"ClassVar[Optional{ann.lstrip('ClassVar')}]"
        else:
            ann = f'Optional[{ann}]'

        if isinstance(spec, tuple):
            if type(None) not in spec:
                spec = (*spec, type(None))
        else:
            if spec is not object and spec is not type(None):
                spec = (spec, type(None))

        res = Attr(f'optional{i}', ann).type

        is_valid = res == spec if isinstance(spec, type) else set(res) == set(spec)
        assert is_valid, f'{ann} - expected {spec}, got {res}'

    print("\n\nTest ForwardRef[...]\n")
    for i, (ann, spec) in enumerate(types.items()):
        if ann == 'ClassVar': ann = "ClassVar[Union['Any']]"
        elif ann.startswith('ClassVar'):
            ann = f"ClassVar[Union['{ann.lstrip('ClassVar[')[:-1]}']]"
        elif not ann:
            continue
        else:
            ann = f"Union['{ann}']"
        res = Attr(f'attr{i}', ann).type
        is_valid = res == spec if isinstance(spec, type) else set(res) == set(spec)
        assert is_valid, f'{ann} - expected {spec}, got {res}'

    # TODO: error cases

    with pytest.raises(ValueError, match=re.escape("annotation 'Ellipsis' is invalid type")):
        res = Attr('ellipsisErr', '...').type

    with pytest.raises(NameError, match=re.escape("name 'Err' is not defined")):
        res = Attr('z', 'Err').type

    with pytest.raises(NameError, match=re.escape("name 'Err' is not defined")):
        res = Attr('nameErr', 'Union[Tuple[str, str, int], "Err", "Resolved"]').type

    with pytest.raises(SyntaxError, match=re.escape("unexpected EOF while parsing")):
        res = Attr('y', ' ').type


if __name__ == '__main__':
    test_FRef()
