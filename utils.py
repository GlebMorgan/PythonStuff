#TODO: classes use their own imports

import importlib
import os
import sys
import sys
import keyword
import distutils.sysconfig
import stdlib_list
import bits
from timer import Timer
from functools import wraps


class InternalNameShadingVerifier():

    def __init__(self, docslibs=True, reallibs=True, builtins=True, keywords=True, internals=False):
        self.internalNamesDict = {}
        self.checkinternals = internals
        if (docslibs): self.internalNamesDict['docslibs'] = stdlib_list.stdlib_list()
        if (keywords): self.internalNamesDict['keywords'] = keyword.kwlist
        if (builtins):
            modules = []
            try:
                for modulename in sys.builtin_module_names:
                    if (not modulename.startswith('_')): self._public_submodules_recursive(modules, '', modulename)
            except RecursionError: modules.append(...)

            self.internalNamesDict['builtins'] = modules
        if (reallibs):
            stdlib_items = []
            std_lib = distutils.sysconfig.get_python_lib(standard_lib=True)
            for top, dirs, files in os.walk(std_lib):
                for nm in files:
                    prefix = top[len(std_lib)+1:]
                    if nm == '__init__.py':
                        stdlib_items.append(top[len(std_lib)+1:].replace(os.path.sep,'.'))
                    elif nm[-3:] == '.py':
                        stdlib_items.append(os.path.join(prefix, nm)[:-3].replace(os.path.sep,'.'))
                    elif nm[-3:] == '.so' and top[-11:] == 'lib-dynload':
                        stdlib_items.append(nm[0:-3])
            self.internalNamesDict['actuallibs'] = stdlib_items


    def _public_submodules_recursive(self, submodules, basemodule, currname):
        if (currname in ('this', 'antigravity')): return
        fullbasemodule = f"{basemodule}.{currname}" if basemodule else currname
        try: currmodule = importlib.import_module(fullbasemodule)
        except (ImportError, ModuleNotFoundError): return
        for submodule in dir(currmodule):
            if (not submodule.startswith('_') or self.checkinternals):
                self._public_submodules_recursive(submodules, fullbasemodule, submodule)
                submodules.append(f"{fullbasemodule}.{submodule}")


    @property
    def reservedNames(self):
        reservedNamesSet = set()
        for key in self.internalNamesDict:
            for name in self.internalNamesDict[key]:
                reservedNamesSet.add(name.split(".")[-1] if '.' in name else name)
        return reservedNamesSet


    def isReserved(self, name):
        return (name in self.reservedNames)


    def showShadowedModules(self, name):
        name = f".{name}"
        names = (moduleName
                for key in self.internalNamesDict
                    for moduleName in self.internalNamesDict[key]
                        if (moduleName.endswith(name))
        )
        return set(names) or '<None>'


    def showShadowedNames(self, name):
        names = []
        for currname in self.reservedNames: self._public_submodules_recursive(names, '', currname)
        return tuple(currname for currname in names if currname.endswith(f".{name}")) or '<None>'


def isint(num):
    """
    Check an object could be coarced to 'int'

    :param num: any
    :return: True / False
    :rtype: bool
    """

    try:
        int(num)
        return True
    except ValueError:
        return False


def bytewise(bBytes, collapseAfter=None):
    """
    Represents sequence of bytes as hexidecimal space-separated
    octets or '<Void>' if sequence is empty or equals to None

    :param bBytes: bytes sequence to display
    :type bBytes: bytes
    :param collapseAfter: defines maximum output string length. Intermediate bytes are replaced with ellipsis.
                          No length limit if 'collapseAfter' is set to 'None'
    :type collapseAfter: int
    :return: bytewise space-separated string
    :rtype str
    """

    if (not bBytes or bBytes is None): return '<Void>'
    strRepr = " ".join(list(map(''.join, zip(*[iter(bBytes.hex().upper())]*2))))
    if (collapseAfter is None or len(bBytes) <= collapseAfter): return strRepr
    else: return f"{strRepr[:collapseAfter-2]} ... {strRepr[-2:]} ({len(bBytes)} bytes)"



