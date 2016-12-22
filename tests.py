import json

from datatypes import Value, Struct, List, Dict, Query
import rows2objects
import objects2rows


a = Value('a', None)
b = Value('b', None)
c = Value('c', None)
d = Value('d', None)
s = Struct({ 'a': a, 'b': b }, Query(('a', 'b'), 'foo', ('a', 'b', 'c')))
s2 = Struct({ 'c': c, 'd': d, 's': s }, None)
lst = Dict({ '_key_': c, '_val_': s2 }, Query(('c', 'd'), 'bar', ('c', 'd')))

mydatabase = {
    'foo': [(1, 2, 3), (4, 5, 6)], 
    'bar': [(3, 666), (6, 1024), (42, 0)]
}

myobject = {
    3: { 'c': 3, 'd': 666, 's': { 'a': 1, 'b': 2 } },
    6: { 'c': 6, 'd': 1024, 's': { 'a': 4, 'b': 5 } },
    42: { 'c': 42, 'd': 0, 's': None }
}


def json_repr(x):
    return json.dumps(x, sort_keys=True, indent=2)


def test_rows2objects():
    print()
    print('TESTING rows2objects()...')
    print('=========================')
    print()

    print('Database:')
    print('=========')
    for key, rows in sorted(mydatabase.items()):
        print(key)
        print('-' * len(key))
        for row in sorted(rows):
            print(row)
        print()

    [(topobject, subobject)] = rows2objects.rows2objects(lst, mydatabase)

    assert topobject is None
    assert isinstance(subobject, dict)

    print('RESULT')
    print('======')
    print(json_repr(subobject))

    return subobject


def test_objects2rows():
    print()
    print('TESTING objects2rows()...')
    print('=========================')
    print()

    print('Objects:')
    print('========')
    print(json_repr(myobject))

    database = objects2rows.objects2rows([myobject], lst)

    print()
    print('RESULTS')
    print()

    for table in ['bar', 'foo']:
        print(table)
        print('=' * len(table))
        for row in database[table]:
            print(row)
        print()

    return database


if __name__ == '__main__':
    objects = test_rows2objects()
    database = test_objects2rows()

    assert json_repr(objects) == json_repr(myobject)
    assert json_repr(database) == json_repr(mydatabase)
