import math
from Syntax import BasicType, Block, Statement
from Env import *


val_types = None | bool | int | float | str | Function | Pattern | BasicType | list[Value]

class Value:
    value: val_types
    type: BasicType
    def __init__(self, value: val_types, basic_type: BasicType = None): ...
    def set_value(self, new_value: Value | val_types) -> Value: ...
    def set_type(self, basic_type: BasicType = None) -> BasicType: ...
    def is_null(self) -> bool: ...
    def not_null(self) -> bool: ...
    def clone(self) -> Value: ...

class Parameter:
    inverse: bool = False
    pattern: Pattern
    name: str | None
    quantifier: str   #  "+" | "*" | "?" | ""
    count: tuple[int, int|float]
    optional: bool
    multi: bool
    def __init__(self,
                 pattern: Pattern | str,
                 name: str = None,
                 quantifier: str = "",
                 inverse = False): ...
    def specificity(self) -> int: ...
    def match_score(self, value: Value) -> int | float: ...

# score is out 7560, this number is 3*2520 (the smallest int divisible by all integers up to 10)
def match_score(val: Value, param: Parameter) -> int: ...

Guard = Function | Statement

class Pattern:
    """
    A Pattern is like a regex for types and parameters; it can match one very specific type, or even
    one specific value, or it can match a type on certain conditions (e.g. int>0), or union of types
    """
    name: str | None
    guard: Guard
    def match_score(self, arg: Value) -> int | float: ...
    def __init__(self, name: str = None, guard: Guard = None): ...
    def zip(self, args: list[Value]) -> dict[Parameter, Value]: ...
    def min_len(self) -> int: ...
    def max_len(self) -> int | float: ...
    def __len__(self): ...
    def __getitem__(self, item): ...
    def __eq__(self, other): ...
    def __hash__(self): ...


class ValuePattern(Pattern):
    value: Value
    def __init__(self, value: Value, name: str = None): ...
    def __eq__(self, other): ...
    def __hash__(self): ...

class Type(Pattern):
    basic_type: BasicType
    def __init__(self, basic_type: BasicType, name: str = None, guard: Guard = None): ...
    def __eq__(self, other): ...
    def __hash__(self): ...

class Prototype(Pattern):
    prototype: Function
    def __init__(self, value: Value, name: str = None, guard: Guard = None): ...
    def __eq__(self, other): ...
    def __hash__(self): ...

class Union(Pattern):
    patterns: frozenset[Pattern]
    def __init__(self, *patterns: Pattern, name: str = None, guard: Guard = None): ...
    def __eq__(self, other): ...
    def __hash__(self): ...

class ListPatt(Pattern):
    parameters: tuple[Parameter, ...]
    def __init__(self, *parameters: Parameter): ...
    def zip(self, args: list[Value] = None) -> dict[Pattern, Value]: ...
    def min_len(self) -> int | float:
        count = 0
        for param in self.parameters:
            count += int(param.quantifier in ("", "+"))
        return count
    def max_len(self) -> int | float:
        count = 0
        for param in self.parameters:
            if param.quantifier in ("+", "*"):
                return math.inf
            count += int(param.quantifier != "?")
        return count
    def __len__(self):
        return len(self.parameters)
    def __getitem__(self, item):
        return self.parameters[item]
    def match_score(self, arg: Value) -> int | float: ...
    def __eq__(self, other): ...
    def __hash__(self): ...

def make_patt(val: Value) -> Pattern: ...

class Element:
    value: Value | None
    type: BasicType | None
    prototype: Function | None
    guard: Statement | None
    def __init__(self, value: Value | None,
                 type: BasicType | None,
                 prototype: Function | None,
                 guard: Statement | None): ...
    def __hash__(self): ...

opt_type = Value | Block | callable | None

class Option:
    pattern: ListPatt
    resolution: opt_type
    value: Value
    block: Block
    fn: callable
    def __init__(self, pattern: ListPatt | Pattern | Parameter | str, resolution: opt_type = None): ...
    def is_null(self) -> bool: ...
    def not_null(self) -> bool: ...
    def assign(self, val_or_block: Value | Block): ...
    def resolve(self, args: list[Value] = None, proto: Function = None, env: Function = Context.env) -> Value: ...

class Function:
    prototype: Function # class-like inheritance
    args: list[Value]
    options: list[Option]
    named_options: dict[str, Option]
    block: Block
    env: Function
    exec: any
    return_value: Value
    is_null: bool
    init: any
    def __init__(self, opt_pattern: Pattern | Parameter | str = None,
                     opt_value: opt_type = None,
                     options: dict[Pattern | Parameter | str, opt_type] = None,
                     # block: Block = None,
                     prototype: Function = None,
                     env: Function = Context.env,
                     # value: Value = None,
                     # is_null=False
                 ): ...

    def add_option(self, pattern: Pattern | Parameter | str, value: opt_type = None) -> Option: ...
    def assign_option(self, pattern: Pattern, value: opt_type = None) -> Function: ...
    def index_of(self, key: list[Value]) -> int | None: ...
    def select(self, key: Pattern | list[Value] | str, walk_prototype_chain=True, ascend_env=False) -> Option: ...
    def call(self, key: list[Value], copy_option=True, ascend=False) -> Value: ...
    def deref(self, name: str, ascend_env=True) -> Value: ...
    def execute(self) -> Value: ...
    def init(self, pattern: Pattern, key: list[Value], parent: Function = None, copy=True) -> Function: ...
    def instanceof(self, prototype: Function) -> bool: ...
    def clone(self) -> Function: ...

class Operator:
    text: str
    prefix: int
    postfix: int
    binop: int
    ternary: str
    associativity: str
    fn: Function
    static: bool | callable
    def __init__(self, text, fn:Function=None, prefix:int=None, postfix:int=None, binop:int=None,
                 ternary:str=None, associativity='left', static=False): ...
    def prepare_args(self, lhs, mid, rhs) -> list[Value]: ...
