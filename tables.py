print(f'Import {__name__}.py')
import math
from fractions import Fraction
from Env import *
from typing import TypeVar, Generic, overload

print(f"loading module: {__name__} ...")

PyFunction = type(lambda: None)

def memoize(fn):
    memory = {}
    if type(fn) == PyFunction:
        def inner(*args):
            try:
                return memory[args]
            except KeyError:
                result = fn(*args)
                memory[args] = result
                return result
    elif type(fn) == type(list.append):
        def inner(self, *args):
            try:
                return memory[self, args]
            except KeyError:
                result = fn(self, *args)
                memory[self, args] = result
                return result
    else:
        raise TypeError
    return inner

def memoize_property(fn):
    memory = {}

    def inner(self):
        try:
            return memory[self]
        except KeyError:
            result = fn(self)
            memory[self] = result
            return result
    return property(inner)

def dependencies(*slots: str):
    def memoize(fn):
        memory = {}

        def wrapper(self: Record):
            state = self, tuple(self.get(slot) for slot in slots)
            if state in memory:
                return memory[state]
            result = fn(self)
            memory[state] = result
            return result
        return wrapper
    return memoize


class frozendict(dict):
    hash: int
    def __hash__(self):
        try:
            return self.hash
        except AttributeError:
            try:
                self.hash = hash(frozenset(self.items()))
            except TypeError:
                self.hash = hash(frozenset(self))
            return self.hash

    def __setitem__(self, *args, **kwargs):
        raise RuntimeError(f'Cannot change values of immutable {repr(self)}.')

    __delitem__ = pop = popitem = clear = update = setdefault = __setitem__

    def __add__(self, other: tuple | dict):
        new = frozendict(self)
        dict.update(new, other)
        return new

    def __sub__(self, other):
        new = frozendict(self)
        dict.__delitem__(new, other)
        return new

    def __str__(self):
        return super().__str__()

    def __repr__(self):
        return f"frozendict({super().__repr__()})"


class OptionCatalog:
    op_list: list
    op_map: dict
    # noinspection PyDefaultArgument
    def __init__(self, options={}, *traits):
        self.op_list = []
        self.op_map = {}
        if options:
            for patt, res in options.items():
                self.assign_option(Option(patt, res))
        for trait in traits:
            for option in trait.op_list:
                self.assign_option(option)
            self.op_map.update(trait.op_map)

    def assign_option(self, pattern, resolution=None, *, no_clobber=False):
        match pattern, resolution:
            case Option(pattern=pattern, resolution=resolution) as option, None:
                key = pattern.to_args()
            case _:
                if resolution is None:
                    raise AssertionError("Why are you trying to add a null option?")
                option = Option(pattern, resolution)
                if isinstance(pattern, Args):
                    key = pattern
                else:
                    key = option.pattern.to_args()
                pattern = option.pattern

        if key is not None:
            if no_clobber and key in self.op_map:
                # don't overwrite existing key
                return self.op_map[key]
            else:
                self.op_map[key] = option
                return option

        if Context.settings['sort_options']:
            for i, opt in enumerate(self.op_list):
                if option.pattern == opt.pattern:
                    if not no_clobber:
                        self.op_list[i] = option
                    break
                elif option.pattern <= opt.pattern:
                    self.op_list.insert(i, option)
                    break
            else:
                self.op_list.append(option)
        elif opt := self.select_by_pattern(pattern):
            opt.resolution = resolution
        else:
            self.op_list.append(option)

        return option

    def remove_option(self, pattern):
        opt = self.select_by_pattern(pattern)
        if opt is None:
            raise NoMatchingOptionError(f'cannot find option "{pattern}" to remove')
        opt.nullify()

    def select_and_bind(self, key):
        if isinstance(key, tuple):
            key = Args(*key)  # I don't think this should happen anymore
        try:
            if key in self.op_map:
                return self.op_map[key], {}
        except TypeError as e:
            if not (e.args and e.args[0].startswith('unhashable type')):
                raise e
        if Context.debug and self is BuiltIns['call']:
            Context.debug = 0  # pause debugger
        option = bindings = None
        high_score = 0
        for opt in self.op_list:
            bindings = opt.pattern.match(key)
            score, saves = bindings is not None, bindings
            if score == 1:
                if Context.debug is 0:
                    Context.debug = True  # unpause debug
                return opt, saves
            if score > high_score:
                high_score = score
                option, bindings = opt, saves
        if Context.debug is 0:
            Context.debug = True  # unpause debug
        return option, bindings

    def select_by_pattern(self, patt, default=None):
        # return [*[opt for opt in self.op_list if opt.pattern == patt], None][0]
        for opt in self.op_list:
            if opt.pattern == patt:
                return opt
        return default


class Record:
    name = None
    # table: Table
    # data: dict[int, Record]
    # key: Record
    truthy = True
    def __init__(self, table, *data_tuple, **data_dict):
        self.table = table
        i = len(data_tuple)
        if i > len(self.table.defaults):
            raise RuntimeErr(f"Line {Context.line}: too many values provided for creating new instance of {self.table};"
                             f" Expected a maximum of {len(self.table.defaults)} values but got {i}: {data_tuple}")
        defaults = (val.call(self) if val else BuiltIns['blank'] for val in self.table.defaults[i:])
        self.data = [*data_tuple, *defaults]
        for k, v in data_dict.items():
            self.set(k, v)
            
        table.add_record(self)

    # @property
    # def mro(self):
    #     yield from self.table.traits

    # key property
    # def get_key(self):
    #     match self.table:
    #         case ListTable():
    #             return py_value(self.index)
    #         case DictTable(key_field=fid):
    #             return self.get_by_index(fid)
    #         case SetTable():
    #             return self
    #     raise RuntimeErr
    # def set_key(self, new_key):
    #     match self.table:
    #         case ListTable():
    #             raise RuntimeErr(f"Cannot set automatically assigned key (index)")
    #         case DictTable(key_field=fid):
    #             self.set_by_index(fid, new_key)
    #         case SetTable():
    #             raise RuntimeErr(f"Cannot set key of SetTable.")
    #         case _:
    #             raise RuntimeErr
    # key = property(get_key, set_key)

    def get(self, name: str, *default, search_table_frame_too=False):
        if name in self.table.getters:
            match self.table.getters[name]:
                case int() as idx:
                    return self.data[idx]
                case Function() as fn:
                    return fn.call(self)
        if search_table_frame_too and self.table.frame:
            val = self.table.frame[name]
            if val is not None:
                return val
        if not default:
            raise SlotErr(f"Line {Context.line}: no field found with name '{name}'.")
        return default[0]

    def set(self, name: str, value):
        match self.table.setters.get(name):
            case int() as idx:
                # TODO: check for type agreement ...
                #  or skip it in this context, rely on the type-checking of foo.bar = "value"
                self.data[idx] = value
                return value
            case Function() as fn:
                return fn.call(self, value)
            case None:
                raise SlotErr(f"Line {Context.line}: no field found with name '{name}'.")

    # @overload
    # def call(self, *args, flags: set = None, **kwargs): ...
    # @overload
    # def call(self, args): ...
    # @overload
    # def call(self, *args: Record, flags: set[Record] = None, **kwargs: Record) -> Record: ...
    # @overload
    # def call(self, args: Args) -> Record: ...
    """ A Record can be called on multiple values (like calling a regular function) with flags and kwargs, in which 
    case it will build an Args object.  Or, it can be called on an already built Args object. """
    def call(self, *args, flags=None, caller=None, **kwargs):
        match args:
            case [Args()] if flags is None and not kwargs:
                args = args[0]
            case [Args() as args]:
                print("WARNING: this might be dangerous, I'm not sure yet.")
                args += Args(flags=flags, **kwargs)
            case _:
                args = Args(*args, flags=flags, **kwargs)

        option, bindings = self.select(args)
        if option:
            return option.resolve(args, caller, bindings, self)
        raise NoMatchingOptionError(f'Line {Context.line}: {args} not found in "{self.name or self}"')

        # if not isinstance(args, Args):
        #     args = Args(args)
        # option, bindings = self.select_by_args(args)
        # if option:
        #     return option.resolve(args, self, bindings)
        # raise NoMatchingOptionError(f"Line {Context.line}: key {args} not found in {self.name or self}")

        # option, bindings = self.select(*key)
        # if option:
        #     return option.resolve(key, self, bindings)
        # raise NoMatchingOptionError(f"Line {Context.line}: key {key} not found in {self.name or self}")

    # I should not make Records python callable... that's just confusing
    # def __call__(self, args):
    #     option, bindings = self.select(args)
    #     if option:
    #         return option.resolve(args, self, bindings)
    #     raise NoMatchingOptionError(f"Line {Context.line}: {args} not found in {self.name or self}")

    def select(self, args):
        return self.table.catalog.select_and_bind(args)
    #     for t in self.mro:
    #         option, bindings = t.select_and_bind(args)
    #         if option:
    #             return option, bindings
    #     return None, None

    def hashable(self):
        try:
            return isinstance(hash(self), int)
        except TypeError:
            return False

    # @property
    # def truthy(self):
    #     return True

    def to_string(self):
        if self.name:
            return py_value(self.name)
        # if self.instanceof(BuiltIns['BasicType']):
        #     return Value(self.name)
        return py_value(str(self))

    # def __eq__(self, other):
    #     if not isinstance(other, Record):
    #         return False
    #     if isinstance(self.table, VirtTable) or isinstance(other.table, VirtTable):
    #         return id(self) == id(other)
    #     return (self.table, self.key) == (other.table, other.key)
    #
    # def __hash__(self):
    #     return id(self)

    def __repr__(self):
        return f"Record<{self.table}>({self.data})"

    # def __eq__(self, other):
    #     if getattr(self, "value", object()) == getattr(other, "value", object()) and self.value is not NotImplemented:
    #         return True
    #     if self is other:
    #         return True
    #     if not isinstance(other, Function):
    #         return False
    #     if getattr(self, "value", object()) == getattr(other, "value", object()) and self.value is not NotImplemented:
    #         return True
    #     if self.type is not other.type:
    #         return False
    #     if self.env != other.env or self.name != other.name:
    #         return False
    #     # for opt in self.options:
    #     #     if opt.resolution != getattr(other.select_by_pattern(opt.pattern), 'resolution', None):
    #     #         return False
    #     return True


