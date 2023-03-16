from Syntax import Node, Token, TokenType, List, Statement, Block
from Env import Context, NoMatchingOptionError, OperatorError
from DataStructures import Value, Function, FuncBlock
from BuiltIns import Op, BuiltIns
from Expressions import Expression, read_option, eval_node

def static_fn(lhs: list[Node], mid: list[Node], rhs: list[Node]) -> Value:
    return Value("this is just a function signature")


def assign_val(lhs: list[Node], mid: list[Node], rhs: list[Node]) -> Value:
    value = Expression(rhs).evaluate().clone()
    option = read_option(lhs)
    option.value = value
    return value

def assign_alias(lhs: list[Node], mid: list[Node], rhs: list[Node]) -> Value:
    value = Expression(rhs).evaluate()
    option = read_option(lhs)
    option.value = value
    return value

def assign_fn(lhs: list[Node], mid: list[Node], rhs: list[Node]) -> Value:
    blk_nd = rhs[0]
    if len(rhs) == 1 and isinstance(blk_nd, Block):
        block: Block = blk_nd
    else:
        return_statement = Statement([Token('return')] + rhs)  # noqa
        block = Block([return_statement])
    option = read_option(lhs)
    option.block = FuncBlock(block)
    return Value(None)


Op['='].static = assign_val
Op[':='].static = assign_alias
Op[':'].static = assign_fn

# Op['+='].static = lambda a, _, b: assign_val(Op['+'].fn.call())
# def assign_with_operator()
#     val = op.assign_op.fn.call([Expression(self.lhs).evaluate(), Expression(self.rhs).evaluate()])


def or_fn(lhs: list[Node], mid: list[Node], rhs: list[Node]) -> Value:
    condition = Expression(lhs).evaluate()
    return condition if BuiltIns['boolean'].call([condition]).value else Expression(rhs).evaluate()
Op['or'].static = or_fn

def and_fn(lhs: list[Node], mid: list[Node], rhs: list[Node]) -> Value:
    condition = Expression(lhs).evaluate()
    return Expression(rhs).evaluate() if BuiltIns['boolean'].call([condition]).value else condition
Op['and'].static = and_fn

def if_fn(lhs: list[Node], mid: list[Node], rhs: list[Node]) -> Value:
    condition = Expression(mid).evaluate()
    if BuiltIns['boolean'].call([condition]).value:
        return Expression(lhs).evaluate()
    else:
        return Expression(rhs).evaluate()
Op['if'].static = if_fn

def option_exists(lhs: list[Node], mid: list[Node], rhs: list[Node]) -> Value:
    try:
        last = lhs[-1]
        if isinstance(last, List):
            key = eval_node(last)
        elif last.type in (TokenType.Name, TokenType.PatternName):
            key = [Value(last.source_text)]
        else:
            raise OperatorError(f"Line {Context.line}: right-most arg of ? operator must be a name or arg-list.")
        if len(lhs) == 1:
            fn = Context.env
        else:
            # assert lhs[-1] is '.' or '.['
            fn = Expression(lhs[:-2]).evaluate().value
            assert isinstance(fn, Function)
        fn.select(key)
        return Value(True)
    except NoMatchingOptionError:
        return Value(False)
Op['?'].static = option_exists

def nullish_or(lhs: list[Node], mid: list[Node], rhs: list[Node]) -> Value:
    try:
        return Expression(lhs).evaluate()
    except NoMatchingOptionError:
        return Expression(rhs).evaluate()
Op['??'].static = nullish_or

def dot_op(lhs: list[Node], mid: list[Node], rhs: list[Node]) -> Value:
    assert len(mid) == 1
    fn = Expression(lhs).evaluate()
    name = mid[0].source_text
    if isinstance(fn, Function):
        try:
            option = fn.deref(name)
        except NoMatchingOptionError:
            option = Context.env.deref()


