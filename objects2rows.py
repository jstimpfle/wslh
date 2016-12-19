from types import Value, Struct, List, Settable, Spec, Query


def add_rows(database, query, columns, rows):
    key = tuple(columns.index(v) for v in query.variables)
    database[query.table] += [tuple(row[i] for i in key) for row in rows]


def todb_value(columns, rows, objs, spec, database):
    idx = columns.index(spec.variable)
    for row, obj in zip(rows, objs):
        row[idx].set(obj)


def todb_struct(columns, rows, objs, spec, database):
    if spec.query is not None:
        nextcolumns = columns + spec.query.freshvariables
        nextrows = [row + [Settable() for _ in spec.query.freshvariables] for row, obj in zip(rows, objs) if obj is not None]
        add_rows(database, spec.query, nextcolumns, nextrows)
    else:
        nextcolumns = columns
        nextrows = rows
    for key in spec.childs:
        nextobjs = [obj[key] for obj in objs if obj is not None]
        todb(nextcolumns, nextrows, nextobjs, spec.childs[key], database)


def todb_list(columns, rows, objs, spec, database):
    nextcolumns = columns + spec.query.freshvariables
    nextrows = []
    nextobjs = []
    for row, lst in zip(rows, objs):
        for item in lst:
            nextrows.append(row + [Settable() for _ in spec.query.freshvariables])
            nextobjs.append(item)
    todb(nextcolumns, nextrows, nextobjs, spec.childs['_val_'], database)
    add_rows(database, spec.query, nextcolumns, nextrows)


def todb(columns, rows, objs, spec, database):
    assert len(rows) == len(objs)
    if spec.typ == Value:
        todb_value(columns, rows, objs, spec, database)
    elif spec.typ == Struct:
        todb_struct(columns, rows, objs, spec, database)
    elif spec.typ == List:
        todb_list(columns, rows, objs, spec, database)