T = TypeVar('T', None, bool, int, Fraction, float, str, tuple, frozenset, set, list)
A = TypeVar('A')
class PyValue(Record, Generic[T]):
    def __init__(self, table, value: T):
        self.value = value
        # self.slices = list(slices)
        super().__init__(table)

    def to_string(self):
        for singleton in ('true', 'false', 'blank'):
            if self is BuiltIns[singleton]:
                return py_value(singleton)
        if BuiltIns['num'] in self.table.traits:
            return py_value(write_number(self.value, Context.settings['base']))
        # if self.instanceof(BuiltIns['list']):
        #     return py_value(f"[{', '.join(v.to_string().value for v in self.value)}]")
        if BuiltIns['seq'] in self.table.traits:
            gen = (f'"{el.value}"' if isinstance(getattr(el, 'value', None), str) else el.to_string().value
                   for el in self.value)
            items = ', '.join(gen)
            match self.value:
                case list():
                    return py_value(f'[{items}]')
                case tuple():
                    return py_value(f'({items}{"," * (len(self.value) == 1)})')
                case set() | frozenset():
                    return py_value('{' + items + '}')

        return py_value(str(self.value))

    def __index__(self) -> int | None:
        if not isinstance(self.value, int | bool):
            raise TypeErr(f"Line {Context.line}: Value used as seq index must have trait int. "
                          f"{self} is a record of {self.table}")
        if not self.value:
            # return None  -->  TypeError: __index__ returned non-int (type NoneType)
            raise ValueError(f"Line {Context.line}: Pili indices start at ±1.  0 is not a valid index.")
        return self.value - (self.value > 0)

    def assign_option(self, key, val: Record):
        key: Args
        assert self.table == BuiltIns['List']
        index: PyValue[int] = key[0]  # noqa
        if index.value == len(self.value) + 1:
            self.value.append(val)
        else:
            self.value[index] = val
        return val

    @property
    def truthy(self):
        return bool(self.value)

    def __hash__(self):
        try:
            return hash(self.value)
        except TypeError:
            return id(self)

    def __eq__(self, other):
        return isinstance(other, PyValue) and self.value == other.value or self.value == other

    def __iter__(self):
        match self.value:
            case tuple() | list() | set() | frozenset() as iterable:
                return iter(iterable)
            case str() as string:
                return (PyValue(BuiltIns['String'], c) for c in string)
        raise TypeErr(f"Line {Context.line}: {self.table} {self} is not iterable.")

    def __repr__(self):
        match self.value:
            case frozenset() as f:
                return repr(set(f))
            case Fraction(numerator=n, denominator=d):
                return f"{n}/{d}"
            case None:
                return 'blank'
            case v:
                return repr(v)
        # return f"Record({self.value})"


class2table = dict(bool='Bool', int="Integer", Fraction='Fraction', float="Float", str='String', tuple="Tuple",
                   list='List', set='Set', frozenset='FrozenSet', dict='Dictionary')


def py_value(value: T | object):
    match value:
        case None:
            return BuiltIns['blank']
        case True:
            return BuiltIns['true']
        case False:
            return BuiltIns['false']
        case Fraction(denominator=1, numerator=value) | (int() as value):
            return PyValue(BuiltIns['Integer'], value)
        case Fraction() | float() | str():
            table = BuiltIns[class2table[type(value).__name__]]
        # case list():
        #     return List(list(map(py_value, value)))
        case tuple() | list() | set() | frozenset():
            table = BuiltIns[class2table[type(value).__name__]]
            t = type(value)
            value = t(map(py_value, value))
        case dict() as d:
            table = BuiltIns['Function']
            value = Function({py_value(k): py_value(v) for k, v in d.items()})
        case Record():
            return value
        # case Parameter():
        #     return ParamSet(value)
        # case Matcher() as t:
        #     return ParamSet(Parameter(t))
        case _:
            return PyObj(value)
    return PyValue(table, value)

piliize = py_value

class PyObj(Record, Generic[A]):
    def __init__(self, obj):
        self.obj = obj
        super().__init__(BuiltIns['PythonObject'])

    def to_string(self):
        return py_value(repr(self.obj))


class Range(Record):
    def __init__(self, *args: PyValue):
        step = py_value(1)
        match args:
            case []:
                start = py_value(1)
                end = py_value(-1)
            case [end]:
                start = step = py_value(1)
            case [start, end]:
                step = py_value(1)
            case [start, end, step]:
                # start, stop, step = (a.value for a in args)
                if step.value == 0:
                    raise RuntimeErr(f"Line {Context.line}: Third argument in range (step) cannot be 0.")
            case _:
                raise RuntimeErr(f"Line {Context.line}: Too many arguments for range")
        if start == BuiltIns['blank']:
            start = py_value(0)
        if end == BuiltIns['blank']:
            end = py_value(0)
        super().__init__(BuiltIns['Range'], start, end, step)

    def __iter__(self):
        start, end, step = tuple(f.value for f in self.data)
        if start is None:
            return
        i = start
        while i <= end if step > 0 else i >= end:
            yield py_value(i)
            i += step

    @property
    def slice(self) -> slice | None:
        start, end, step = (f.value for f in self.data)
        if start > 0:
            start -= 1
        if step < 0:
            if end < 0:
                end -= 1
            elif end in (0, 1):
                end = 0
            else:
                end -= 2
        else:
            if end < 0:
                end += 1

        """
        1..3      => [0:3]
        1..-2     => [0:-1]
        -1..-3:-1 => [-1:-4:-1]
        4..2:-1   => [3:0:-1]
        """
        return slice(start or None, end or None, step)

