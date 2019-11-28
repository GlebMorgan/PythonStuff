from __future__ import annotations as annotations_feature

import typing
from types import CodeType
from typing import Union, Collection, Callable, ClassVar, Dict, Tuple, Type, Any, TypeVar, Generic, _Protocol
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
    __slots__ = '_code_', 'typeSlot', 'annotationSlot'

    def __init__(self, typeSlot: str, annotationSlot: str):
        self.typeSlot: str = typeSlot
        self.annotationSlot: str = annotationSlot
        # Compiled annotation expressions cache
        self._code_: Dict[Attr, CodeType] = {}

    def parse(self, attr: Attr, annotation: str = Null, *, strict: bool = False):
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

        globs = globals()
        locs = vars(typing)  # TODO: evaluation scope

        # TODO: define type Unions as [type1, type2, ..., typeN]
        try:
            typeval = eval(code, globs, locs)
            setattr(attr, self.annotationSlot, typeval)

            if isinstance(typeval, type):
                setattr(attr, self.typeSlot, typeval)
                return

            if typeval is None:
                setattr(attr, self.typeSlot, type(None))
                return

            if typeval is Any:
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

        except NameError as e:
            # Annotation may contain forward reference
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


class Base:
    def __init__(self):
        self.a = Attr('a', 'str')


def test_FRef():
    import pytest
    import re

    print("@")

    with pytest.raises(NameError, match=re.escape("name 'Resolved' is not defined")):
        res = Attr('b', 'Resolved').type

    class Resolved: pass

    globals()['Resolved'] = Resolved

    res = Attr('b', 'Resolved').type
    assert res == Resolved

    with pytest.raises(RuntimeError, match=re.escape("Cannot evaluate annotation ' '")):
        res = OldAttr('y', ' ').type

    with pytest.raises(RuntimeError, match=re.escape("Cannot resolve type 'Error'")):
        res = OldAttr('z', 'Error').type

    types = {
        'Any': object,
        'object': object,
        'int': int,
        'Union[str, str, type("s")]': str,
        'Union[tuple]': tuple,
        'Union[str, list]': (list, str),
        'Union[str, Any]': object,
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
    }

    for i, (ann, spec) in enumerate(types.items()):
        res = Attr(f'a{i}', ann).type
        assert res == spec, f'Expected {spec}, got {res}'


if __name__ == '__main__':
    test_FRef()