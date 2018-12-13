from functools import reduce

def set(value, bits):
    """
    Set specified bits to 1 and return new binary number

    :param value: set bits of this number
    :type value: int
    :param bits: iterable with bits indices that need to be set
    :type bits: collections.abc.Iterable
    :return: modified number
    """

    if (not hasattr(bits, '__iter__')): bits = (bits,)
    for bit in bits: value |= (1 << bit)
    return value


def clear(value, bits):
    """
    Set specified bits to 0 and return new binary number

    :param value: set bits of this number
    :type value: int
    :param bits: iterable with bits indices that need to be cleared
    :type bits: collections.abc.Iterable
    :return: modified number
    """
    if (not hasattr(bits, '__iter__')): bits = (bits,)
    for bit in bits: value &= ~(1 << bit)
    return value


def combine(*values):
    return reduce(lambda v1,v2: v1 | v2, values)


def split(): NotImplemented


if __name__ == '__main__':
    def set_test():
        assert (set_bits(0b0011, (2, 3)) == 0b1111)
        assert (set_bits(0b0000, (0, 1, 2, 3)) == 0b1111)
        assert (set_bits(0b0011, ()) == 0b0011)
        assert (set_bits(0b1111, (1, 2, 2, 3)) == 0b1111)
        assert (set_bits(0b1111, ()) == 0b1111)
        assert (set_bits(0b0000, (0, 1, 2, 3, 4)) == 0b11111)
        assert (set_bits(0b0000_0000, (8)) == 0b1_0000_0000)
        assert (set_bits(0b1000_0000, ()) == 128)
        assert (set_bits(0b1000_0000, (7)) == 0b1000_0000)
        assert (set_bits(0b0000_0001, (7)) == 0b1000_0001)
        assert (set_bits(0b1, 0) == 0b1)
        print("DONE")

    def clear_test():
        assert(clear(0b0100, (0,2)) == 0)
        assert(clear(0b0000, (4)) == 0)
        assert(clear(0b0001, (2)) == 1)
        print("DONE")


    print(bin(combine(0b0010_0000, 0b1110_0001, 0b0000_0010)))