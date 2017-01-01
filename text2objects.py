import re

from datatypes import Value, Struct, List, Dict


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


def parse_keyword(indent, text, i):
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


def parse_string(indent, text, i):
    end = len(text)
    start = i
    m = re.match(r'^\[[a-zA-Z 0-9 _-]*\]', text[i:])
    if m is None:
        raise make_parse_exc('String [in square bracket style] expected but found %s' %(text[i:],), text, i)
    i += m.end(0)
    return i, text[start+1:i-1]


def parse_int(indent, text, i):
    end = len(text)
    start = i
    m = re.match(r'^(0|-?[1-9][0-9]*)', text[i:])
    if m is None:
        raise make_parse_exc('Integer expected', text, i)
    i += m.end(0)
    return i, int(text[start:i])


def parse_block(dct, indent, text, i):
    nextindent = indent + 4
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
        i, val = parser(nextindent, text, i)
        out.append((kw, val))
    return i, out


def space_and_then(valueparser):
    def space_and_then_parser(indent, text, i):
        i = parse_space(text, i)
        i, v = valueparser(indent, text, i)
        return i, v
    return space_and_then_parser


def newline_and_then(valueparser):
    def newline_and_then_parser(indent, text, i):
        i = parse_newline(text, i)
        i, v = valueparser(indent, text, i)
        return i, v
    return newline_and_then_parser


def make_keyvalue_parser(keyparser, valueparser):
    def keyvalue_parser(indent, text, i):
        i = parse_space(text, i)
        i, k = keyparser(indent, text, i)
        i = parse_newline(text, i)
        i, v = valueparser(indent, text, i)
        return i, (k, v)
    return keyvalue_parser


def make_struct_parser(dct):
    def struct_parser(indent, text, i):
        i, items = parse_block(dct, indent, text, i)
        wantkeys = set(dct.keys())
        havekeys = set(k for k, v in items)
        invalid = havekeys.difference(wantkeys)
        struct = {}
        for k, v in items:
            if k not in wantkeys:
                raise make_parse_exc('Invalid key: %s' %(k,), text, i)
            if k in items:
                raise make_parse_exc('Duplicate key: %s' %(k,), text, i)
            struct[k] = v
        for k in wantkeys:
            struct.setdefault(k, None)
        return i, struct
    return struct_parser


def make_dict_parser(key_parser, val_parser):
    item_parser = make_keyvalue_parser(key_parser, val_parser)
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


def make_parser_from_spec(spec):
    typ = type(spec)

    if typ == Value:
        # XXX: just to be able to test other code while it is developped
        if spec.primtype == 'Int':
            return parse_int
        elif spec.primtype == 'String':
            return parse_string
        elif spec.primtype.endswith('ID'):
            return parse_identifier
        else:
            assert False
    elif typ == Struct:
        dct = {}
        for k, v in spec.childs.items():
            subparser = make_parser_from_spec(v)
            if type(v) == Value:
                dct[k] = space_and_then(subparser)
            else:
                dct[k] = newline_and_then(subparser)
        return make_struct_parser(dct)
    elif typ == List:
        val_parser = make_parser_from_spec(spec.childs['_val_'])
        for k, v in spec.childs.items():
            subparser = make_parser_from_spec(v)
            if type(v) == Value:
                p = space_and_then(subparser)
            else:
                p = newline_and_then(subparser)
        return make_list_parser(p)
    elif typ == Dict:
        key_parser = make_parser_from_spec(spec.childs['_key_'])
        val_parser = make_parser_from_spec(spec.childs['_val_'])
        return make_dict_parser(key_parser, val_parser)

    assert False  # missing case
