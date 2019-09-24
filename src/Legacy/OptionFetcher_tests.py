from __future__ import annotations as annotations_feature


class OptionFetcher(dict):
    #
    # class Option:
    #     """ Option descriptor """
    #     __slots__ = 'instance', 'owner'
    #
    #     def __init__(self, owner: OptionFetcher):
    #         self.owner = owner
    #
    #     def __call__(self, par: str):
    #         optionname = self.owner.targetDict.popitem()[0]
    #         self.owner.validatePar()  # TODO
    #         self.owner.targetDict[optionname] = par
    #
    #     def __getattr__(self, item):

    class Option:
        """ Option descriptor """

        __slots__ = 'name'

        def __init__(self, optionname):
            self.name = optionname

        def __get__(self, instance: OptionFetcher, owner):
            # TODO: check for duplicates
            instance.targetDict[self.name] = True
            return instance

    def __init__(self, target=None):
        self.targetDict = target if target else self
        for optionname in Attr._options_.keys():
            setattr(self, optionname, self.Option(optionname))
        super().__init__()

    def __call__(self, par):
        optionname = self.targetDict.popitem()[0]
        self.validatePar(optionname, par)
        self.targetDict[optionname] = par
        return self

    def validatePar(self, option, par):
        return NotImplemented  # TODO


class Section(OptionFetcher): pass

class Attr(OptionFetcher):
    _options_ = dict.fromkeys(('const', 'lazy',), False)