#TODO: classes use their own imports

import importlib
import os
import sys
import keyword
import distutils.sysconfig
import stdlib_list
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

def isInt(num):
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


def bytewise(bBytes):
    """
    Represents sequence of bytes as space-separated octets or '<Void>' if sequence is empty

    :param bBytes: bytes sequence to display
    :type bBytes: bytes
    :return: bytewise space-separated string
    :rtype str
    """

    return " ".join(list(map(''.join, zip(*[iter(bBytes.hex())]*2)))) or '<Void>' if bBytes is not None else '<Void>'





if __name__ == '__main__':
    CHECK_ITEM = InternalNameShadingVerifier

    if (CHECK_ITEM == InternalNameShadingVerifier):
        shver = InternalNameShadingVerifier(internals=0)
        # print(shver.reservedNames)
        print(shver.isReserved("c"))
        print(shver.showShadowedModules("c"))
        print(shver.showShadowedNames('c'))

    if (CHECK_ITEM == bytewise):
        print(f"b'' - {bytewise(b'')}")
        print(f"None - {bytewise(None)}")
        print(f"Bytes - {bytewise(b'AAABBCC')}")
        print(f"Short bytes - {bytewise(bytes.fromhex('0055FF01'))}")
        print(f"Zero bytes - {bytewise(bytes.fromhex('0000000000'))}")
        print(f"1 byte - {bytewise(bytes.fromhex('00'))}")
        print(f"two bytes - {bytewise(b'fc')}")
        # print(f"Looong bytes - {bytewise(bytes.fromhex('00'*10_000_000))}")

