from dataclasses import Field, field, is_dataclass, MISSING as N_A


# Native dataclasses.field signature (from docs):
#   field(*, default=MISSING, default_factory=MISSING, repr=True, hash=None, init=True, compare=True, metadata=None)


def dataclassField(value=N_A, tokens: str = '', tag: str = '', **kwargs):
    """ Provide a shortcut syntax for defining a dataclasses.field()
            value: default value for a field ([], {} and set() are automatically reassigned with default_factory)
            tokens: set of characters defining arguments to dataclass.field()
                n (no-init) ——► init=False
                r (repr)    ——► repr=True
                c (compare) ——► compare=True
            tag: if defined, sets dataclasses.field() metadata argument to specified STRING value;
                may denote field purpose or category
        Any native arguments to dataclasses.field() may be specified alongside,
            but any conflicts would be overridden with values specified by arguments introduced in this function
        Recommended import semantics:
            from dataclass_metadata_utils import dataclassField as f
    """

    tokens = ''.join(*tokens)
    field_kwargs = {}
    if isinstance(value, (list, dict, set)) and value is False:
        field_kwargs['default_factory'] = type(value)
    else:
        field_kwargs['default'] = value

    field_kwargs['init'] = 'n' not in tokens
    field_kwargs['repr'] = 'r' in tokens
    field_kwargs['compare'] = 'c' in tokens

    if tag: field_kwargs['metadata'] = tag

    kwargs.update(field_kwargs)
    return field(**kwargs)


def getFieldTag(field_object: Field):
    """ Fetch STRING value out of field_object.metadata attr
        Recommended import semantics:
            from dataclass_metadata_utils import getFieldTag as tag
    """
    return str(field_object.metadata)


def taggedAttrsIterator(dataclass, tag: str):
    """ Iterator over 'dataclass_field' attrs assigned with 'tag'. Yields (name, value) items """

    if not is_dataclass(dataclass) or isinstance(dataclass, type):
        raise ValueError(f"{dataclass.__class__.__name__} should be a dataclass instance")

    return ((df.name, getattr(dataclass, df.name)) for df in dataclass.fields() if str(df.metadata) == tag)


def taggedNamesIterator(dataclass, tag: str):
    """ Iterator over 'dataclass_field' attrs assigned with 'tag'. Yields attr names """

    if not is_dataclass(dataclass) or isinstance(dataclass, type):
        raise ValueError(f"{dataclass.__class__.__name__} should be a dataclass instance")

    return (df.name for df in dataclass.fields() if str(df.metadata) == tag)


def taggedValuesIterator(dataclass, tag: str):
    """ Iterator over 'dataclass_field' attrs assigned with 'tag'. Yields attr values """

    if not is_dataclass(dataclass) or isinstance(dataclass, type):
        raise ValueError(f"{dataclass.__class__.__name__} should be a dataclass instance")

    return (getattr(dataclass, df.name) for df in dataclass.fields() if str(df.metadata) == tag)
