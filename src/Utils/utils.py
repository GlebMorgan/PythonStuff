from contextlib import contextmanager
from functools import wraps
from itertools import chain as itertools_chain
from os import linesep
from typing import Union, Iterable
from time import time

import stdlib_list

from .bits import extract

sampledict = {
    1: 'a',
    2: 'b',
    'None': None,
    'bool': True,
    'str': 'blablabla',
    'multilineStr': '1st str' + linesep + '2nd str',
    'ellipsis': ...,
    'list': [1, 2, 3, 4, 5, ('a', 'b', 'c'), ..., None],
    'dict': {1: 'first', 2: 'second'},
    'object': object(),
    'errorClass': RuntimeError,
    'function': print,
    'module': stdlib_list
}
sampledict['self'] = sampledict


class Timer:

    def __init__(self, name=None, mul=1):
        self.name = name
        self.multiplier = mul
        self.tstart = None
        self.running = False

    def __enter__(self):
        self.start()

    def __exit__(self, errtype, value, traceback):
        self.stop()

    def start(self):
        if not self.running:
            self.running = True
            self.tstart = time()

    def stop(self):
        if self.running:
            self.running = False
            print(f"[{self.name or 'Timer'}] duration: {(time() - self.tstart)*self.multiplier}")

class InternalNameShadingVerifier():

    def __init__(self, docslibs=True, reallibs=True, builtins=True,
                 builtin_modules=True, keywords=True, internals=False):
        self.internalNamesDict = {}
        self.checkinternals = internals
        if (docslibs): self.internalNamesDict['docslibs'] = stdlib_list.stdlib_list()
        if (keywords):
            import keyword
            self.internalNamesDict['keywords'] = keyword.kwlist
        if (builtins):
            import builtins as module_builtins
            self.internalNamesDict['builtins'] = dir(module_builtins)
        if (builtin_modules):
            modules = []
            try:
                import sys
                for modulename in sys.builtin_module_names:
                    if (not modulename.startswith('_')): self._public_submodules_recursive(modules, '', modulename)
            except RecursionError: modules.append(...)

            self.internalNamesDict['builtin_modules'] = modules
        if (reallibs):
            import distutils.sysconfig, os
            stdlib_items = []
            std_lib = distutils.sysconfig.get_python_lib(standard_lib=True)
            for top, dirs, files in os.walk(std_lib):
                for nm in files:
                    prefix = top[len(std_lib) + 1:]
                    if nm == '__init__.py':
                        stdlib_items.append(top[len(std_lib) + 1:].replace(os.path.sep, '.'))
                    elif nm[-3:] == '.py':
                        stdlib_items.append(os.path.join(prefix, nm)[:-3].replace(os.path.sep, '.'))
                    elif nm[-3:] == '.so' and top[-11:] == 'lib-dynload':
                        stdlib_items.append(nm[0:-3])
            self.internalNamesDict['actuallibs'] = stdlib_items

    def _public_submodules_recursive(self, submodules, basemodule, currname):
        import importlib
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
    strRepr = " ".join(list(map(''.join, zip(*[iter(bBytes.hex().upper())] * 2))))
    if (collapseAfter is None or len(bBytes) <= collapseAfter): return strRepr
    else: return f"{strRepr[:collapseAfter - 2]} ... {strRepr[-2:]} ({len(bBytes)} bytes)"


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
            f"{byte >> 4:04b} {extract(byte, frombit=3):04b}" for byte in iter(bBytes)
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
        print(f"!!! Class '{legacy_entity.__name__}' is tagged as legacy !!!")
        return new_cls
    else:
        @wraps(legacy_entity)
        def funWrapper(*args, **kwargs):
            print(f"!!! Function '{legacy_entity.__name__}' is tagged as legacy !!!")
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
    def init_wrapper(*args, **kwargs):
        _self = args[0]
        _self.__dict__.update(kwargs)
        _total_names = initFunc.__code__.co_varnames[1:initFunc.__code__.co_argcount]
        _values = args[1:]
        _names = [n for n in _total_names if not n in kwargs]
        d = dict()
        for n, v in zip(_names, _values): d[n] = v
        _self.__dict__.update(d)
        initFunc(*args, **kwargs)

    return init_wrapper


