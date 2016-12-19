from types import Value, Struct, List, Query


def find_child_rows(cols, rows, objs, query, database):
    assert len(rows) == len(objs)

    freshidxs = tuple(i for i, v in enumerate(query.variables) if v in query.freshvariables)
    fkeyvars = [v for v in query.variables if v not in query.freshvariables]
    fkey_local = tuple(query.variables.index(v) for v in fkeyvars)
    fkey_foreign = tuple(cols.index(v) for v in fkeyvars)

    index = {}

    for row, obj in zip(rows, objs):
        key = tuple(row[i] for i in fkey_foreign)
        index[key] = row, obj, []

    newcols = cols + query.freshvariables
    newrows = []
    newobjs = []

    for row in database[query.table]:
        key = tuple(row[i] for i in fkey_local)
        frow, fobj, flist = index[key]
        newrow = frow + tuple(row[i] for i in freshidxs)
        flist.append(newrow)
        newrows.append(newrow)
        newobjs.append(fobj)

    return newcols, newrows, newobjs, index.values()


def fromdb_value(cols, rows, objs, spec, database):
    if spec.query is not None:
        newcols, newrows, newobjs, _ = find_child_rows(cols, rows, objs, spec.query, database)
    else:
        newcols, newrows, newobjs = cols, rows, objs

    idx = newcols.index(spec.variable)
    return [(newobj, newrow[idx]) for newobj, newrow in zip(newobjs, newrows)]


def fromdb_struct(cols, rows, objs, spec, database):
    structs = [None] * len(objs)
    ids = range(len(objs))

    if spec.query is not None:
        newcols, newrows, newids, _ = find_child_rows(cols, rows, ids, spec.query, database)
    else:
        newcols, newrows, newids = cols, rows, ids

    for i in newids:
        structs[i] = {}

    for key in spec.childs:
        pairs = fromdb(newcols, newrows, newids, spec.childs[key], database)
        for i, val in pairs:
            structs[i][key] = val

    return list(zip(objs, structs))


def fromdb_list(cols, rows, objs, spec, database):
    lsts = [[] for _ in objs]

    newcols, newrows, newobjs, _ = find_child_rows(cols, rows, lsts, spec.query, database)

    pairs = fromdb(newcols, newrows, newobjs, spec.childs['_val_'], database)
    for lst, val in pairs:
        lst.append(val)

    return list(zip(objs, lsts))


def fromdb(cols, rows, objs, spec, database):
    assert len(rows) == len(objs)
    typ = type(spec)
    if typ == Value:
        return fromdb_value(cols, rows, objs, spec, database)
    elif typ == List:
        return fromdb_list(cols, rows, objs, spec, database)
    elif typ == Struct:
        return fromdb_struct(cols, rows, objs, spec, database)
    else:
        assert False
