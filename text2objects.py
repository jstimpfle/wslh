import re


class ParseException(Exception):
    def __init__(self, msg, text, lineno, charno):
        self.msg = msg
        self.text = text
        self.lineno = lineno
        self.charno = charno

    def __str__(self):
        return 'At %d:%d: %s' %(self.lineno, self.charno, self.msg)


def make_parse_exc(msg, text, i):
    lines = text[:i].split('\n')
    lineno = len(lines)
    charno = i + 1 - sum(len(l) + 1 for l in lines[:-1])
    return ParseException(msg, text, lineno, charno)


def parse_space(text, i):
    end = len(text)
    start = i
    if i >= end or text[i] != ' ':
        raise make_parse_exc('Space character expected', text, i)
    return i + 1


def parse_newline(text, i):
    end = len(text)
    start = i
    if i >= end or text[i] != '\n':
        raise make_parse_exc('End of line (\\n) expected', text, i)
    return i + 1


def parse_keyword(identifier, text, i):
    end = len(text)
    start = i
    while i < end and text[i].isalpha():
        i += 1
    if i == start:
        raise make_parse_exc('Keyword expected', text, i)
    return i, text[start:i]


def parse_identifier(indent, text, i):
    end = len(text)
    start = i
    m = re.match(r'^[a-zA-Z][a-zA-Z0-9]*', text[i:])
    if m is None:
        raise make_parse_exc('Identifier expected', text, i)
    i += m.end(0)
    return i, text[start:i]


def parse_block(dct, indent, text, i):
    end = len(text)
    out = []
    while True:
        while i < end and text[i] == '\n':
            i += 1
        if i == end:
            break
        if not text[i:].startswith(' ' * indent):
            break
        i += indent
        i, kw = parse_keyword(indent, text, i)
        parser = dct.get(kw)
        if parser is None:
            raise make_parse_exc('Found unexpected field "%s"' %(kw,), text, i)
        i = parse_space(text, i)
        i, val = parser(indent + 4, text, i)
        out.append((kw, val))
    return i, out


def make_keyvalue_parser(keyparser, valueparser):
    def keyvalue_parser(indent, text, i):
        i, k = keyparser(indent, text, i)
        i, v = valueparser(indent, text, i)
        return i, (k, v)
    return keyvalue_parser


def make_struct_parser(dct):
    def struct_parser(indent, text, i):
        i = parse_newline(text, i)
        i, items = parse_block(dct, indent, text, i)
        missing = set(dct.keys()).difference(set(dict(items).keys()))
        if missing:
            raise make_parse_exc('Missing keys: %s' %(', '.join(missing),), text, i)
        if len(items) != len(dct):
            raise make_parse_exc('Duplicate keys in %s' %(', '.join(k for k, _ in items),), text, i)
        out = {}
        for k, v in items:
            if k in out:
                raise make_parse_exc('Duplicate member: %s' %(k,), text, i)
            out[k] = v
        return i, out
    return struct_parser


def make_dict_parser(value_parser):
    item_parser = make_keyvalue_parser(parse_identifier, value_parser)
    def dict_parser(indent, text, i):
        i, items = parse_block({ 'value': item_parser }, indent, text, i)
        out = {}
        for _, (k, v) in items:
            if k in out:
                raise make_parse_exc('Key "%s" used multiple times in this block' %(k,), text, i)
            out[k] = v
        return i, out
    return dict_parser


def make_list_parser(parser):
    def list_parser(indent, text, i):
        dct = { 'value': parser }
        i, items = parse_block(dct, indent, text, i)
        out = []
        for _, v in items:
            out.append(v)
        return i, out
    return list_parser


def doparse(parser, text):
    i, r = parser(0, text, 0)
    if i != len(text):
        raise make_parse_exc('Unconsumed text', text, i)
    return r


text = """\
value v1
    foo b
    bar c
value v2
    foo x
    bar y
"""

theparser = make_dict_parser(make_struct_parser({
    'foo': parse_identifier,
    'bar': parse_identifier
}))

x = doparse(theparser, text)
print(x)