def bytewise_format(bBytes, void='<Void>'):
    """Same as 'bytewise' except different (more readable) implementation"""

    return " ".join(f"{byte:02X}" for byte in iter(bBytes)) if bBytes else void


def bitwise(bBytes):
    """
    Represents sequence of bytes as bianry space-separated
    octets or '<Void>' if sequence is empty or 'None'

    :param bBytes: bytes sequence to display
    :type bBytes: bytes
    :return: bitwise space-separated string
    :rtype str
    """

    return "  ".join(
            f"{byte>>4:04b} {bits.extract(byte, frombit=3):04b}" for byte in iter(bBytes)
            ) if bBytes is not None else '<Void>'


def legacy(legacy_entity):
    """ Decorator.
        Force prints warning mesage on legacy_function call.
        Use to prevent legacy code from interfering with actual one
            when it should still exist in source codes
    """
    if (type(legacy_entity) == type):
        new_cls = type(f"old_{legacy_entity.__name__}", legacy_entity.__bases__, dict(legacy_entity.__dict__))
        new_cls.__legacy = True
        return new_cls
    else:
        @wraps(legacy_entity)
        def funWrapper(*args, **kwargs):
            print("!!! Function is tagged as legacy !!!")
            return legacy_entity(*args, **kwargs)
        funWrapper.__name__ = f"old_{funWrapper.__name__}"
        funWrapper.legacy = True
        return funWrapper


def inject_args(initFunc):
    """ __init__ decorator.
        Automatically creates and initializes same-name object attrs based on args passed to '__init__'
    """
    # TODO: does not assign to default values specified in function defenition;
    # like '4' in folowing function: def f(a, b, c=4): ...
    def init_wrapper(*args,**kwargs):
        _self = args[0]
        _self.__dict__.update(kwargs)
        _total_names = initFunc.__code__.co_varnames[1:initFunc.__code__.co_argcount]
        _values = args[1:]
        _names = [n for n in _total_names if not n in kwargs]
        d = dict()
        for n, v in zip(_names,_values): d[n] = v
        _self.__dict__.update(d)
        initFunc(*args, **kwargs)
    return init_wrapper


def inject_slots(at):
    """ __init__ decorator.
        Automatically creates and initializes same-name object slots based on args passed to '__init__'
    """
    #TODO: does not assign to default values specified in function defenition;
    # like '4' in folowing function: def f(a, b, c=4): ...
    if (type(at) is not str):
        f = at
        at = 'start'
    elif (at not in ('start', 's', 'end', 'e')):
        raise ValueError("Define slots injection order as 'start' or 'end'")
    def decorator_inject_slots(initFunc):
        @wraps(initFunc)
        def init_wrapper(*args,**kwargs):
            if (at == 'start' or at == 's'): initFunc(*args, **kwargs)
            _self = args[0]
            try: _self.__slots__
            except AttributeError: raise TypeError(f"Class '{_self.__class__.__name__}' does not have __slots__ set")
            for par, value in kwargs.items(): object.__setattr__(_self, par, value)
            _total_names = initFunc.__code__.co_varnames[1:initFunc.__code__.co_argcount]
            _values = args[1:]
            _names = [n for n in _total_names if not n in kwargs]
            args_dict = dict()
            for n, v in zip(_names,_values): args_dict[n] = v
            for par, value in args_dict.items(): object.__setattr__(_self, par, value)
            if (at == 'end' or at == 'e'): initFunc(*args, **kwargs)
        return init_wrapper
    return decorator_inject_slots(f)


