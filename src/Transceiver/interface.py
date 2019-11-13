from abc import ABC


class Transceiver(ABC):
    token: str
    nTimeouts: int

    # def __new__(cls, *args, **kwargs):
    #     raise NotImplementedError(f"Class {cls.__name__} is an interface")

    def sendPacket(self, data: bytes) -> int: ...

    def receivePacket(self) -> bytes: ...