class Function(Record, OptionCatalog):
    frame = None
    def __init__(self, options=None, *fields, name=None,
                 table_name='Function', traits=(), frame=None, uninitialized=False):
        if name:
            self.name = name
        if uninitialized:
            self.uninitialized = True
        # self.slot_dict = {}
        # self.formula_dict = {}
        # self.setter_dict = {}
        if frame:
            self.frame = frame
        for f in fields:
            self.update_field(f)
        # self.trait = Trait(options, *fields)
        OptionCatalog.__init__(self, options or {}, *traits)
        super().__init__(BuiltIns[table_name])

    # @property
    # def mro(self):
    #     if self.trait:
    #         yield self.trait
    #     yield from super().mro
    #     # return self.trait, *super().mro

    def update_field(self, field):
        raise DeprecationWarning("This is being replaced by simple get and set for locals/vars within the functions frame.")
        name = field.name
        match field:
            case Slot(default=default):
                self.slot_dict[name] = default.call(self)
            case Formula(formula=fn):
                self.formula_dict[name] = fn
            case Setter(fn=fn):
                self.setter_dict[name] = fn

    def get(self, name: str, *default, search_table_frame_too=False):
        if self.frame:
            val = self.frame[name]
            if val:
                return val
        # if name in self.slot_dict:
        #     return self.slot_dict[name]
        # if name in self.formula_dict:
        #     return self.formula_dict[name].call(self)
        return super().get(name, *default, search_table_frame_too=search_table_frame_too)

    def set(self, name: str, value: Record):
        if self.frame:
            if name in self.frame.vars:
                self.frame.vars[name] = value
            else:
                self.frame.locals[name] = value
            return value
        # if name in self.slot_dict:
        #     self.slot_dict[name] = value
        #     raise NotImplementedError("How can I set the value of the local var in the closure associated with this function?")
        #     return value
        # if name in self.setter_dict:
        #     return self.setter_dict[name].call(self, value)
        return super().set(name, value)

    def select(self, args):
        option, bindings = self.select_and_bind(args)
        if option is not None:
            return option, bindings
        return self.table.catalog.select_and_bind(args)

    def __repr__(self):
        if self is Context.root:
            return 'root'
        return f"Function({self.name or ''})"


class Trait(Function):
    # trait = None
    # noinspection PyDefaultArgument
    def __init__(self, options={}, *fields, name=None, fn_options={}, fn_fields=[], uninitialized=False):
        self.options = [Option(patt, res) for (patt, res) in options.items()]
        self.fields = list(fields)
        super().__init__(fn_options, *fn_fields, name=name, table_name='Trait', uninitialized=uninitialized)

    # def add_option(self, pattern, resolution=None):
    #     option = Option(pattern, resolution)
    #
    #     # try to hash option
    #     key: list[Record] = []
    #     for parameter in option.pattern.parameters:
    #         t = parameter.matcher
    #         if isinstance(t, ValueMatcher) and t.guard is None and not t.invert and t.value.hashable():
    #             key.append(t.value)
    #         else:
    #             if Context.settings['sort_options']:
    #                 for i, opt in enumerate(self.options):
    #                     if option.pattern <= opt.pattern:
    #                         self.options.insert(i, option)
    #                         break
    #                     elif option.pattern == opt.pattern:
    #                         self.options[i] = option
    #                         break
    #                 else:
    #                     self.options.append(option)
    #             else:
    #                 self.options.append(option)
    #             break
    #     else:
    #         self.hashed_options[tuple(key)] = option
    #
    #     return option
    #
    # def remove_option(self, pattern):
    #     opt = self.select_by_pattern(pattern)
    #     if opt is None:
    #         raise NoMatchingOptionError(f'cannot find option "{pattern}" to remove')
    #     opt.nullify()
    #
    # def assign_option(self, pattern, resolution=None):
    #     opt = self.select_by_pattern(pattern)
    #     if opt is None:
    #         return self.add_option(pattern, resolution)
    #     else:
    #         opt.resolution = resolution
    #     return opt
    #
    # def select_and_bind(self, key):
    #     match key:
    #         case tuple() if key in self.hashed_options:
    #             return self.hashed_options[key], {}
    #         case Args(positional_arguments=pos) if not (key.named_arguments or key.flags):
    #             if pos in self.hashed_options:
    #                 return self.hashed_options[pos], {}
    #
    #     option = bindings = None
    #     high_score = 0
    #     for opt in self.options:
    #         score, saves = opt.pattern.match_zip(key)
    #         if score == 1:
    #             return opt, saves
    #         if score > high_score:
    #             high_score = score
    #             option, bindings = opt, saves
    #     return option, bindings
    #
    # def select_by_pattern(self, patt, default=None):
    #     # return [*[opt for opt in self.options if opt.pattern == patt], None][0]
    #     for opt in self.options:
    #         if opt.pattern == patt:
    #             return opt
    #     return default

    def upsert_field(self, field):
        for i, f in self.fields:
            if f.name == field.name:
                self.fields[i] = field
                return
        self.fields.append(field)
        # if field.name in self.field_ids:
        #     fid = self.field_ids[field.name]
        #     self.fields[fid] = field
        # else:
        #     self.field_ids[field.name] = len(self.fields)
        #     self.fields.append(field)

    # def add_own_option(self, pattern, resolution=None):
    #     if self.trait is None:
    #         self.trait = Trait()
    #     return self.add_option(pattern, resolution)

    def __repr__(self):
        return f"Trait({self.name or self.fields})"
        # match self.options, self.hashed_options:
        #     case _ if self.name:
        #         return f"Trait({self.name})"
        #     case [], {}:
        #         return "Trait()"
        #     case [opt], {}:
        #         return f"Trait({opt})"
        #     case [], dict() as d if len(d) == 1:
        #         return f"Trait({tuple(d.values())[0]})"
        #     case list() as opts, dict() as hopts:
        #         return f"Trait({len(opts) + len(hopts)})"
        # return f"OptionMap({self.table})"

def flat_gen(*args):
    for arg in args:
        if isinstance(arg, str):
            yield arg
        else:
            try:
                for item in flat_gen(*arg):
                    yield item
            except TypeError:
                yield arg