def inject_slots(at):
    """ __init__ decorator.
        Automatically creates and initializes same-name object slots based on args passed to '__init__'
    """
    # TODO: does not assign to default values specified in function defenition;
    # like '4' in following function: def f(a, b, c=4): ...
    if (type(at) is not str):
        f = at
        at = 'start'
    elif (at not in ('start', 's', 'end', 'e')):
        raise ValueError("Define slots injection order as 'start' or 'end'")

    def decorator_inject_slots(initFunc):
        @wraps(initFunc)
        def init_wrapper(*args, **kwargs):
            if (at == 'start' or at == 's'): initFunc(*args, **kwargs)
            _self = args[0]
            try: _self.__slots__
            except AttributeError: raise TypeError(f"Class '{_self.__class__.__name__}' does not have __slots__ set")
            for par, value in kwargs.items(): object.__setattr__(_self, par, value)
            _total_names = initFunc.__code__.co_varnames[1:initFunc.__code__.co_argcount]
            _values = args[1:]
            _names = [n for n in _total_names if not n in kwargs]
            args_dict = dict()
            for n, v in zip(_names, _values): args_dict[n] = v
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
    """ Decorator (to use with methods only!) to cache single-output result
        Returns existing 'class.name' attr if one exists
        Otherwise computes and creates it first
    """
    if (type(name) is not str): raise TypeError("Attribute name is required")

    def store_value_decorator(f):
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            try: return getattr(self, name)
            except AttributeError:
                setattr(self, name, f(self, *args, **kwargs))
                return getattr(self, name)

        return wrapper

    return store_value_decorator


def auto_repr(obj, msg):
    return f"<{obj.__class__.__module__}.{obj.__class__.__qualname__} {msg} at {hex(id(obj))}>"


def init_class(method):
    """ Calls 'method' class method (should take no arguments)
        immediately after class creation """

    if (type(method) is not str): raise TypeError("Method name is required")

    def decorator_init_class(cls):
        getattr(cls, method).__call__()
        return cls

    return decorator_init_class


def injectProperties(init_func):
    """ Used to separate object native properties from service attributes
        Class whose '__init__()' is wrapped should define 'init()' method
            that handles all remaining class initialization (including creation of service attrs)
        Attr names defined in '__init__()' will be collected into new tuple 'self.props' """

    if (init_func.__name__ != '__init__'):
        raise SyntaxError("'injectProperties' decorator is intended to wrap '__init__' only")

    @wraps(init_func)
    def wrapper(init_self, *a, **kw):
        init_func(init_self, *a, **kw)
        props = []
        for a in vars(init_self):
            props.append(a)
        init_self.props = tuple(props)
        init_self.init()

    return wrapper


def alias(this: type): return this


@contextmanager
def this(ref):
    """ Context manager to shorten long expressions to one name """
    yield ref


def castStr(targetType: type, value: str) -> Union[None, str, int, float, bool]:
    """ Convert string 'value' to specified type (non case-sensitively).
        ['True', 'Yes', '1', 'ON']  —> True <bool>
        ['False', 'No', '0', 'OFF'] —> False <bool>
        ['12', '0xC', '0b1100']     —> 12 <int>
        ['0.1', '1E-1', '1.00E-1']  —> 12 <int>
        'any_str'                   —> 'any_str' <str>
    """

    value = value.lower()

    if targetType is str:
        return value

    if targetType is bool:
        if value in ('true', 'yes', '1', 'on'): return True
        elif value in ('false', 'no', '0', 'off'): return False

    elif targetType is int:
        try:
            if (value[:2] == '0x'): return int(value, 16)
            elif (value[:2] == '0b'): return int(value, 2)
            else: return int(value)
        except ValueError: pass  # Value error will be raised at the end of function

    elif targetType is float:
        try:
            return float(value)
        except ValueError: pass  # Again, value error will be raised below

    elif targetType is None: return None

    # if got here ▼, that was invalid string representation of specified type
    raise ValueError(f"Cannot convert '{value}' to {targetType}")


