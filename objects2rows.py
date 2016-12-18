from types import Value, Struct, List, Settable, Spec, Query


def add_rows(database, query, columns, rows):
    key = tuple(columns.index(v) for v in query.variables)
    database[query.table] += [tuple(row[i] for i in key) for row in rows]


def todb_value(columns, rows, objects, spec, database):
    idx = columns.index(spec.variable)
    for row, obj in zip(rows, objects):
        row[idx].set(obj)


def todb_struct(columns, rows, objects, spec, database):
    if spec.query is not None:
        nextcolumns = columns + spec.query.freshvariables
        nextrows = [row + [Settable() for _ in spec.query.freshvariables] for row in rows]
        add_rows(database, spec.query, nextcolumns, nextrows)
    else:
        nextcolumns = columns
        nextrows = rows
    for key in spec.childs:
        nextobjects = []
        for obj in objects:
            nextobjects.append(obj[key])
        todb(nextcolumns, nextrows, nextobjects, spec.childs[key], database)


def todb_list(columns, rows, objects, spec, database):
    nextcolumns = columns + spec.query.freshvariables
    nextrows = []
    nextobjects = []
    for row, obj in zip(rows, objects):
        for item in obj:
            nextrows.append(row + [Settable() for _ in spec.query.freshvariables])
            nextobjects.append(item)
    todb(nextcolumns, nextrows, nextobjects, spec.childs['_val_'], database)
    add_rows(database, spec.query, nextcolumns, nextrows)


def todb(columns, rows, objects, spec, database):
    if spec.typ == Value:
        todb_value(columns, rows, objects, spec, database)
    elif spec.typ == Struct:
        todb_struct(columns, rows, objects, spec, database)
    elif spec.typ == List:
        todb_list(columns, rows, objects, spec, database)


a = Spec(Value, None, None, 'a')
b = Spec(Value, None, None, 'b')
c = Spec(Value, None, None, 'c')
d = Spec(Value, None, None, 'd')
s = Spec(Struct, { 'a': a, 'b': b }, Query(['a', 'b'], 'foo', ['a', 'b', 'c']))
s2 = Spec(Struct, { 'c': c, 'd': d, 's': s }, None)
l = Spec(List, { '_val_': s2 }, Query(['c', 'd'], 'bar', ['c', 'd']))

database = {
    'foo': [],
    'bar': []
}

myobjects = [[
    { 'c': 1, 'd': 3, 's': { 'a': 666, 'b': 1024 } },
    { 'c': 2, 'd': 3, 's': { 'a': 666, 'b': 1024 } },
    { 'c': 3, 'd': 3, 's': { 'a': 666, 'b': 1024 } }
]]

todb([], [[] for _ in myobjects], myobjects, l, database)

print('foo')
print('===')
print(database['foo'])
print()

print('bar')
print('===')
print(database['bar'])
print()