def add_slots(oldclass):
    """ Class decorator.
        Adds __slots__ to the class attrs that were annotated,
        except ones annotated with typing.ClassVar - those are left
        as conventional class variables
    """

    oldclass_dict = dict(oldclass.__dict__)
    # inherited_slots = set().union(*(getattr(c, '__slots__', set()) for c in oldclass.mro()))
    field_names = tuple(var[0] for var in getattr(oldclass, '__annotations__').items()
                            if not (str(var[1]).startswith('ClassVar[') and str(var[1]).endswith(']')))

    oldclass_dict['__slots__'] = tuple(field for field in field_names)  # '... if field not in inherited_slots'
    for f in field_names: oldclass_dict.pop(f, None)
    oldclass_dict.pop('__dict__', None)
    oldclass_dict.pop('__weakref__', None)
    newclass = type(oldclass.__name__, oldclass.__bases__, oldclass_dict)
    newclass.__qualname__ = getattr(oldclass, '__qualname__')

    return newclass


def store_value(name):
    """ Decorator (to use with methods only!) to cach single-output result
        Returns existing 'class.name' attr if one exists
        Otherwise computes and creates it first
    """
    if(type(name) is not str): raise TypeError("Attribute name is required")
    def store_value_decorator(f):
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            try: return getattr(self, name)
            except AttributeError:
                setattr(self, name, f(self, *args, **kwargs))
                return getattr(self, name)
        return wrapper
    return store_value_decorator


def auto_repr(object, msg):
    return f"{object.__class__.__module__}.{object.__class__.__name__} {msg} at {id(object):X}"


def init_class(method):
    """ Calls 'method' class method (should take no arguments)
        immediately after class creation """

    if (type(method) is not str): raise TypeError("Method name is required")

    def decorator_init_class(cls):
        getattr(cls, method).__call__()
        return cls
    return decorator_init_class


if __name__ == '__main__':
    CHECK_ITEM = inject_args

    if (CHECK_ITEM == InternalNameShadingVerifier):
        shver = InternalNameShadingVerifier(internals=0)
        # print(shver.reservedNames)
        print(shver.isReserved("c"))
        print(shver.showShadowedModules("c"))
        print(shver.showShadowedNames('c'))

    if (CHECK_ITEM == bytewise):
        print(f"b'' - {bytewise(b'')}")
        print(f"None - {bytewise(None)}")
        print(f"Bytes - {bytewise(b'ABCDEFGHIJKLMNO')}")
        print(f"Short bytes - {bytewise(bytes.fromhex('0055FF01'))}")
        print(f"Zero bytes - {bytewise(bytes.fromhex('0000000000'))}")
        print(f"1 byte - {bytewise(bytes.fromhex('00'))}")
        print(f"two bytes - {bytewise(b'fc')}")
        # print(f"Looong bytes - {bytewise(bytes.fromhex('00'*10_000_000))}")

    if (CHECK_ITEM == bytewise_format):
        with Timer("iter"):
            print(f"Looong bytes - {bytewise(bytes.fromhex(''.join([i.to_bytes(2, 'big').hex()for i in range(65_535)])))}")
        with Timer("format"):
            print(f"Looong bytes - {bytewise_format(bytes.fromhex(''.join([i.to_bytes(2, 'big').hex()for i in range(65_535)])))}")

    if (CHECK_ITEM == bitwise):
        print(bitwise(b'FGRb'))
        print(f"{int.from_bytes(b'FGRb', 'big'):032b}")

    if (CHECK_ITEM == legacy):
        class A:
            a = "new_a"
            print("##")
        @legacy
        class A:
            a = "legacy_A"
            print("!!")
        @legacy
        def fun(): print('fuuun!')
        print(A.a)
        fun()
        print(fun.legacy)

    if (CHECK_ITEM == inject_slots):
        class TestInjetSlots:
            __slots__ = ('a', 'b', 'c', 'd')

            @inject_slots
            def __init__(self, a, b, c=4, d=8): print("finished __init__")

        t = TestInjetSlots('avar', 'bvar')
        print(*(t.a, t.b, t.c, t.d))

    if (CHECK_ITEM == inject_args):
        class TestInjetArgs:
            @inject_args
            def __init__(self, a, b, c=4, d=8): print("finished __init__")


        t = TestInjetArgs('avar', 'bvar')
        print(*(t.a, t.b, t.c, t.d))