class Table(Function):
    name = None
    # records: list[Record] | dict[Record, Record] | set[Record] | None
    # getters = dict[str, tuple[int, Field]]
    # setters = dict[str, tuple[int, Field]]
    # fields = list[Field]
    # noinspection PyDefaultArgument
    def __init__(self, *traits: Trait, name=None, fn_options={}, fn_fields=[], uninitialized=False):
        self.traits = (Trait(name=name), *traits)
        self.getters = {}
        self.setters = {}
        self.defaults = ()
        # for field in fields:
        #     self.fields.append(field)
        super().__init__(fn_options, *fn_fields, name=name, table_name='Table', traits=traits)
        if uninitialized:
            self.uninitialized = True
        else:
            self.integrate_traits()
        match self:
            case VirtTable():
                pass
            case ListTable():
                self.records = []
            case DictTable():
                self.records = {}
            case SetTable():
                self.records = set()
            case _:
                raise TypeError("Oops, don't use the Table class — use a derived class instead.")

    @property
    def trait(self):
        return self.traits[0]

    def integrate_traits(self):
        defaults: dict[str, Function | None] = {}
        types: dict[str, Pattern] = {}

        for trait in self.traits:
            # if trait.frame:
            #     for name, value in trait.frame.locals.items():
            #         if name not in self.frame:
            #             self.frame[name] = value
            # ^^ I thought about transferring all names from all traits into the current table, but that's a bit heavy
            for trait_field in trait.fields:
                name = trait_field.name
                pattern: Pattern = getattr(trait_field, 'type', None)
                if pattern:
                    # if isinstance(pattern, Parameter):
                    #     assert pattern.binding == name
                    if name in types and not types[name].issubset(pattern):
                        raise SlotErr(f"Line {Context.line}: Could not integrate table {self.name}; "
                                      f"type of Field \"{name}\" ({types[name]}) "
                                      f"doesn't match type of {trait_field.__class__.__name__} \"{name}\" "
                                      f"of trait {trait.name}.")
                    elif isinstance(trait_field, Setter):
                        types[name] = AnyMatcher()
                    else:
                        types[name] = pattern

                match trait_field:
                    case Slot(default=default):
                        # if slot: allow adding of default
                        # if formula: skip (formula should overwrite slot)
                        # if setter: skip (setter overwrites slot, hopefully a formula will also be defined)
                        if name in defaults:
                            # this means a slot was already defined.  Add a default if none exists
                            if defaults[name] is None:
                                defaults[name] = default
                        elif name not in self.getters and name not in self.setters:
                            # this means no slot, formula, or setter was defined.  So add a slot.
                            self.getters[name] = self.setters[name] = len(defaults)
                            defaults[name] = default

                    case Formula(formula=fn):
                        if name not in self.getters:
                            self.getters[name] = fn
                    case Setter(fn=fn):
                        if name not in self.setters:
                            self.setters[name] = fn
                        types[name] = AnyMatcher()

        self.defaults = tuple(defaults[n] for n in defaults)
        self.types = types
        patt = ParamSet(*(Parameter(types[name],
                                    name,
                                    "?" * (defaults[name] is not None))
                          for name in defaults))

        def make_option(table: Table):
            return Native(lambda args: BuiltIns['new'].call(Args(table) + args))
        self.assign_option(patt,
                           make_option(self),
                           no_clobber=True)

        self.catalog = OptionCatalog({}, *self.traits)

    # def get_field(self, name: str):
    #     _, field = self.getters.get(name,
    #                                 self.setters.get(name, (0, None)))
    #     return field

    def __getitem__(self, item):
        raise NotImplementedError

    def __setitem__(self, key, value):
        self.records[key] = value

    def __contains__(self, item):
        return item.table == self

    def truthy(self):
        return bool(self.records)

    def add_record(self, record: Record):
        match self:
            case VirtTable():
                pass
            case ListTable():
                record.index = len(self.records)
                self.records.append(record)
            case DictTable():
                self.records[record.key] = record
            case SetTable():
                self.records.add(record)

    def __repr__(self):
        if self.name:
            return self.name
        return f"Table({self.traits})"


class ListTable(Table):
    records: list[Record]
    # def __init__(self, *fields, name=None):
    #     super().__init__(*fields, name=name)
    #     self.records = []

    def __getitem__(self, key: PyValue[int]):
        try:
            return self.records[key.__index__()]
        except (TypeError, AttributeError):
            raise RuntimeErr(f"Index must be integer in range for ListTable.")
        except IndexError:
            return None


class MetaTable(ListTable):
    def __init__(self):
        self.name = 'Table'
        self.records = [self]
        self.table = self
        self.data = []
        self.index = 0
        self.traits = ()
        self.getters = {}
        self.setters = {}
        self.defaults = ()
        self.slot_dict = {}
        self.formula_dict = {}
        self.setter_dict = {}
        self.op_list = []
        self.op_map = {}
        self.catalog = OptionCatalog()


class BootstrapTable(ListTable):
    def __init__(self, name):
        self.name = name
        self.records = []
        self.traits = ()
        self.getters = {}
        self.setters = {}
        self.defaults = ()
        self.slot_dict = {}
        self.formula_dict = {}
        self.setter_dict = {}
        self.op_list = []
        self.op_map = {}
        self.catalog = OptionCatalog()
        Record.__init__(self, BuiltIns['Table'])


class DictTable(Table):
    records: dict[Record, Record]
    key_field: int
    def __init__(self, key_field: int = 0, *fields, name=None):
        self.key_field = key_field
        super().__init__(*fields, name=name)
        self.records = {}
    def __getitem__(self, key: Record):
        return self.records.get(key)

class SetTable(Table):
    records: set[Record]
    # def __init__(self, *fields, name=None):
    #     super().__init__(*fields, name=name)
    #     self.records = set([])
    def __getitem__(self, key: Record):
        return key

class VirtTable(SetTable):
    records = None
    # def __init__(self, *fields, name=None):
    #     self.records = None
    #     Table.__init__(self, *fields, name=name)

    @property
    def truthy(self):
        return True


class Field(Record):
    type = None
    def __init__(self, name: str, type=None, default=None, formula=None):
        self.name = name
        if type:
            self.type = type
        if default is None:
            default = py_value(None)
        if formula is None:
            formula = py_value(None)
        super().__init__(BuiltIns['Field'])
        # , name=py_value(name),
        # type=ParamSet(Parameter(type)) if type else BuiltIns['blank'],
        # is_formula=py_value(formula is not None),
        # default=default, formula=formula)


class Slot(Field):
    def __init__(self, name, type, default=None):
        match default:
            case Function(op_list=[Option(pattern=
                                          ParamSet(parameters=(Parameter(binding='self'), ))
                                          )]):
                pass  # assert that default is a function whose sole option is [<patt> self]: ...
            case _:
                assert default is None
        self.default = default
        super().__init__(name, type, default)

    # def get_data(self, rec, idx):
    #     return rec.data[idx]
    #
    # def set_data(self, rec, idx, value):
    #     rec.data[idx] = value
    #     return BuiltIns['blank']

    def __repr__(self):
        return f"Slot({self.name}: {self.type}{' ('+str(self.default)+')' if self.default else ''})"


class Formula(Field):
    def __init__(self, name, type, formula):
        self.formula = formula
        super().__init__(name, type, None, formula)

    # def get_data(self, rec, idx):
    #     return self.formula.call(rec)

    def __repr__(self):
        return f"Formula({self.name}: {str(self.formula)})"

class Setter(Field):
    fn: Function
    def __init__(self, name: str, fn: Function):
        self.fn = fn
        super().__init__(name)

    # def set_data(self, rec, idx, value):
    #     return self.fn.call(rec, value)

    def __repr__(self):
        return f"Setter({self.name}: {self.fn})"


