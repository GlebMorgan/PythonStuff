from functools import reduce
from math import log2


__all__ = 'set', 'clear', 'combine', 'extract', 'flag', 'flags', 'bitsarray'


def set(bits=0, value=0):
    """
    Set specified bits to 1 and return new binary number
    If value is not specified, new number is returned with only defined bits set

    :param value: set bits of this number
    :type value: int
    :param bits: iterable with bits indices that need to be set
    :type bits: int or collections.abc.Iterable
    :return: number with defined bits set to 1
    """

    if (not hasattr(bits, '__iter__')):
        return value | (1 << bits)
    for bit in bits: value |= (1 << bit)
    return value


def clear(value=0, bits=0):
    """
    Set specified bits to 0 and return new binary number
    If value is not specified, 0 is returned

    :param value: set bits of this number
    :type value: int
    :param bits: iterable with bits indices that need to be cleared
    :type bits: collections.abc.Iterable
    :return: number with defined bits set to 0
    """
    if (not hasattr(bits, '__iter__')):
        return value & ~(1 << bits)
    for bit in bits: value &= ~(1 << bit)
    return value


def combine(*values):
    """
    Stich multiple values into one bit sequence

    :param values: numbers to combine
    :type values: int
    :return: number with bits from all input numbers combined
    """

    return reduce(lambda v1,v2: v1 | v2, values)


def split(): NotImplemented

def extract(val, frombit=None, tobit=0):
    # TODO: define range in a symbol mask way
    """
    Extract number from 'val' based on provided limits [frombit..tobit], both inclusive
    Ex: extract(0b001_110_10, 2, 4) == 0b110
        extract(0b01_0_1, 1, 1) == 0b0
        extract(0b000_1, 0) == 0b1

    :param val: integer number to be masked
    :type val: int
    :param frombit: first mask bit index (right to left bit order)
    :type frombit: int
    :param tobit: last mask bit index (right to left bit order)
    :type tobit: int
    :return: extracted integet
    :rtype: int
    """

    if (val == 0): return 0
    # set 'frombit' to leftmost meaningful bit if undefined
    if (not frombit): frombit = int(log2(val))+1
    return (val & ((1<<frombit+1) - 1)) >> tobit


def flag(val, pos):
    """
    Extract one-bit boolean value from 'value'

    :param val: integer number, typically representing a flags array
    :type val: int
    :param pos: position of requested bit in flags array
    :type pos: int
    :return: extracted flag bit
    :rtype: bool
    """

    return bool((val >> pos) & 0b1)


def flags(val, n):
    """ Convert 'n' rightmost bits of number 'val' to tuple of bools (ordered right to left) """

    return tuple(bool((val >> i) & 0b1) for i in range(n))


def bitsarray(*args)->int:
    """ Accepts any number of flags (booleans) and packs them into an integer
        representing input flags in given order """

    return combine(*map(lambda i: args[i]<<i, range(len(args))))


if __name__ == '__main__':
    def set_test():
        assert (set(0b0011, (2, 3)) == 0b1111)
        assert (set(0b0000, (0, 1, 2, 3)) == 0b1111)
        assert (set(0b0011, ()) == 0b0011)
        assert (set(0b1111, (1, 2, 2, 3)) == 0b1111)
        assert (set(0b1111, ()) == 0b1111)
        assert (set(0b0000, (0, 1, 2, 3, 4)) == 0b11111)
        assert (set(0b0000_0000, (8)) == 0b1_0000_0000)
        assert (set(0b1000_0000, ()) == 128)
        assert (set(0b1000_0000, (7)) == 0b1000_0000)
        assert (set(0b0000_0001, (7)) == 0b1000_0001)
        assert (set(0b1, 0) == 0b1)
        print("DONE")

    def clear_test():
        assert(clear(0b0100, (0,2)) == 0)
        assert(clear(0b0000, (4)) == 0)
        assert(clear(0b0001, (2)) == 1)
        print("DONE")

    def extract_test():
        assert(extract(0b01100, 3, 2) == 0b11)
        assert(extract(0b01100, tobit=2) == 0b11)
        assert(extract(0b01100, tobit=2) == 0b11)
        assert(extract(0b11100, tobit=2) == 0b111)
        assert(extract(0b000, 0, 0) == 0b0)
        assert(extract(0b0011, 1, 0) == 0b11)
        assert(extract(0b0011, tobit=0) == 0b11)
        assert(extract(0b0011, tobit=1) == 0b1)
        assert(extract(0b0011, tobit=2) == 0b0)
        assert(extract(0b1100_0010, 7, 2) == 0b110000)
        assert(extract(0b1100_0010, 7, 0) == 0b11000010)
        assert(extract(0b1100_0010, tobit=0) == 0b11000010)
        assert(extract(0b1100_0010, 6, 0) == 0b1000010)
        assert(extract(0b1100_0010, 6, 6) == 0b1)
        assert(extract(0b1100_0010, 7, 6) == 0b11)
        assert(extract(0b1000110, tobit=4) == 0b100)
        assert(extract(0b0011_1010, 4, 2) == 0b110)
        assert(extract(0b0001, tobit=0) == 0b1)
        assert(extract(0b0101, 1, 1) == 0b0)

    def combine_test():
        print(bin(combine(0b0010_0000, 0b1110_0001, 0b0000_0010)))

    combine_test()