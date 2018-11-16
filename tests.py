class Context():
    def __init__(self, currObj):
        self._obj = currObj
        # object.__setattr__(self, 'obj', currObj)

    def __getattr__(self, name):
        return self._obj.__getattribute__(name)
        
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

def test1():
    class B():
        class C():
            def __init__(self):
                self.par = 1
            def max(self, x):
                print("B.C.max({})".format(x))

        def __init__(self):
            self.c = self.C()

    b = B()

    with Context(b.c) as this:
        print(this.par)
        this.max("ff")

def main():
    filename = "VanoAsked.txt"
    with open("C:/Users/Serge/Desktop/" + filename, "wt") as file:
        file.write("Hello Vano!")

if __name__ == '__main__':
    main()
