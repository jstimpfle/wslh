"""Just looking for a possible implementation of WSL-H"""

import collections
import re


class StructuralType:
    pass


class SimpleValue(StructuralType):
    def __init__(self, query_variable, query):
        self.query_variable = query_variable
        self.query = query

    def __repr__(self):
        return str(self.query_variable)


class Struct(StructuralType):
    def __init__(self, sub, query):
        self.sub = sub
        self.query = query

    def __repr__(self):
        return str(self.sub)


class Set(StructuralType):
    def __init__(self, query_variable, query):
        assert query is not None
        self.query_variable = query_variable
        self.query = query

    def __repr__(self):
        return str(self.query_variable)


class List(StructuralType):
    def __init__(self, query_variable, query):
        assert query is not None
        self.query_variable = query_variable
        self.query = query

    def __repr__(self):
        return str(self.query_variable)


class Dict(StructuralType):
    def __init__(self, key_variable, val_variable, query):
        assert query is not None
        self.key_variable = key_variable
        self.val_variable = val_variable
        self.query = query

    def __repr__(self):
        return '(%s => %s)' %(str(self.key_variable), str(self.val_variable))


class Reference(StructuralType):
    def __init__(self, name, index=None, child=None):
        """
        Args:
            name (str): A member name (relative to the root of the namespace or
                the preceding element)
            index (str): If *name* references a dict, *index* is the name of an
                in-scope variable that is used as an index into the dict.
                It must be *None* if *name* doesn't reference a dict.
                Otherwise it must be given if *child* is given, and is optional
                otherwise.
            child (Reference): If given, where the reference leads from here.
        """
        if name is not None and not isinstance(name, str):
            raise ValueError('"name" must be None or a str')
        if index is not None and not isinstance(index, str):
            raise ValueError('"index" must be None or a str')
        if child is not None and not isinstance(child, Reference):
            raise ValueError('"child" must be None or another Reference')

        self.name = name
        self.child = child
        self.index = index

    def __repr__(self):
        out = self.name
        if self.index is not None:
            out += "["
            out += self.index
            out += "]"
        if self.child is not None:
            out += "."
            out += str(self.child)
        return out


class ParseError(Exception):
    pass


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
    return i, vs


def parse_freevars(line, i):
    return parse_identifier_list(line, i, empty_allowed=True)


def parse_clause(line, i):
    return parse_identifier_list(line, i, empty_allowed=False)


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
    i = parse_keyword(line, i, 'for', '(option) "for" keyword')
    i = parse_space(line, i)
    i, vs = parse_freevars(line, i)
    i = parse_space(line, i)
    i, q = parse_clause(line, i)
    # XXX
    return i, (vs, q)


def parse_line(line):
    """
    cases:

      MEMBER_VALUE     := TYPE (QUERY)?
      TYPE             := "value" | "option" | "struct" | "set" | "dict" | 
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

    if membertype in ["value", "option", "reference"]:
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


def parse_tree(lines, li=None, curindent=None):
    if li is None:
        li = 0
    if curindent is None:
        curindent = 0

    x = collections.OrderedDict()
    while li < len(lines):
        indent, membername, membertype, membervariable, query, line = lines[li]

        if indent < curindent:
            break
        if indent > curindent:
            raise ParseError('Wrong amount of indentation (need %d) at %s' %(curindent, line.desc()))

        if membertype in ["struct", "set", "list", "dict"]:
            assert membervariable is None
            li, sub = parse_tree(lines, li+1, curindent + 4)

            if membertype == "struct":
                for x in (x for x in sub.keys() if x.startswith('_')):
                    raise ParseError('Struct member at %s: child %s: must not start with underscore' %(line.desc(), x))
                spec = Struct(sub, query)

            elif membertype == "set":
                if set(sub) != set(['_val_']):
                    raise ParseError('Set member at %s: Need _val_ child (and no more)' %(line.desc(),))
                spec = Set(sub['_val_'], query)

            elif membertype == "list":
                if set(sub) != set(['_val_']):
                    raise ParseError('List member at %s: Need _val_ child (and no more)' %(line.desc(),))
                spec = List(sub['_val_'], query)

            elif membertype == "dict":
                if set(sub) != set(['_key_', '_val_']):
                    raise ParseError('Dict member at %s: Need _key_ and _val_ childs (and no more)' %(line.desc(), sub))
                spec = Dict(sub['_key_'], sub['_val_'], query)

        else:
            assert membervariable is not None

            if membertype == "value":
                spec = SimpleValue(membervariable, query)

            elif membertype == "reference":
                spec = membervariable  # XXX

            li += 1

        x[membername] = spec
    return li, x


def testit():
    spec = """\
Person: dict for (pid fn ln abbr) (Person pid fn ln abbr)
    _key_: value pid
    _val_: struct
        id: value pid
        firstname: value fn
        lastname: value bl
        abbr: value abbr
        lecturing: dict for (cid) (Lecturer pid cid)
            _key_: value cid
            _val_: reference Course[cid]
        tutoring: dict for (cid) (Tutor pid cid)
            _key_: value cid
            _val_: reference Course[cid]

Course: dict for (cid name) (Course cid name)
    _key_: value cid
    _val_: struct
        id: value cid
        name: value name
        lecturer: list for (pid) (Lecturer pid cid)
            _val_: reference Person[pid]
        tutor: list for (pid) (Tutor pid cid)
            _val_: reference Person[pid]

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

    _, bar = parse_tree(parsed_lines)
    print('Tree:')
    print()
    print(bar)
    print()


if __name__ == '__main__':
    testit()