def trimDict(dct: dict, limit: int):
    if len(dct) <= limit: return dct
    return dict(list(dct.items())[:limit])


def formatDict(d: dict, indent=4, level=0, limit=None):
    """ Return string representation of mapping in a following format:
        {
            <name1>: str(<value1>)
            <name2>: self  # ◄ if <value2> is a self reference
            <name3>: {
                <nestedName1>: str(<nestedValue1>)
                <nestedName2>: str(<nestedValue2>)
                ...
            }
            ...
        }
    """

    def addIndent(s: str, lvl=1):
        return indent * lvl + s

    def iteritems(dct, trimmed=False):
        for name, value in dct.items():
            if value is dct: value = '<self>'
            elif isinstance(value, dict): value = formatDict(value, level=level+1)
            yield f"{addIndent('', level+1)}{name}: {str(value)}"
        if trimmed: yield addIndent('...')

    if not d: return '{}'
    indent = ' ' * indent
    shortd = trimDict(d, limit) if limit else d
    return linesep.join(itertools_chain(
            '{',
            iteritems(shortd, trimmed = len(d) != len(shortd)),
            (addIndent('}', level),)
    ))


def formatList(seq, indent=0):
    return linesep.join(' '*indent + str(item) for item in seq)


def memo(f):
    """ Cache every no-side-effect function/method output
        Function arguments must be immutable
        'self' argument in methods is not cached """
    excludeFirst = True if 'self' in f.__code__.co_varnames else False
    memory = {}

    @wraps(f)
    def memoize_wrapper(*args, **kwargs):
        if not kwargs: key = args[excludeFirst:]
        else: key = (tuple(args), frozenset(kwargs.items()))
        if key not in memory: memory[key] = f(*args, **kwargs)
        return memory[key]
    return memoize_wrapper


def memoLastPosArgs(f):
    """ Cache single last no-side-effect function/method output
        Function should accept positional arguments only
        'self' argument in methods is not cached """
    f.cachedArgs = None
    f.cachedRes = None
    excludeFirst = True if 'self' in f.__code__.co_varnames else False

    def wrapper(*args):
        if args[excludeFirst:] != f.cachedArgs:
            f.cachedArgs = args[excludeFirst:]
            f.cachedRes = f(*args)
        return f.cachedRes
    return wrapper


class Dummy:
    """ Void mock class returning itself on every attr access
        Use to avoid attribute/name errors with no if-checks
        Evaluates to False on logical operations """

    def __init__(self, *args, **kwargs): pass

    def __getattr__(self, item): return self

    def __call__(self, *args, **kwargs): return self

    def __bool__(self): return False


class VoidDict():
    """ Emulate empty dict, but not actually creating one """

    def items(self): return self

    def values(self): return self

    def keys(self): return self

    def get(self): return None

    def __iter__(self): return self

    def __next__(self): raise StopIteration


Null = type('NULL', (), {
    '__slots__': (),
    '__doc__': """ Denotes non-existent value. Should never be assigned to anything by user code """,
    '__bool__': lambda self: False,
    '__str__': lambda self: "N/A",
    '__repr__': lambda self: auto_repr(self, 'Null object'),
})()


class isiterableMeta(type):
    def __init__(cls, *args):
        super().__init__(*args)
        cls.type = None
    def __getitem__(cls, item):
        if not isinstance(item, type):
            raise TypeError(f"{item} is not a type")
        else: cls.type = item
        return cls