# class Pattern(Record):
#     def __init__(self):
#         super().__init__(BuiltIns['Pattern'])
#
#
# class Matcher(Pattern):
#     guard = None
#     invert = False
#     def __init__(self, name: str = None, guard: Function | PyFunction = None, inverse=False):
#         if name is not None or guard is not None or inverse:
#             raise Exception("Check this out.  Can we get rid of these properties entirely?")
#         self.name = name
#         self.guard = guard
#         self.invert = inverse
#         super().__init__()
#
#     def match_score(self, arg: Record) -> bool | float:
#         return self.basic_score(arg)
#         # score = self.basic_score(arg)
#         # if self.invert:
#         #     score = not score
#         # if score and self.guard:
#         #     result = self.guard.call(arg)
#         #     return score * BuiltIns['bool'].call(result).value
#         # return score
#
#     def basic_score(self, arg):
#         # implemented by subclasses
#         raise NotImplementedError
#
#     def issubset(self, other):
#         print('WARNING: Matcher.issubset method not implemented properly yet.')
#         return self.equivalent(other)
#
#     def equivalent(self, other):
#         return True
#         # return (other.guard is None or self.guard == other.guard) and self.invert == other.invert
#
#     # def call_guard(self, arg: Record) -> bool:
#     #     if self.guard:
#     #         result = self.guard.call(arg)
#     #         return BuiltIns['bool'].call(result).value
#     #     return True
#
#     def get_rank(self):
#         return self.rank
#         # rank = self.rank
#         # if self.invert:
#         #     rank = tuple(100 - n for n in rank)
#         # if self.guard:
#         #     rank = (rank[0], rank[1] - 1, *rank[1:])
#         # return rank
#
#     def __lt__(self, other):
#         return self.get_rank() < other.get_rank()
#
#     def __le__(self, other):
#         return self.get_rank() <= other.get_rank()
#
#     # def __eq__(self, other):
#     #     return self.get_rank() == other.get_rank()
#
# class TableMatcher(Matcher):
#     table: Table
#     rank = 5, 0
#
#     def __init__(self, table, name=None, guard=None, inverse=False):
#         assert isinstance(table, Table)
#         self.table = table
#         super().__init__(name, guard, inverse)
#
#     def basic_score(self, arg: Record) -> bool:
#         return arg.table == self.table or self.table in arg.table.traits
#
#     def issubset(self, other):
#         match other:
#             case TableMatcher(table=table):
#                 return table == self.table
#             case TraitMatcher(trait=trait):
#                 return trait in self.table.traits
#         return False
#
#     def equivalent(self, other):
#         return isinstance(other, TableMatcher) and self.table == other.table
#
#     def __repr__(self):
#         return f"TableMatcher({self.table})"
#
# class TraitMatcher(Matcher):
#     trait: Trait
#     rank = 6, 0
#
#     def __init__(self, trait):
#         self.trait = trait
#
#     def basic_score(self, arg: Record) -> bool:
#         return self.trait in arg.table.traits
#
#     def issubset(self, other):
#         return isinstance(other, TraitMatcher) and other.trait == self.trait
#
#     def equivalent(self, other):
#         return isinstance(other, TraitMatcher) and other.trait == self.trait
#
#     def __repr__(self):
#         return f"TraitMatcher({self.trait})"
#
#
# class ValueMatcher(Matcher):
#     value: Record
#     rank = 1, 0
#
#     def __init__(self, value):
#         self.value = value
#
#     def basic_score(self, arg: Record) -> bool:
#         return arg == self.value
#
#     def issubset(self, other):
#         match other:
#             case ValueMatcher(value=value):
#                 return value == self.value
#             case TableMatcher(table=table):
#                 return self.value.table == table
#             case TraitMatcher(trait=trait):
#                 return trait in self.value.table.traits
#         return False
#
#     def equivalent(self, other):
#         return isinstance(other, ValueMatcher) and other.value == self.value
#
#     def __repr__(self):
#         return f"ValueMatcher({self.value})"
#
#
# class FunctionMatcher(Matcher):
#     # pattern: ParamSet
#     # return_type: Matcher
#     def __init__(self, pattern, return_type, name=None, guard=None, inverse=False):
#         self.pattern = pattern
#         self.return_type = return_type
#         super().__init__(name, guard, inverse)
#
#     def basic_score(self, arg):
#         if not hasattr(arg, 'op_list'):
#             return False
#         arg: Function
#
#         def options():
#             yield from arg.op_list
#             yield from arg.op_map.values()
#
#         if all((option.pattern.issubset(self.pattern) and option.return_type.issubset(self.return_type)
#                 for option in options())):
#             return True
#
#     def issubset(self, other):
#         match other:
#             case FunctionMatcher(pattern=patt, return_type=ret):
#                 return self.pattern.issubset(patt) and self.return_type.issubset(ret)
#             case TraitMatcher(trait=BuiltIns.get('fn')) | TableMatcher(table=BuiltIns.get('Function')):
#                 return True
#         return False
#
#     def equivalent(self, other):
#         return (isinstance(other, FunctionMatcher)
#                 and other.pattern == self.pattern
#                 and other.return_type == self.return_type)
#
#
# class AnyMatcher(Matcher):
#     rank = 100, 0
#     def basic_score(self, arg: Record) -> True:
#         return True
#
#     def issubset(self, other):
#         return isinstance(other, AnyMatcher)
#
#     def equivalent(self, other):
#         return isinstance(other, AnyMatcher)
#
#     def __repr__(self):
#         return f"AnyMatcher()"
#
# class EmptyMatcher(Matcher):
#     rank = 3, 0
#     def basic_score(self, arg: Record) -> bool:
#         match arg:
#             case VirtTable():
#                 return False
#             case PyValue(value=str() | tuple() | frozenset() | list() | set() as v) | Table(records=v):
#                 return len(v) == 0
#             case Function(op_list=options, op_map=hashed_options):
#                 return bool(len(options) + len(hashed_options))
#             case _:
#                 return False
#
#     def issubset(self, other):
#         return isinstance(other, EmptyMatcher)
#
#     def equivalent(self, other):
#         return isinstance(other, EmptyMatcher)
#
#     def __repr__(self):
#         return f"EmptyMatcher()"
#
#
# class ExprMatcher(Matcher):
#     def __init__(self, expr):
#         self.expression = expr
#     def basic_score(self, arg):
#         print(f"Line {Context.line}: WARNING: expr pattern not fully implemented yet.")
#         return self.expression.evaluate().truthy
#
#
# class IterMatcher(Matcher):
#     parameters: tuple
#     def __init__(self, *params):
#         self.parameters = params
#
#     def basic_score(self, arg: Record):
#         return self.match_zip(arg)[0]
#
#     def match_zip(self, arg: Record):
#         try:
#             it = iter(arg)  # noqa
#         except TypeError:
#             return 0, {}
#         state = MatchState(self.parameters, list(it))
#         return state.match_zip()
#
#
# class FieldMatcher(Matcher):
#     fields: dict
#
#     def __init__(self, **fields):
#         self.fields = fields
#
#     def basic_score(self, arg: Record):
#         for name, param in self.fields.items():
#             prop = arg.get(name, None)
#             if prop is None:
#                 if not param.optional:
#                     return False
#                 continue
#             if not param.pattern.match_score(prop):
#                 return False
#         return True
#
#     def match_zip(self, arg: Record):
#         raise NotImplementedError
#         # state = MatchState((), Args(**dict(((name, arg.get(name)) for name in self.fields))))
#         # return state.match_zip()
#
#
# class ParamSet(Matcher):
#     parameters: tuple
#     # machine: VM
#     named_params: frozendict
#     def __init__(self, *parameters, **named_params):
#         self.parameters = parameters
#         self.named_params = frozendict(named_params)
#         # self.vm = VM(parameters)
#         super().__init__()
#         # super().__init__(BuiltIns['ParamSet'])  # , parameters=py_value(parameters))
#
#     def match_score(self, *values: Record) -> int | float:
#         return self.match_zip(values)[0]
#
#     def issubset(self, other):
#         return (isinstance(other, ParamSet)
#                 and all(p1.issubset(p2) for (p1, p2) in zip(self.parameters, other.parameters))
#                 and all(self.named_params[k].issubset(other.named_params[k])
#                         for k in set(self.named_params).union(other.named_params)))
#
#     def __len__(self):
#         return len(self.parameters) + len(self.named_params)
#
#     def __getitem__(self, item):
#         return self.named_params.get(item, self.parameters[item])
#
#     def to_tuple(self):
#         if self.named_params:
#             return None
#         key: list[Record] = []
#         for parameter in self.parameters:
#             match parameter.pattern.matchers:
#                 case (ValueMatcher(value=value), ) if value.hashable():
#                     key.append(value)
#                 case _:
#                     return None
#         return tuple(key)
#
#     def to_args(self):
#         pos_args = []
#         names = {}
#         for id, param in self:
#             match param:
#                 case Parameter(quantifier='', pattern=ValueMatcher(value=val)):
#                     pass
#                 case _:
#                     return None
#             # if (val := param.pattern.value) is None:
#             #     return None
#             if isinstance(id, int):
#                 pos_args.append(val)
#             else:
#                 names[id] = val
#             # match param.pattern.matchers:
#             #     case (ValueMatcher(value=value), ) if value.hashable():
#             #         if isinstance(id, int):
#             #             pos_args.append(value)
#             #         else:
#             #             names[id] = value
#             #     case _:
#             #         return None
#         return Args(*pos_args, **names)
#
#     def __iter__(self):
#         yield from enumerate(self.parameters)
#         yield from self.named_params.items()
#
#     @memoize
#     def min_len(self) -> int:
#         count = 0
#         for param in self.parameters:
#             count += not param.optional
#         return count
#
#     @memoize
#     def max_len(self) -> int | float:
#         for param in self.parameters:
#             if param.quantifier in ("+", "*"):
#                 return math.inf
#         return len(self.parameters)
#
#     def match_zip(self, args=None) -> tuple[float | int, dict[str, Record]]:
#         if args is None:
#             return 1, {}
#         if len(args) == 0 == self.min_len():
#             return 1, {}
#         if not self.min_len() <= len(args) <= self.max_len():
#             return 0, {}
#         if isinstance(args, tuple):
#             args = Args(*args)
#         return MatchState(self.parameters, args).match_zip()
#         # state = MatchState(self.parameters, args)
#         # return self.match_zip_recursive(state)
#
#     @memoize
#     def min_len(self) -> int:
#         count = 0
#         for param in self.parameters:
#             count += not param.optional
#         return count
#
#     @memoize
#     def max_len(self) -> int | float:
#         for param in self.parameters:
#             if param.quantifier in ("+", "*"):
#                 return math.inf
#         return len(self.parameters)
#
#     def __lt__(self, other):
#         if not isinstance(other, ParamSet):
#             return NotImplemented
#         return self.parameters < other.parameters
#
#     def __le__(self, other):
#         if not isinstance(other, ParamSet):
#             return NotImplemented
#         return self.parameters <= other.parameters
#
#     def __eq__(self, other):
#         return (isinstance(other, ParamSet)
#                 and self.parameters == other.parameters
#                 and self.named_params == other.named_params)
#
#     def __hash__(self):
#         return hash((self.parameters, self.named_params))
#
#     def __gt__(self, other):
#         if not isinstance(other, ParamSet):
#             return NotImplemented
#         return self.parameters > other.parameters
#
#     def __ge__(self, other):
#         if not isinstance(other, ParamSet):
#             return NotImplemented
#         return self.parameters >= other.parameters
#
#     def __repr__(self):
#         return f"ParamSet({', '.join(self.parameters)}{'; ' + str(self.named_params) if self.named_params else ''})"
#
# class Intersection(Pattern):
#     patterns: tuple[Pattern, ...]
#     def __init__(self, *patterns: Pattern, binding=None):
#         if binding is not None:
#             raise Exception("This should be a parameter, not an Intersection.")
#         self.patterns = patterns
#         super().__init__()
#
#     @property
#     def matchers(self):
#         return self.patterns
#
#     def match_score(self, arg: Record):
#         return all(m.match_score(arg) for m in self.matchers)
#
#     def issubset(self, other):
#         match other:
#             case Matcher() as other_matcher:
#                 return any(m.issubset(other_matcher) for m in self.matchers)
#             case Intersection() as patt:
#                 return any(matcher.issubset(patt) for matcher in self.matchers)
#             case Union(patterns=patterns):
#                 return any(self.issubset(patt) for patt in patterns)
#             case Parameter(pattern=pattern):
#                 return self.issubset(pattern)
#         return False
#
#     def __lt__(self, other):
#         match other:
#             case Intersection(matchers=other_matchers):
#                 return (len(self.matchers) > len(other_matchers)
#                         or len(self.matchers) == len(other_matchers) and self.matchers < other_matchers)
#             case Union(patterns=patterns):
#                 return any(self <= p for p in patterns)
#             case _:
#                 raise NotImplementedError
#
#     def __le__(self, other):
#         match other:
#             case Intersection(matchers=other_matchers):
#                 return (len(self.matchers) > len(other_matchers)
#                         or len(self.matchers) == len(other_matchers) and self.matchers <= other_matchers)
#             case Union(patterns=patterns):
#                 return any(self <= p for p in patterns)
#             case _:
#                 raise NotImplementedError
#
#     def __hash__(self):
#         return hash(self.patterns)
#
#     def __eq__(self, other):
#         match other:
#             case Intersection(matchers=matchers):
#                 return matchers == self.matchers
#             case Union(patterns=(Pattern() as patt, )):
#                 return self == patt
#             case Matcher() as m:
#                 return len(self.matchers) == 1 and self.matchers[0] == m
#         return False
#
#
# class Union(Pattern):
#     patterns: tuple[Pattern, ...]
#     def __init__(self, *patterns, binding=None):
#         self.patterns = patterns
#         if binding is not None:
#             raise Exception("Shoulda been a Parameter!")
#         super().__init__()
#
#     def match_score(self, arg: Record):
#         return any(p.match_score(arg) for p in self.patterns)
#
#     def issubset(self, other):
#         return all(p.issubset(other) for p in self.patterns)
#
#     def __lt__(self, other):
#         match other:
#             case Intersection():
#                 return all(p < other for p in self.patterns)
#             case Union(patterns=patterns):
#                 return self.patterns < patterns
#             case _:
#                 raise NotImplementedError
#
#     def __le__(self, other):
#         match other:
#             case Intersection():
#                 return all(p <= other for p in self.patterns)
#             case Union(patterns=patterns):
#                 return self.patterns <= patterns
#             case _:
#                 raise NotImplementedError
#
#     def __eq__(self, other):
#         match self.patterns:
#             case ():
#                 return isinstance(other, Union) and other.patterns == ()
#             case (Pattern() as patt, ):
#                 return patt == other
#         return isinstance(other, Union) and self.patterns == other.patterns
#
#
# class Parameter(Pattern):
#     pattern: Pattern | None = None
#     binding: str = None  # property
#     quantifier: str  # "+" | "*" | "?" | "!" | ""
#     count: tuple[int, int | float]
#     optional: bool
#     required: bool
#     multi: bool
#     default = None
#
#     # @property
#     # def binding(self): return self.pattern.binding
#
#     def __init__(self, pattern, binding: str = None, quantifier="", default=None):
#         self.pattern = patternize(pattern)
#         self.binding = binding
#         # self.name = self.pattern.binding
#         if default:
#             if isinstance(default, Option):
#                 self.default = default
#             else:
#                 self.default = Option(ParamSet(), default)
#             match quantifier:
#                 case "":
#                     quantifier = '?'
#                 case "+":
#                     quantifier = "*"
#         self.quantifier = quantifier
#         super().__init__()
#
#     def issubset(self, other):
#         if not isinstance(other, Parameter):
#             raise NotImplementedError(f"Not yet implemented Parameter.issubset({other.__class__})")
#         if self.count[1] > other.count[1] or self.count[0] < other.count[0]:
#             return False
#         return self.pattern.issubset(other.pattern)
#
#     def _get_quantifier(self) -> str:
#         return self._quantifier
#     def _set_quantifier(self, quantifier: str):
#         self._quantifier = quantifier
#         match quantifier:
#             case "":
#                 self.count = (1, 1)
#             case "?":
#                 self.count = (0, 1)
#             case "+":
#                 self.count = (1, math.inf)
#             case "*":
#                 self.count = (0, math.inf)
#             case "!":
#                 self.count = (1, 1)
#                 # union matcher with `nonempty` pattern
#         self.optional = quantifier in ("?", "*")
#         self.required = quantifier in ("", "+")
#         self.multi = quantifier in ("+", "*")
#     quantifier = property(_get_quantifier, _set_quantifier)
#
#     def match_score(self, value) -> int | float: ...
#
#     def compare_quantifier(self, other):
#         return "_?+*".find(self.quantifier) - "_?+*".find(other.quantifier)
#
#     def __lt__(self, other):
#         match other:
#             case Parameter():
#                 q = self.compare_quantifier(other)
#                 return q < 0 or q == 0 and self.pattern < other.pattern
#         return NotImplemented
#
#     def __le__(self, other):
#         match other:
#             case Parameter():
#                 q = self.compare_quantifier(other)
#                 return q < 0 or q == 0 and self.pattern <= other.pattern
#         return NotImplemented
#
#     def __eq__(self, other):
#         match other:
#             case Parameter() as param:
#                 pass
#             case Matcher() | Pattern():
#                 param = Parameter(other)
#             case ParamSet(parameters=(param, ), named_params={}):
#                 pass
#             case _:
#                 return False
#         return self.quantifier == param.quantifier and self.pattern == param.pattern and self.default == param.default
#
#     def __hash__(self):
#         return hash((self.pattern, self.quantifier, self.default))
#
#     def __gt__(self, other):
#         match other:
#             case Parameter():
#                 q = self.compare_quantifier(other)
#                 return q < 0 or q == 0 and self.pattern > other.pattern
#         return NotImplemented
#
#     def __ge__(self, other):
#         match other:
#             case Parameter():
#                 q = self.compare_quantifier(other)
#                 return q < 0 or q == 0 and self.pattern >= other.pattern
#         return NotImplemented
#
#     def __repr__(self):
#         return f"Parameter({self.pattern} {self.binding or ''}{self.quantifier})"
#
#
class MatchState:
    def __init__(self, pattern, args, i_param=0, i_arg=0, named_params=None, score=0, param_score=0, bindings=None):
        self.pattern = pattern
        self.args = args
        self.i_param = i_param
        self.i_arg = i_arg
        self.score = score
        self.param_score = param_score
        self.bindings = bindings or {}
        # self.satisfied_named_params = satisfied_named_params or set()
        self.named_params = named_params or self.pattern.named_params.copy()
        # self.done = i_param == len(parameters) and i_arg == len(args)
        if i_param > len(pattern.parameters) or i_arg > len(args.positional_arguments):
            raise RuntimeErr(f"Line {Context.line}: ParamSet error: i_param or i_arg went out of bounds.")

    @property
    def success(self):
        if self.i_param > len(self.pattern.parameters) or self.i_arg > len(self.args.positional_arguments):
            raise RuntimeErr(f"Line {Context.line}: ParamSet error: i_param or i_arg went out of bounds.")
        return (self.i_param == len(self.pattern.parameters)
                and self.i_arg == len(self.args.positional_arguments)
                # and used up named arguments
                and self.score)


    @property
    def param(self):
        if self.i_param < len(self.pattern.parameters):
            return self.pattern.parameters[self.i_param]

    @property
    def arg(self):
        if self.i_arg < len(self.args.positional_arguments):
            return self.args[self.i_arg]

    def branch(self, **kwargs):
        bindings = self.bindings.copy().update(kwargs.get('bind', {}))
        named_params = self.named_params.copy().update(kwargs.get('named_params', {}))
        for key in self.__dict__:
            if key not in kwargs:
                kwargs[key] = self.__dict__[key]
        return MatchState(**kwargs, bindings=bindings, named_params=named_params)

    def match_zip(self):
        # first, match all the required named parameters (since those can't be matched by positional args)
        for name, param in self.named_params.items():
            arg = self.args.try_get(name)
            if arg is None or not param.match_score(arg):
                if param.required:
                    return 0, {}
            elif param.optional:
                branch = self.branch(bind={name: arg})
                del branch.named_params[name]
                score, bindings = branch.match_zip()
                if score:
                    return score, bindings
            else:
                del self.named_params[name]
                self.bindings[name] = arg

        while param := self.param:
            name = param.binding
            if name in self.args.named_arguments and name not in self.bindings:
                branch = self.branch()
                branch.bindings[name] = self.args.named_arguments[name]
                branch.i_param += 1
                score, bindings = branch.match_zip()
                if score:
                    return score, bindings
            if name in self.args.flags and name not in self.bindings:
                self.bindings[name] = BuiltIns['true']
                self.i_param += 1
                continue
            if isinstance(param.pattern, UnionMatcher):
                # TODO: I don't think this is logically sound.  I think I need to find a new approach.  I need to abstract more.
                param_tuple = self.parameters.parameters
                param_list = list(param_tuple)
                for patt in param.pattern.matchers:
                    param_list[self.i_param] = Parameter(patt)
                    self.parameters.parameters = tuple(param_list)
                    new_params = [*self.parameters[:self.i_param], param, *self.parameters[self.i_param + 1:]]
                    score, bindings = self.branch(parameters=new_params).match_zip()
                    if score:
                        self.parameters.parameters = param_tuple
                        return score, bindings
                self.parameters.parameters = param_tuple
                return 0, {}

            key: str | int = name or self.i_param
            if self.arg is not None:
                match_value = param.pattern.match_score(self.arg)
            else:
                match_value = 0  # no arguments left to process match

            # clear param score if you have moved on...
            # Wait, this is wrong.  I need to clear the param score only when I
            assert not (self.param_score and not param.multi)
            # self.param_score *= param.multi

            if param.required and match_value == 0 == self.param_score:
                return 0, self.bindings
            match param.quantifier:
                case "":
                    # match patt, save, and move on
                    if not match_value:
                        return 0, {}
                    self.bindings[key] = self.arg
                    self.score += match_value
                    self.i_arg += 1
                    self.i_param += 1
                case "?":
                    # try match patt and save... move on either way
                    self.i_param += 1
                    if match_value:
                        branch = self.branch()
                        branch.bindings[key] = self.arg
                        branch.score += match_value
                        branch.i_arg += 1
                        score, bindings = branch.match_zip()
                        if score:
                            return score, bindings
                    elif param.default:
                        self.bindings[key] = param.default.resolve()
                case "+" | "*":
                    if key not in self.bindings:
                        self.bindings[key] = []
                        if not match_value and param.default:
                            self.bindings[key] = param.default.resolve()
                    if match_value:
                        branch = self.branch()
                        branch.i_arg += 1
                        branch.param_score += match_value
                        branch.bindings[key].append(self.arg)
                        score, bindings = branch.match_zip()
                        if score:
                            return score, bindings
                    if self.param_score:  #  if len(saves[key].value):
                        self.score += self.param_score / len(self.bindings[key])
                    self.i_param += 1
                    self.param_score = 0
        if self.success:
            return self.score_and_bindings()
        return 0, {}

    def score_and_bindings(self):
        for key, value in self.bindings.items():
            if isinstance(value, list):
                self.bindings[key] = py_value(tuple(value))
        self.score /= len(self.parameters)
        return self.score, self.bindings

