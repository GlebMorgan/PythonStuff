




if __name__ == '__main__':

    from contextlib import contextmanager

    @contextmanager
    def TAG(tag):
        print(f"tag is {tag}")
        yield
        print(f"cleared tag {tag}")

    class Const:
        def __rrshift__(self, other): return other
        def __lt__(self, other):  return other
        def __rmatmul__(self, other):  return other
        def __matmul__(self, other):  return self
        def __ror__(self, other):  return other
        def __or__(self, other):  return self

    const = Const()
    lazy = Const()

    class T:
        a = 1
        b = 2

        with TAG('x') |const |lazy:
            c: int = 5
            d: int = 7 |const |lazy

        e = 8
        f = 9

    print(dir(T()))