class isiterable(metaclass=isiterableMeta):
    """ Check whether `target` is iterable object (NOT considering 'str' and 'bytes')
        If type is given in [], check whether iteration over `target` generates objects of specified type
    """
    def __new__(self, target):
        if isinstance(target, (str, bytes)): return False
        try: iterator = iter(target)
        except TypeError: return False
        if self.type is None: return True
        else: return True if all(isinstance(item, self.type) for item in iterator) else False


def threaded(f):
    """ Decorator to run function in new thread """

    from threading import Thread

    @wraps(f)
    def runThreaded(*args, **kwargs):
        thread = Thread(name=f"Threaded: {f.__name__}", target=f, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return runThreaded


def testCOMs(comSeq=(1, 2, 10, 11, 12, 13)):
    from serial import Serial as S
    s = S(baudrate=912600, timeout=1, write_timeout=1)
    for i in comSeq:
        s.port = f'COM{i}'
        try:
            s.open()
        except Exception as e:
            print(f"{s.port}: {e}")
        else:
            print(f"{s.port}: OK")
        s.close()


def listAttrs(obj, invoke=False, limit: int = None):
    for a in dir(obj):
        v = getattr(obj, a)

        if hasattr(v, '__call__'):
            try:
                if invoke: v = v()
                else: raise TypeError
            except TypeError:
                import inspect
                try: v = f'{v.__name__}{inspect.signature(v)}'
                except ValueError: v = v.__name__
                except AttributeError: pass  # leave name as repr
            a = f'{a}()'

        if isinstance(v, dict): v = formatDict(v, limit=limit)
        print(f"{a} = {v}", sep=linesep)


def attachItem(iterable: Iterable, append=Null, prepend=Null):
    # TODO: analyze first and second arguments' types and provide a clean seamless signature
    #           (prepend, iterable, append) or (iterable, append) or (prepend, iterable) with no keyword arguments
    """ Attach one item to an iterable (before or/and after) and return resulting extended generator """
    if prepend is not Null: yield prepend
    yield from iterable
    if append is not Null: yield append


def chain(*items):
    """ Extended itertools.chain()
            • accepts single objects as well as iterables
            • treats strings as objects, not iterables
    """
    for item in items:
        try:
            if isinstance(item, str): yield item
            else: yield from item
        except TypeError as err:
            # ▼ Re-raise errors occurred in inner frames (inside item)
            if err.__traceback__.tb_next is not None: raise err
            yield item


def die(msg: Union[int, str], errcode: int = 1):
    """ Display message 'msg', wait for a key press and exit with exit code 'errcode'
        If first parameter is integer number, it is interpreted as an error code,
            and msg is considered to be omitted
    """

    if isinstance(msg, int): errcode, msg = msg, ''
    print(msg)
    input('Press any key to exit ...')
    exit(errcode)


def ask(msg, options=None):
    """ TODO: ask() helper function docstring """
    if not options:
        options = ['y', 'n']
    options = list(options)
    choices = f"{msg} [{', '.join((name if name else '<Enter>' for name in options))}]: "
    for i, string in enumerate(options): options[i] = string.lower()
    for _ in range(10):
        ans = input(choices)
        if ans.strip().lower() in options: return ans
    else: die("Run out of attempts")


@contextmanager
def ignoreErrors():
    try: yield
    except Exception: pass


class Chain:
    """ TODO: Chain class docstring """
    def __init__(self, obj):
        self.target = obj
        self.methodname = None

    def __getitem__(self, item: str):
        """ getattribute() for internal use """
        return object.__getattribute__(self, item)

    def __getattribute__(self, item):
        if item in ('ok', 'end', 'apply'):
            return self['target']
        if item.startswith('__') and item.endswith('__'):
            return self[item]
        self.methodname = item
        method = getattr(self['target'], item)
        if not hasattr(method, '__call__'):
            raise TypeError(f"'{type(method).__name__}' object '{method}' is not callable")
        return self

    def __call__(self, *args, **kwargs):
        # if self['method'].__func__(self['target'], *args, **kwargs) is not None:
        if getattr(self['target'], self['methodname'])(*args, **kwargs) is not None:
            raise RuntimeError(f"Method '{self['methodname']}' returned non-None value, cannot use Chain")
        return self

    def __repr__(self): return f"Chain wrapper of {self['target']} object at {hex(id(self))}"


class classproperty:
    """ Decorator implementing a class-level read-only property """
    def __init__(self, func):
        self.__func__ = func
        self.__doc__ = func.__doc__

    def __get__(self, instance, cls=None):
        if cls is None:
            cls = type(instance)
        return self.__func__(cls)

# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————— #


if __name__ == '__main__':
    CHECK_ITEM = classproperty

    if CHECK_ITEM == InternalNameShadingVerifier:
        shver = InternalNameShadingVerifier(internals=False)
        # print(shver.reservedNames)
        print(shver.isReserved("c"))
        print(shver.showShadowedModules("c"))
        print(shver.showShadowedNames('c'))

    if CHECK_ITEM == bytewise:
        print(f"b'' - {bytewise(b'')}")
        print(f"None - {bytewise(None)}")
        print(f"Bytes - {bytewise(b'ABCDEFGHIJKLMNO')}")
        print(f"Short bytes - {bytewise(bytes.fromhex('0055FF01'))}")
        print(f"Zero bytes - {bytewise(bytes.fromhex('0000000000'))}")
        print(f"1 byte - {bytewise(bytes.fromhex('00'))}")
        print(f"two bytes - {bytewise(b'fc')}")
        # print(f"Looong bytes - {bytewise(bytes.fromhex('00'*10_000_000))}")

    if CHECK_ITEM == bytewise_format:
        with Timer("iter"):
            print(f"Looong bytes - "
                  f"{bytewise(bytes.fromhex(''.join([i.to_bytes(2, 'big').hex() for i in range(65_535)])))}")
        with Timer("format"):
            print(f"Looong bytes - "
                  f"{bytewise_format(bytes.fromhex(''.join([i.to_bytes(2, 'big').hex() for i in range(65_535)])))}")

    if CHECK_ITEM == bitwise:
        print(bitwise(b'FGRb'))
        print(f"{int.from_bytes(b'FGRb', 'big'):032b}")

    if CHECK_ITEM == legacy:
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

    if CHECK_ITEM == inject_slots:
        class TestInjetSlots:
            __slots__ = ('a', 'b', 'c', 'd')

            @inject_slots
            def __init__(self, a, b, c=4, d=8): print("finished __init__")


        t = TestInjetSlots('avar', 'bvar')
        print(*(t.a, t.b, t.c, t.d))

    if CHECK_ITEM == inject_args:
        class TestInjetArgs:
            @inject_args
            def __init__(self, a, b, c=4, d=8): print("finished __init__")


        t = TestInjetArgs('avar', 'bvar')
        print(*(t.a, t.b, t.c, t.d))

    if CHECK_ITEM == isiterable:
        assert isiterable[str]('value') is False
        assert isiterable[bytes](b'abcd') is False
        assert isiterable[int](b'abcd') is False
        assert isiterable[str](['a', 'g', 't']) is True
        assert isiterable[bytes]([b'a', b'b', b'c']) is True
        assert isiterable[int]({1: 'a', 2: 't'}) is True
        assert isiterable[int]('wrong') is False
        assert isiterable[bool]((True, False, None)) is False
        assert isiterable[bool]((True, False, True)) is True
        assert isiterable[int](0) is False
        assert isiterable(1) is False
        assert isiterable((1, 2, 3)) is True
        assert isiterable('abc') is False
        assert isiterable(b'abc') is False
        try: print(isiterable[all]('error'))
        except TypeError as e: print(e.args[0])
        else: assert False

    if CHECK_ITEM == formatDict:
        print(formatDict(sampledict, limit=4))

    if CHECK_ITEM == classproperty:
        class A:
            @classproperty
            def p(cls):
                print('p')
                return 1

        print(A.p)
        A.p = 3
        print(A.p)