# def patternize(val):
#     match val:
#         case Matcher():
#             return Parameter(val)
#         case Parameter():
#             return val
#         case Table():
#             return Parameter(TableMatcher(val))
#         case Trait():
#             return Parameter(TraitMatcher(val))
#         case Record():
#             return Parameter(ValueMatcher(val))
#         case _:
#             raise TypeErr(f"Line {Context.line}: Could not patternize {val}")


class Args(Record):
    # I tried to make Args no longer child of Record, but then the dot-operator fails to pattern match on it
    positional_arguments: list[Record] | tuple[Record, ...]
    named_arguments: dict[str, Record]
    flags: set[str]
    def __init__(self, *args: Record, flags: set[str] = None, named_arguments: dict[str, Record] = None, **kwargs: Record):
        self.positional_arguments = args
        self.flags = flags or set()
        self.named_arguments = named_arguments or kwargs
        super().__init__(BuiltIns['Args'])

    def __len__(self):
        return len(self.positional_arguments) + len(self.named_arguments) + len(self.flags)

    def __getitem__(self, key):
        if key in self.flags:
            return BuiltIns['true']
        return self.named_arguments.get(key, self.positional_arguments[key])

    def try_get(self, key):
        match key:
            case str():
                return BuiltIns['true'] if key in self.flags else self.named_arguments.get(key, None)
            case int():
                try:
                    return self.positional_arguments[key]
                except IndexError:
                    return None
        raise TypeError(key)

    def __iter__(self):
        if self.flags or self.named_arguments:
            raise NotImplementedError
        return iter(self.positional_arguments)

    def keys(self):
        return self.named_arguments.keys()

    def __add__(self, other):
        match other:
            case Args(positional_arguments=pos, flags=flags, named_arguments=kwargs):
                pass
            case tuple() as pos:
                flags = set()
                kwargs = {}
            case set() as flags:
                pos = ()
                kwargs = {}
            case dict() as kwargs:
                pos = ()
                flags = set()
            case _:
                return NotImplemented
        return Args(*self.positional_arguments, *pos,
                    flags=self.flags.union(flags),
                    **self.named_arguments, **kwargs)

    def __radd__(self, other):
        match other:
            case Args(positional_arguments=pos, flags=flags, named_arguments=kwargs):
                pass
            case tuple() as pos:
                flags = set()
                kwargs = {}
            case set() as flags:
                pos = ()
                kwargs = {}
            case dict() as kwargs:
                pos = ()
                flags = set()
            case _:
                return NotImplemented
        return Args(*pos, *self.positional_arguments,
                    flags=self.flags.union(flags),
                    **self.named_arguments, **kwargs)

    def __eq__(self, other):
        return isinstance(other, Args) and self.dict() == other.dict()

    def dict(self):
        d = dict(enumerate(self.positional_arguments))
        d.update(self.named_arguments)
        for s in self.flags:
            d[s] = BuiltIns['true']
        return d

    def __hash__(self):
        d = self.dict()
        return hash((frozenset(d), frozenset(d.values())))

    def __repr__(self):
        pos = map(str, self.positional_arguments)
        names = (f"{k}={v}" for (k, v) in self.named_arguments.items())
        flags = ('!'+str(f) for f in self.flags)
        return f"Args({', '.join(pos)}; {', '.join(names)}; {' '.join(flags)})"


