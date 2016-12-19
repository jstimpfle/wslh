from types import Value, Struct, List, Dict, Settable, Query


def add_rows(database, query, cols, rows):
    key = tuple(cols.index(v) for v in query.variables)
    database[query.table] += [tuple(row[i] for i in key) for row in rows]


def todb_value(cols, rows, objs, spec, database):
    idx = cols.index(spec.variable)
    for row, obj in zip(rows, objs):
        row[idx].set(obj)


def todb_struct(cols, rows, objs, spec, database):
    if spec.query is not None:
        nextcols = cols + spec.query.freshvariables
        nextrows = [row + tuple(Settable() for _ in spec.query.freshvariables) for row, obj in zip(rows, objs) if obj is not None]
        add_rows(database, spec.query, nextcols, nextrows)
    else:
        nextcols = cols
        nextrows = rows
    for key in spec.childs:
        nextobjs = [obj[key] for obj in objs if obj is not None]
        todb(nextcols, nextrows, nextobjs, spec.childs[key], database)


def todb_list(cols, rows, objs, spec, database):
    nextcols = cols + spec.query.freshvariables
    nextrows = []
    nextobjs = []
    for row, lst in zip(rows, objs):
        for item in lst:
            nextrows.append(row + tuple(Settable() for _ in spec.query.freshvariables))
            nextobjs.append(item)
    add_rows(database, spec.query, nextcols, nextrows)
    todb(nextcols, nextrows, nextobjs, spec.childs['_val_'], database)


def todb_dict(cols, rows, objs, spec, database):
    nextcols = cols + spec.query.freshvariables
    nextrows = []
    nextobjs_keys = []
    nextobjs_vals = []
    for row, dct in zip(rows, objs):
        for key, val in dct.items():
            nextrows.append(row + tuple(Settable() for _ in spec.query.freshvariables))
            nextobjs_keys.append(key)
            nextobjs_vals.append(val)
    add_rows(database, spec.query, nextcols, nextrows)
    todb(nextcols, nextrows, nextobjs_keys, spec.childs['_key_'], database)
    todb(nextcols, nextrows, nextobjs_vals, spec.childs['_val_'], database)


def todb(cols, rows, objs, spec, database):
    assert len(rows) == len(objs)
    typ = type(spec)
    if typ == Value:
        todb_value(cols, rows, objs, spec, database)
    elif typ == Struct:
        todb_struct(cols, rows, objs, spec, database)
    elif typ == List:
        todb_list(cols, rows, objs, spec, database)
    elif typ == Dict:
        todb_dict(cols, rows, objs, spec, database)
    else:
        assert False
