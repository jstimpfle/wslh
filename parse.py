import collections
import re
from datatypes import Value, Struct, Set, List, Dict, Reference, Query


class ParseError(Exception):
    pass


class PrettyOrderedDict(collections.OrderedDict):
    __repr__ = dict.__repr__


class Line(str):
    """A single-line *str* with line number information for better error messages"""

    def __init__(self, string, lineno):
        str.__init__(string)
        self.lineno = lineno

    def __new__(cls, string, lineno):
        return str.__new__(cls, string)

    def desc(self, i=None):
        if i is None:
            return 'line %d' %(self.lineno+1,)
        else:
            return 'line %d, character %d' %(self.lineno+1, i+1)


def iter_lines(it):
    for i, line in enumerate(it):
        yield Line(line, i)


def parse_sequence(line, i, sequence, typedesc):
    if not line[i:].startswith(sequence):
        raise ParseError('Expected "%s" at %s' %(typedesc, line.desc(i)))
    return i + len(sequence)


def parse_regex(line, i, regex, typedesc):
    m = re.match(regex, line[i:])
    if m is None:
        raise ParseError('Expected "%s" at %s' %(typedesc, line.desc(i)))
    return i + m.end(0), m.group(0)


def parse_space(line, i):
    return parse_sequence(line, i, ' ', 'space character')


def parse_identifier(line, i):
    return parse_regex(line, i, r'[a-zA-Z_][a-zA-Z0-9_]*', 'identifier token')


def parse_variable(line, i):
    return parse_regex(line, i, r'[a-zA-Z][a-zA-Z0-9_]*', 'variable name')


def parse_keyword(line, i, keyword, desc):
    try:
        i, kw = parse_identifier(line, i)
    except ParseError as e:
        raise ParseError('Expected "%s" at %s' %(typedesc, line.desc(i)))
    if kw != keyword:
        raise ParseError('Expected "%s" but found identifier "%s" at "%s"', desc, kw, line.desc(i))
    return i


def parse_index(line, i):
    end = len(line)
    try:
        i = parse_sequence(line, i, '[', 'opening bracket "["')
        i, name = parse_variable(line, i)
        i = parse_sequence(line, i, ']', 'closing bracket "]"')
    except ParseError as e:
        raise ParseError('Expected bracketed index expression at %s' %(line.desc(i))) from e
    return i, name


def parse_identifier_list(line, i, empty_allowed):
    """Parse a list of identifiers in parentheses, like (a b c)"""
    end = len(line)
    i = parse_sequence(line, i, '(', '"(" character')
    vs = []
    while i < end:
        if line[i] == ')':
            if not vs and not empty_allowed:
                raise ParseError('Empty identifier list not allowed at %s' %(line.desc(i)))
            break
        if vs:
            i = parse_space(line, i)
        i, v = parse_variable(line, i)
        vs.append(v)
    i = parse_sequence(line, i, ')', '")" character')
    return i, tuple(vs)


def parse_freshvars(line, i):
    i, vs = parse_identifier_list(line, i, empty_allowed=True)
    return i, tuple(vs)


def parse_clause(line, i):
    i, names = parse_identifier_list(line, i, empty_allowed=False)
    return i, (names[0], tuple(names[1:]))


def parse_indent(line):
    end = len(line)
    i = 0
    while i < end and line[i] == ' ':
        i += 1
    if i < end and line[i] == '\t':
        raise ParseError('Tabs not allowed for indent at %s' %(line.desc(i),))
    return i


def parse_member_type(line, i):
    ts = ["value", "option", "reference", "struct", "set", "list", "dict"]
    i, w = parse_identifier(line, i)
    if w not in ts:
        raise ParseError('Not a valid member type: "%s". Valid types are: %s at %s' %(w, ' '.join(ts), line.desc(i)))
    return i, w


def parse_member_variable(line, i):
    end = len(line)
    i, name = parse_identifier(line, i)
    index = None
    child = None
    if i < end and line[i] == '[':
        i, index = parse_index(line, i)
    if i < end and line[i] == '.':
        i += 1
        i, child = parse_member_variable(line, i)
    return i, Reference(name=name, index=index, child=child)


def parse_query(line, i):
    i = parse_keyword(line, i, 'for', '(optional) "for" keyword')
    i = parse_space(line, i)
    i, freshvariables = parse_freshvars(line, i)
    i = parse_space(line, i)
    i, (table, variables) = parse_clause(line, i)
    return i, Query(freshvariables, table, variables)


def parse_line(line):
    """
    cases:

      MEMBER_VALUE     := TYPE (QUERY)?
      TYPE             := "value" | "option" | "struct" | "set" | "dict"
      QUERY            := FOR_KEYWORD FREEVARS_LIST QUERY_LIST
      FREEVARS_LIST    := IDENTIFIERS_LIST
      QUERY_LIST       := IDENTIFIERS_LIST
      IDENTIFIER_LIST0 := LPAREN IDENTIFIERS0 RPAREN
      IDENTIFIER_LIST1 := LPAREN IDENTIFIERS1 RPAREN
      IDENTIFIERS0     := (IDENTIFIERS1)?
      IDENTIFIERS1     := IDENTIFIER (SPACE IDENTIFIERS1)?
      FOR_KEYWORD      := "for"
      SPACE            := " "
      LPAREN           := "("
      RPAREN           := ")"
    """
    end = len(line)

    i = parse_indent(line)
    indent = i

    try:
        i, membername = parse_identifier(line, i)
    except ParseError as e:
        raise ParseError('Expected a "member: declaration" line at %s' %(line.desc())) from e

    i = parse_sequence(line, i, ':', '":" after member name')
    i = parse_space(line, i)

    try:
        i, membertype = parse_member_type(line, i)
    except ParseError as e:
        raise ParseError('Failed to parse member type at %s' %(line.desc(i))) from e

    if membertype in ["value", "option"]:
        i = parse_space(line, i)
        try:
            i, membervariable = parse_identifier(line, i)
        except ParseError as e:
            raise ParseError('Failed to parse member variable at %s' %(line.desc(i))) from e
    elif membertype in ["reference"]:
        i = parse_space(line, i)
        try:
            i, membervariable = parse_member_variable(line, i)
        except ParseError as e:
            raise ParseError('Failed to parse member variable at %s' %(line.desc(i))) from e
    else:
        membervariable = None

    if i < end:
        i = parse_space(line, i)
        i, query = parse_query(line, i)
    else:
        query = None

    return indent, membername, membertype, membervariable, query, line


