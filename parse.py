"""Just looking for a possible implementation of WSL-H"""

import re


class ParseError(Exception):
    pass


def chardesc(line, i):
    end = len(line)
    if i < end:
        return "'%s'" %(line[i],)
    else:
        return '(EOL)'


class Reference:
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


def parse_space(line, i):
    if line[i:i+1] != ' ':
        raise ParseError('Expected space character but found %s at line %s, character %d' %(chardesc(line, i), line, i))
    return i+1


def parse_identifier(line, i):
    start = i
    m = re.match(r'[a-zA-Z_][a-zA-Z0-9_]*', line[i:])
    if m is None:
        raise ParseError('Expected variable but found %s at line %s, character %d'
                            %(chardesc(line, i), line, start))
    return i + m.end(0), m.group(0)


def parse_key(line, i):
    start = i
    end = len(line)
    while i < end and is_identifierchar(line[i]):
        i += 1
    if i == start:
        raise ParseError('Expected keyword but found %s character at line %s, character %d' %(chardesc(line, i), line, start))
    return i, line[start:i]


def parse_variable(line, i):
    i, v = parse_identifier(line, i)
    return i, v


def parse_index(line, i):
    end = len(line)
    if i == end or line[i] != '[':
        raise ParseError('Expected opening bracket "["')
    i += 1
    i, name = parse_variable(line, i)
    if i == end or line[i] != ']':
        raise ParseError('Expected closing bracket "]"')
    i += 1
    return i, name


def parse_string(line, i, s):
    if not line[i:].startswith(s):
        raise ParseError('Expected string "%s" but found %s at line %s, character %d' %(s, chardesc(line, i), line, i))
    return i + len(s)


def parse_identifier_list(line, i, empty_allowed):
    """Parse a list of identifiers in parentheses, like (a b c)"""
    end = len(line)
    i = parse_string(line, i, '(')
    vs = []
    while i < end:
        if line[i] == ')':
            if not vs and not empty_allowed:
                raise ParseError('Empty identifier list not allowed')
            break
        if vs:
            i = parse_space(line, i)
        i, v = parse_identifier(line, i)
        vs.append(v)
    i = parse_string(line, i, ')')
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
        raise ParseError('Tabs not allowed for indent')
    return i


def parse_member_type(line, i):
    ts = ["value", "option", "reference", "struct", "set", "list", "dict"]
    i, w = parse_identifier(line, i)
    if w not in ts:
        raise ParseError('Not a valid member type: "%s". Valid types are: %s'
                         %(w, ' '.join(ts)))
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
    i, w = parse_identifier(line, i)
    if w != 'for':
        raise ParseError('Expected (optional) "for" keyword following member type decl in line %s' %(line,))
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
        raise ParseError('Expected a "member: declaration" line') from e

    if line[i:i+2] != ': ':
        raise ParseError('Expected ": " after the member name')
    i += 2

    try:
        i, membertype = parse_member_type(line, i)
    except ParseError as e:
        raise ParseError('Failed to parse member type') from e

    if membertype in ["value", "option", "reference"]:
        i = parse_space(line, i)
        try:
            i, membervariable = parse_member_variable(line, i)
        except ParseError as e:
            raise ParseError('Failed to parse member variable') from e
    else:
        membervariable = None

    if i < end:
        i = parse_space(line, i)
        i, query = parse_query(line, i)
    else:
        query = None

    return indent, membername, membertype, membervariable, query


def parse_dict(lines, li=None, curindent=None):
    if li is None:
        li = 0
    if curindent is None:
        curindent = 0
    x = {}
    while li < len(lines):
        indent, membername, membertype, membervariable, query = lines[li]
        if indent < curindent:
            break
        if indent > curindent:
            raise ParseError('Wrong amount of indentation (need %d) in line %s' %(curindent, lines[li]))
        if membertype in ["struct", "set", "list", "dict"]:
            li, sub = parse_dict(lines, li+1, curindent + 4)
            if not sub:
                raise ParseError('Empty %s' %(membertype,))
            spec = membertype, sub, query
        else:
            spec = membertype, membervariable, query
            li += 1
        x[membername] = spec
    return li, x


def testit():
    spec = """
Person: dict for (pid fn ln abbr) (Person pid fn ln abbr)
    _key_: value pid
    _val_: struct
        id: value pid
        firstname: value fn
        lastname: value ln
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

    parsed_lines = []
    for line in spec.splitlines():
        if line:
            parsed_lines.append(parse_line(line))

    print('Lines:')
    print()
    print(parsed_lines)
    print()

    _, bar = parse_dict(parsed_lines)
    print('Tree:')
    print()
    print(bar)


if __name__ == '__main__':
    testit()
