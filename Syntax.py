import math
from enum import Enum, EnumMeta
import re

op_char_patt = r'[:.<>?/~!@;$%^&*+=|-]'

def contains(cls, item):
    if isinstance(item, cls):
        return item.name in cls._member_map_
    else:
        return item in cls._value2member_map_


EnumMeta.__contains__ = contains


class TokenType(Enum):
    Unknown = '?'
    StringLiteral = 'string'
    StringStart = 'string_start'
    StringPart = 'string_part'
    StringEnd = 'string_end'
    Number = 'number'
    Singleton = 'singleton'
    Operator = 'operator'
    Command = 'command'  # return, break, continue, ...
    Keyword = 'keyword'  # in, with, ...
    Name = 'name'
    GroupStart = '('
    GroupEnd = ')'
    ListStart = '['
    ListEnd = ']'
    FnStart = "{"
    FnEnd = "}"
    Comma = ','
    NewLine = '\n'
    BlockStart = '\t'
    BlockEnd = '\t\n'


class Commands(Enum):
    Print = 'print'
    # If = 'if'
    # Else = 'else'
    # For = 'for'
    # While = 'while'
    Local = 'local'
    Var = 'var'
    Return = 'return'
    Break = 'break'
    Continue = 'continue'
    Exit = 'exit'
    Debug = 'debug'
    Else = 'else'
    Import = 'import'
    Inherit = 'inherit'
    Label = 'label'
    Function = 'fn'
    Table = 'table'
    # Slice = 'slice'
    Trait = 'trait'
    Slot = 'slot'
    Formula = 'formula'
    Opt = 'opt'
    Setter = 'setter'

class OptionType(Enum):
    Function = ":"
    SetValue = "="
    Alias = ":="
    PlusEquals = '+='
    MinusEquals = '-='
    MultEquals = '*='
    DivEquals = '/='
    ModEquals = '%='
    AndEquals = "&="
    OrEquals = "|="
    NullEquals = '?='

class OperatorWord(Enum):
    In = 'in'
    And = 'and'
    Or = 'or'
    Is = 'is'
    Not = 'not'
    Of = 'of'
    If = 'if'
    Has = 'has'
    # Else = 'else'


class Singletons(Enum):
    none = 'none'
    true = 'true'
    false = 'false'
    inf = 'inf'


class KeyWords(Enum):
    # In = 'in'
    # And = 'and'
    # Or = 'or'
    # Is = 'is'
    # Not = 'not'
    # Of = 'of'
    If = 'if'
    # Else = 'else'  # I made else into a command because it's easier to parse that way
    For = 'for'
    While = 'while'
    Try = 'try'
    Except = 'except'


class MatchPatternType(Enum):
    Value = 'value'
    Class = 'class'
    SubClass = 'sub_class'


def token_mapper(item: str) -> TokenType:
    return TokenType._value2member_map_.get(item, TokenType.Unknown)
def command_mapper(item: str) -> Commands:
    return Commands._value2member_map_.get(item)
def singleton_mapper(item: str) -> Singletons:
    return Singletons._value2member_map_.get(item, None)
singletons = {'none': None, 'false': False, 'true': True, 'inf': math.inf}
def keyword_mapper(item: str) -> KeyWords:
    return KeyWords._value2member_map_.get(item, None)
def match_pattern_type_mapper(item: str) -> MatchPatternType:
    return MatchPatternType._value2member_map_.get(item, None)
# def type_mapper(item: str | type) -> BasicType:
#     if isinstance(item, str):
#         return BasicType._value2member_map_.get(item, None)


class Node:
    pos: tuple[int, int]
    type = TokenType.Unknown
    source_text: str


class Token(Node):
    def __init__(self, text: str, pos: tuple[int, int] = (-1, -1), type: TokenType = None):
        self.pos = pos[0], pos[1]
        self.type = type
        self.source_text = text

        if not type:
            # if re.match(r'["\'`]', text):
            #     self.type = TokenType.String
            if re.fullmatch(r'-?\d+(\.\d*)?d?', text):
                self.type = TokenType.Number
            elif re.match(op_char_patt, text) or text in OperatorWord:
                self.type = TokenType.Operator
            elif text in Commands:
                self.type = TokenType.Command
            elif text.lower() in Singletons:
                self.source_text = text.lower()
                self.type = TokenType.Singleton
            elif text in KeyWords:
                self.type = TokenType.Keyword
            elif re.fullmatch(r'\w+', text):
                self.type = TokenType.Name
            elif text.startswith('\t'):
                self.type = TokenType.BlockStart
            else:
                self.type = token_mapper(text)

    def __str__(self):
        return self.source_text

    def __repr__(self):
        return f"<{self.source_text}:{self.type.name}>"


class NonTerminal(Node):
    nodes: list[Node]
    def __init__(self, nodes: list[Node]):
        self.nodes = nodes
        for n in nodes:
            if n.pos != (0, 0) and n.pos != (-1, -1):
                self.pos = n.pos
                break
        else:
            self.pos = (-1, -1)

    @property
    def source_text(self):
        return ' '.join(n.source_text for n in self.nodes)


class StringNode(NonTerminal):
    def __repr__(self):
        return ''.join(map(repr, self.nodes))

class Statement(NonTerminal):
    def __repr__(self):
        return ' '.join(repr(node) for node in self.nodes)


class Block(NonTerminal):
    """
    a container for executables (statements, e
    representing the lines of code to put into a function
    """
    statements: list[Statement]

    def __init__(self, nodes: list[Statement], indent=0):
        super().__init__(nodes)
        self.statements = nodes

    def __repr__(self):
        if not self.statements:
            return '[empty]'
        elif len(self.statements) == 1:
            return f"[{repr(self.statements[0])}"
        else:
            return f"[{len(self.statements)} statements]"


class ListType(Enum):
    List = '[list]'
    Tuple = '(tuple)'
    Function = "{function}"
    Args = '[args]'
    Params = '[params]'

class ListNode(NonTerminal):
    """
    [list], (tuple), {function}, or argument-tuple
    """
    items: list[Statement]
    list_type: ListType
    def __init__(self, items: list[Statement], list_type: ListType):
        self.items = items
        self.list_type = list_type
        super().__init__(items)

    def __repr__(self):
        return repr(self.nodes)  # f"[{', '.join(repr(node) for node in self.nodes)}]"


# class FunctionLiteral(NonTerminal):
#     statements: list[Statement]
#     def __init__(self, items: list[Statement]):
#         super().__init__(items)
#         self.statements = items
#
#     def __repr__(self):
#         return f"{{{' '.join(map(repr, self.statements))}}}"


if __name__ == "__main__":
    print(TokenType._value2member_map_.get('?', 'None Found'))
    print(repr(Token(',', (0, 0))))