def parse_lines(lines):
    return [parse_line(line) for line in iter_lines(lines) if line]


def parse_tree(lookup_type, lines, primtypes=None, li=None, curindent=None):
    if primtypes is None:
        primtypes = {}
    if li is None:
        li = 0
    if curindent is None:
        curindent = 0

    tree = PrettyOrderedDict()
    while li < len(lines):
        indent, membername, membertype, membervariable, query, line = lines[li]

        if indent < curindent:
            break
        if indent > curindent:
            raise ParseError('Wrong amount of indentation (need %d) at %s' %(curindent, line.desc()))

        def infer_types(query):
            for i, v in enumerate(query.variables):
                typ = lookup_type(query.table, i)
                if v in query.freshvariables:
                    primtypes[v] = typ
                elif v not in primtypes:
                    assert False
                elif primtypes[v] != typ:
                    raise ParseError('Type mismatch: Usage of variable "%s" in this place of the query requires type "%s", but it was inferred to be of type "%s"' %(membervariable, typ, primtypes[v]))

        if query is not None:
            infer_types(query)

        if membertype in ["struct", "set", "list", "dict"]:
            assert membervariable is None
            li, childs = parse_tree(lookup_type, lines, primtypes, li+1, curindent + 4)

            if membertype == "struct":
                for x in childs.keys():
                    if x.startswith('_'):
                        raise ParseError('Struct member at %s: child %s: must not start with underscore' %(line.desc(), x))
                spec = Struct(childs, query)

            elif membertype == "set":
                if set(childs) != set(['_val_']):
                    raise ParseError('Set member at %s: Need _val_ child (and no more)' %(line.desc(),))
                spec = Set(childs, query)

            elif membertype == "list":
                if set(childs) != set(['_val_']):
                    raise ParseError('List member at %s: Need _val_ child (and no more)' %(line.desc(),))
                spec = List(childs, query)

            elif membertype == "dict":
                if set(childs) != set(['_key_', '_val_']):
                    raise ParseError('Dict member at %s: Need _key_ and _val_ childs (and no more)' %(line.desc(), childs))
                spec = Dict(childs, query)

        else:
            assert membervariable is not None

            if membertype == "value":
                if membervariable not in primtypes:
                    raise ParseError('At %s: Variable not in scope: "%s"' %(line.desc(), membervariable))

                spec = Value(membervariable, query, primtypes[membervariable])

            elif membertype == "reference":
                raise NotImplementedError()

            else:
                assert False

            li += 1

        tree[membername] = spec
    return li, tree


def make_type_lookup(wslschema):
    def lookup_type(tablename, col_index_0based):
        table = wslschema.tables.get(tablename)
        if table is not None and len(table.columns) > col_index_0based:
            return table.columns[col_index_0based]
    return lookup_type


def parse_spec(wslschema, spec):
    assert isinstance(spec, str)

    lookup_type = make_type_lookup(wslschema)

    parsed_lines = parse_lines(spec.splitlines())
    _, tree = parse_tree(lookup_type, parsed_lines)

    return Struct(tree, None)


def testit():
    import wsl
    wslschema = wsl.parse_schema("""\
DOMAIN PID ID
DOMAIN CID ID
DOMAIN String String
TABLE Person PID String String String
TABLE Course CID String
TABLE Tutor PID CID
TABLE Lecturer PID CID
REFERENCE TutorPid Tutor pid * => Person pid * * *
REFERENCE TutorCid Tutor * cid => Course cid *
REFERENCE LecturerPid Tutor pid * => Person pid * * *
REFERENCE LecturerCid Tutor * cid => Course cid *
""")

    lookup_type = make_type_lookup(wslschema)

    spec = """\
Person: dict for (pid fn ln abbr) (Person pid fn ln abbr)
    _key_: value pid
    _val_: struct
        id: value pid
        firstname: value fn
        lastname: value ln
        abbr: value abbr
        lecturing: list for (cid) (Lecturer pid cid)
            _val_: value cid
        tutoring: list for (cid) (Tutor pid cid)
            _val_: value cid

Course: dict for (cid name) (Course cid name)
    _key_: value cid
    _val_: struct
        id: value cid
        name: value name
        lecturer: list for (pid) (Lecturer pid cid)
            _val_: value pid
        tutor: list for (pid) (Tutor pid cid)
            _val_: value pid

Tutor: set for (pid cid) (Tutor pid cid)
    _val_: struct
        person: value pid
        course: value cid

Lecturer: set for (pid cid) (Lecturer pid cid)
    _val_: struct
        person: value pid
        course: value cid
"""

    parsed_lines = parse_lines(spec.splitlines())
    print('Lines:')
    print()
    print(parsed_lines)
    print()

    _, bar = parse_tree(lookup_type, parsed_lines)
    print('Tree:')
    print()
    print(bar)
    print()


if __name__ == '__main__':
    testit()
