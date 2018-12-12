def rfc1071str(msgStr):
    if(len(msgStr) % 4 != 0): msgStr += "00"
    octetPairs = list(map(''.join, zip(*[iter(msgStr)]*4)))
    chsum = sum([int(dOctet, 16) for dOctet in octetPairs])
    chsum = (chsum & 0xFFFF) + (chsum >> 16)
    return (~chsum) & 0xFFFF

if __name__ == '__main__':
    msgStr = "5A-0E-06-80-9F-71-01-81-43-00-00-00-01-00-00-00-00-00"
    msgStr = "".join("".join(msgStr.split('-')).split(' '))
    print(str(hex(RFC1071(msgStr)))[2:].upper())
    a=0xFFFF
    print(bin(a))
    print(bin(~a))
    print(RFC1071(msgStr))
