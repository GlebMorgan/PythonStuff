# classes use their own imports

class InternalNameShadingVerifier():
    def __init__(self, docslibs=True, actuallibs=True, builtins=True, keywords=True):
        import os
        import sys
        import keyword
        import distutils.sysconfig
        from stdlib_list import stdlib_list

        self.reservedNamesSet = set()
        self.internalNamesDict = {}

        if (docslibs): self.internalNamesDict['docslibs'] = stdlib_list()
        if (keywords): self.internalNamesDict['keywords'] = keyword.kwlist
        if (builtins): self.internalNamesDict['builtins'] = sys.builtin_module_names
        if (actuallibs):
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

        for key in self.internalNamesDict:
            for name in self.internalNamesDict[key]:
                self.reservedNamesSet.add(name.split(".")[-1] if '.' in name else name)


    def isReserved(self, name):
        return (name in self.reservedNamesSet)

    def showShadowedModule(self, name):
        return [moduleName
                for key in self.internalNamesDict
                    for moduleName in self.internalNamesDict[key]
                        if moduleName.endswith(f".{name}")
        ]


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

    return (" ".join(list(map(''.join, zip(*[iter(bBytes.hex())]*2)))) or '<Void>') if bBytes is not None else '<Void>'


if __name__ == '__main__':
    CHECK_ITEM = bytewise

    if (CHECK_ITEM == InternalNameShadingVerifier):
        intNameVerifier = InternalNameShadingVerifier()
        print(intNameVerifier.reservedNamesSet)
        print(intNameVerifier.isReserved("utils"))
        print(intNameVerifier.showModule("utils"))

    if (CHECK_ITEM == bytewise):
        print(f"b'' - {bytewise(b'')}")
        print(f"None - {bytewise(None)}")
        print(f"Bytes - {bytewise(b'AAABBCC')}")
        print(f"Short bytes - {bytewise(bytes.fromhex('0055FF01'))}")
        print(f"Zero bytes - {bytewise(bytes.fromhex('0000000000'))}")
        print(f"1 byte - {bytewise(bytes.fromhex('00'))}")
        print(f"two bytes - {bytewise(b'fc')}")
        # print(f"Looong bytes - {bytewise(bytes.fromhex('00'*10_000_000))}")

