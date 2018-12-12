from functools import reduce


def rfc1071(seqBytes):
    """
    Calculate 2-byte RFC1071 checksum of bytes sequence
    :param seqBytes: (bytes) sequence to calculate a checksum of, any size
    :return:         (bytes) RFC1071 checksum, len=2
    """
    if (len(seqBytes) % 2): seqBytes += b'\x00'
    chsum = sum((x<<8|y for x, y in zip(seqBytes[::2], seqBytes[1::2])))
    chsum = (chsum & 0xFFFF) + (chsum >> 16)
    return int.to_bytes((~chsum) & 0xFFFF, length=2, byteorder='big')


def lrc(msgBytes):
    """
    Calculate 1-byte LRC checksum (parity byte) of bytes sequence.
    :param msgBytes: (bytes) sequence to calculate a checksum of, any size
    :return:         (bytes) parity byte checksum, len=1
    """
    return int.to_bytes(reduce(lambda x,y: x^y, msgBytes), length=1, byteorder='big')


if __name__ == '__main__':
    import random

    def _ref_lrc2(a):
        res = 0
        for b in a:
            res = res^b
        return int.to_bytes(res, length=1, byteorder='big')

    def test_lrc():
        a = bytes.fromhex("".join([random.choice('0123456789ABCDEF') for i in range(1_000_000)]))
        print(lrc(a))
        print(_ref_lrc2(a))


    test_lrc()
