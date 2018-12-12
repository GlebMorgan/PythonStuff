from functools import reduce


def rfc1071(seqBytes):
    if (len(seqBytes) % 2): seqBytes += b'\x00'
    chsum = sum((x<<8|y for x, y in zip(seqBytes[::2], seqBytes[1::2])))
    chsum = (chsum & 0xFFFF) + (chsum >> 16)
    return int.to_bytes((~chsum) & 0xFFFF, length=2, byteorder='big')


def lrc(msgBytes):
    return int.to_bytes(reduce(lambda x,y: x^y, msgBytes), length=1, byteorder='big')


if __name__ == '__main__':
    import random
    from Timer import timer

    def _ref_lrc():
        print(f"{0x5A^0x0E^0x06^0x80^0x9F^0x71^0x01^0x81^0x43^0x00^0x00^0x00^0x01^0x00^0x00^0x00^0x00^0x00:X}")


    def _ref_lrc2(a):
        res = 0
        for b in a:
            res = res^b
        return int.to_bytes(res, length=1, byteorder='big')


    def test_lrc():
        a = bytes.fromhex("".join([random.choice('0123456789ABCDEF') for i in range(10_000_000)]))
        print(lrc(a))
        print(_ref_lrc2(a))


    def test_rfc1071_zip():
        a = bytes.fromhex("".join([random.choice('0123456789ABCDEF') for i in range(10_000_000)]))

        with Timer("rfc1071 zip"):
            v = rfc1071_zip(a)
        print(v)

        with Timer("rfc1071 map"):
            v = rfc1071_map(a)
        print(v)

        with Timer("rfc1071"):
            v2 = rfc1071(a)
        print(v2)

        with Timer("rfc1071 direct"):
            v3 = rfc1071_sumdirectly(a)
        print(v3)

        with Timer("rfc1071 no even check"):
            v4 = rfc1071_evenbytes(a)
        print(v4)


    test_lrc()