class Closure:
    """ essentially just a block of code together with the context (Frame) in which it was bound to a function-option """
    # block: Block  # Block class not yet defined
    scope = None
    def __init__(self, block):
        self.block = block
        self.scope = Context.env

    # def execute(self, args=None, caller=None, bindings=None, *, fn=None):
    #     if args is not None or fn is not None:
    #         closure = Frame(self.scope, args, caller, bindings, fn)
    #         Context.push(Context.line, closure)
    #
    #         def finish():
    #             Context.pop()
    #             return closure.return_value or caller or fn
    #     else:
    #         def finish():  # noqa
    #             return BuiltIns['blank']
    #         closure = Context.env
    #
    #     for tbl in self.block.table_names:
    #         closure.locals[tbl] = ListTable(name=tbl)
    #     for trait in self.block.trait_names:
    #         closure.locals[trait] = Trait(name=trait)
    #     for fn in self.block.function_names:
    #         closure.locals[fn] = Function(name=fn)
    #     self.block.execute()
    #     return finish()

    def execute(self, args=None, caller=None, bindings=None, *, fn=None):
        env = Frame(self.scope, args, caller, bindings, fn)
        if fn:
            fn.frame = env
        Context.push(Context.line, env)
        self.block.execute()
        Context.pop()
        return env.return_value or caller or fn

    def __repr__(self):
        return f"Closure({len(self.block.statements)})"

