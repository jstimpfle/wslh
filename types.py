Value = 0
Struct = 1
List = 2


class Settable():
    def __init__(self):
        self.x = None

    def set(self, x):
        self.x = x

    def get(self):
        return self.x

    def __repr__(self):
        if self.x is None:
            return '?'
        else:
            return '%s' %(self.x,)


class Spec:
    def __init__(self, typ, childs, query, variable=None):
        assert typ in [Value, Struct, List]
        if childs is not None:
            for key, val in childs.items():
                assert isinstance(key, str)
                assert isinstance(val, Spec)
        if query is not None:
            assert isinstance(query, Query)
        if variable is not None:
            assert isinstance(variable, str)
        self.typ = typ
        self.childs = childs
        self.query = query
        self.variable = variable


class Query:
    def __init__(self, freshvariables, table, variables):
        self.freshvariables = freshvariables
        self.table = table
        self.variables = variables