class Native(Closure):
    def __init__(self, fn: PyFunction):
        self.fn = fn
        self.scope = Context.env

    def execute(self, args=None, caller=None, bindings=None, *, fn=None):
        assert args is not None or fn is not None
        env = Frame(self.scope, args, caller, bindings, fn)
        Context.push(Context.line, env)
        line = Context.line
        if isinstance(args, tuple):
            env.return_value = self.fn(*args)
        else:
            env.return_value = self.fn(args)
        Context.line = line
        Context.pop()
        return env.return_value or caller or fn

    def __repr__(self):
        return f"Native({self.fn})"

class Frame:
    return_value = None
    def __init__(self, scope, args=None, caller=None, bindings=None, fn=None):
        # self.names = bindings or {}
        self.vars = {}
        self.locals = bindings or {}
        # self.block = block
        # self.scope = code_block.scope
        self.scope = scope
        self.args = args
        self.caller = caller
        self.fn = fn

    def assign(self, name: str, value: Record):
        scope = self
        while scope:
            if name in scope.vars:
                scope.vars[name] = value
                return value
            scope = scope.scope
        self.locals[name] = value
        # if isinstance(self.fn, Function):
        #     self.fn.slot_dict[name] = value
        return value

    def __getitem__(self, key: str):
        return self.vars.get(key, self.locals.get(key, None))

    def update(self, bindings: dict):
        for name, rec in bindings.items():
            self.assign(name, rec)

    def __repr__(self):
        return (f"Frame({len(self.vars) + len(self.locals)} names; " 
                f"{'running' if self.return_value is None else 'finished: ' + str(self.return_value)})")

class GlobalFrame(Frame):
    block = None
    scope = None
    args = None
    caller = None
    fn = None
    def __init__(self, bindings: dict[str, Record]):
        self.vars = {}
        self.locals = bindings

class Option(Record):
    value = None
    block = None
    fn = None
    alias = None
    dot_option = False
    return_type = None
    def __init__(self, pattern, resolution=None):
        match pattern:
            case ParamSet():
                self.pattern = pattern
            case Parameter() as param:
                self.pattern = ParamSet(param)
            case _:
                self.pattern = ParamSet(Parameter(patternize(pattern)))
        if resolution is not None:
            self.resolution = resolution
        super().__init__(BuiltIns['Option'])  # , signature=self.pattern, code_block=self.resolution)

    # def is_null(self):
    #     return (self.value and self.block and self.fn and self.alias) is None
    # def not_null(self):
    #     return (self.value or self.block or self.fn or self.alias) is not None
    def nullify(self):
        if self.value is not None:
            del self.value
        if self.block is not None:
            del self.block
        if self.fn is not None:
            del self.fn
        if self.alias is not None:
            del self.alias
    def set_resolution(self, resolution):
        if self.alias:
            self.alias.set_resolution(resolution)
            return
        self.nullify()
        match resolution:
            case Closure():
                self.block = resolution
            case PyFunction(): self.fn = resolution
            case Option(): self.alias = resolution
            case Record():
                self.value = resolution
                self.return_type = ValueMatcher(resolution)
            # case _:  # assume type Block (not defined yet)
            #     self.block = resolution
            case _:
                raise ValueError(f"Line {Context.line}: Could not assign resolution {resolution} to option {self}")
    def get_resolution(self):
        if self.value is not None:
            return self.value
        return self.block or self.fn or self.alias

    resolution = property(get_resolution, set_resolution, nullify)

    def resolve(self, args, caller, bindings=None, _self=None):
        if isinstance(args, tuple):
            print("WARNING: encountered tuple of args rather than Args object.")
        if self.alias:
            return self.alias.resolve(args, caller, bindings, _self)
        if self.value is not None:
            return self.value
        if self.fn:
            if isinstance(args, Args):
                return call(self.fn, args)
            return self.fn(*args)
        # if self.dot_option:
        #     caller = args[0]
        if self.block:
            return self.block.execute(args, caller, bindings)
            # closure = Closure(self.block, args, caller, bindings)
            # Context.push(Context.line, closure, self)
            # res = self.block.evaluate()
            # Context.pop()
            # return res
        raise NoMatchingOptionError(f"Line {Context.line}: Could not resolve null option")

    def __eq__(self, other):
        return isinstance(other, Option) and (self.pattern, self.resolution) == (other.pattern, other.resolution)

    def __repr__(self):
        if self.value:
            return f"Opt({self.pattern}={self.value})"
        if self.block or self.fn:
            return f"Opt({self.pattern}: {self.block or self.fn})"
        if self.alias:
            return f"Opt({self.pattern} -> {self.alias})"
        return f"Opt({self.pattern} -> null)"


# class Operator:
#     def __init__(self, text, fn=None,
#                  prefix=None, postfix=None, binop=None, ternary=None,
#                  associativity='left',
#                  chainable=False,
#                  static=False):
#         Op[text] = self
#         self.text = text
#         # self.precedence = precedence
#         if fn:
#             if not fn.name:
#                 fn.name = text
#             BuiltIns[text] = fn
#         self.fn = fn
#         self.associativity = associativity  # 'right' if 'right' in flags else 'left'
#         self.prefix = prefix  # 'prefix' in flags
#         self.postfix = postfix  # 'postfix' in flags
#         self.binop = binop  # 'binop' in flags
#         self.ternary = ternary
#         self.static = static  # 'static' in flags
#         self.chainable = chainable
#
#         assert self.binop or self.prefix or self.postfix or self.ternary
#
#     def eval_args(self, lhs, rhs) -> Args:
#         raise NotImplementedError('Operator.prepare_args not implemented')
#
#     def __repr__(self):
#         return self.text

from patterns import *