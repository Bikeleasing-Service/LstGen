"""
Go generator
"""
import ast
from .. import (
    parse_eval_stmt,
    prepare_expr
)
from .. import (
    EvalStmt,
    IfStmt,
    ThenStmt,
    ElseStmt,
    ExecuteStmt,
)
from .base import JavaLikeGenerator

class GoGenerator(JavaLikeGenerator):
    """ Go Generator """
    bd_class = 'decimal.Decimal'
    bd_class_constructor = 'decimal.NewFromInt'
    list_const_parens = ('{', '}')
    stmt_separator = ''
    allow_constants = False
    instance_var = 't'

    def __init__(self, parser, outfile, class_name=None, indent=None, package_name='default'):
        super(GoGenerator, self).__init__(parser, outfile, class_name, indent)
        self.package_name = package_name

    def generate(self):
        wr = self.writer
        self._write_comment("This file is automatically generated by LstGen, do not edit!", False)
        wr.writeln('package {}'.format(self.package_name or 'tax'))
        wr.nl()
        wr.writeln('import ( "github.com/shopspring/decimal" )')
        wr.nl()

        # Define the model as a struct.
        with self.writer.indent('type {} struct'.format(self.class_name)):
            wr.writeln("// ------------------------ Constants -------------------------")
            for const in self.parser.constants:
                if const.comment is not None:
                    wr.nl()
                    self._write_comment(const.comment, False)

                if const.type.endswith('[]'):
                    const.value = '[{}]'.format(const.value[1:-1])

                thetype = self._convert_vartype(const.type)
                wr.writeln('{const.name} {thetype}'.format(
                    const=const,
                    thetype=thetype
                ))

            for (comment, variables) in [
                    ('Input variables', self.parser.input_vars),
                    ('Output variables', self.parser.output_vars),
                    ('Internal variables', self.parser.internal_vars),
                ]:
                wr.nl()
                wr.writeln('// {}'.format(comment))

                wr.writeln("// ------------------------ Variables -------------------------")
                for var in variables:
                    if var.comment is not None:
                        wr.nl()
                        self._write_comment(var.comment, False)
                    vartype = self._convert_vartype(var.type)
                    wr.writeln('{} {}'.format(var.name, vartype))

        # Define the New() method that also sets default values.
        with self.writer.indent('func New{cls}() *{cls}'.format(cls=self.class_name)):
            with self.writer.indent('return &{}'.format(self.class_name)):
                wr.writeln("// ------------------------ Constants -------------------------")
                for const in self.parser.constants:
                    if const.comment is not None:
                        wr.nl()
                        self._write_comment(const.comment, False)

                    if const.type.endswith('[]'):
                        const.value = '[{}]'.format(const.value[1:-1])

                    value = self.convert_to_go(const.value)
                    wr.writeln('{const.name}: {value},'.format(
                        const=const,
                        value=value
                    ))

                wr.nl()
                wr.writeln("// ------------------------ Variables -------------------------")
                for (comment, variables) in [
                        ('Input variables', self.parser.input_vars),
                        ('Output variables', self.parser.output_vars),
                        ('Internal variables', self.parser.internal_vars),
                    ]:

                    for var in variables:
                        if var.default is None:
                            continue

                        if var.comment is not None:
                            wr.nl()
                            self._write_comment(var.comment, False)

                        value = self.convert_to_go(var.default)
                        wr.writeln('{}: {},'.format(var.name, value))


        # create setters for input vars
        for var in self.parser.input_vars:
            wr.nl()
            signature = 'func ({instance} *{cls}) Set{cap}(value {type})'.format(
                instance=self.instance_var,
                cls=self.class_name,
                cap=var.name.capitalize(),
                type=self._convert_vartype(var.type)
            )
            with wr.indent(signature):
                wr.writeln('{instance}.{name} = value'.format(
                    instance=self.instance_var,
                    name=var.name
                ))

        # create getters for output vars
        for var in self.parser.output_vars:
            wr.nl()
            signature = 'func ({instance} *{cls}) Get{cap}() {type}'.format(
                instance=self.instance_var,
                cls=self.class_name,
                cap=var.name.capitalize(),
                type=self._convert_vartype(var.type)
            )
            with wr.indent(signature):
                wr.writeln('return {instance}.{name}'.format(
                    instance=self.instance_var,
                    name=var.name
                ))

        self._write_method(self.parser.main_method)
        for method in self.parser.methods:
            self._write_method(method)
        wr.nl()

    def _convert_vartype(self, vartype):
        return {
            'BigDecimal.ZERO': 'decimal.NewFromInt(0)',
            'BigDecimal[]': '[]'+self.bd_class,
            'BigDecimal': ''+self.bd_class,
            'int': 'int64',
            'double': 'int64',
        }[vartype]

    def _conv_list(self, node):
        res = super(GoGenerator, self)._conv_list(node)
        return ['[]' + self.bd_class] + res

    def _conv_attribute(self, node):
        clsmethod = False
        if node.attr == 'valueOf':
            node.attr = 'NewFromInt'
            clsmethod = True
        elif node.attr == 'ZERO':
            node.attr = 'NewFromInt(0)'
            clsmethod = True
        elif node.attr == 'ONE':
            node.attr = 'NewFromInt(1)'
            clsmethod = True
        elif node.attr == 'TEN':
            node.attr = 'NewFromInt(10)'
            clsmethod = True
        elif node.attr == 'longValue':
            node.attr = 'IntPart'
        elif node.attr == 'add':
            node.attr = 'Add'
        elif node.attr == 'subtract':
            node.attr = 'Sub'
        elif node.attr == 'multiply':
            node.attr = 'Mul'
        elif node.attr == 'divide':
            node.attr = 'Div'
        elif node.attr == 'compareTo':
            node.attr = 'Cmp'
        elif node.attr == 'setScale':
            node.attr = 'Round'
        elif node.attr in ('ROUND_UP', 'ROUND_DOWN'):
            pass
        else:
            raise NotImplementedError("Warning: Unmapped attribute {}".format(node.attr))
        if clsmethod:
            return ['decimal', self.property_accessor_op, node.attr]
        return (
            self.to_code(node.value) +
            [self.property_accessor_op, node.attr]
        )

    def _get_decimal_constructor_from_node(self, node):
        try:
            int(str(node.n))
            return 'NewFromInt'
        except ValueError:
            return 'NewFromFloat'
        except AttributeError: # If node.nodes[0] is not a value, but e.g. a name or a call
            # Unfortunately it's not possible to support all cases due to the strict
            # typing of Go. However, we are "lucky":
            if node.__class__.__name__ == 'Name':
                # For now, all variable assignments that create new values happen to be integers.
                #print("Name...", node.id)
                return 'NewFromInt'
            elif node.__class__.__name__ == 'Call':
                # The nodeument is a function call. Again, luckily, the only function calls in
                # assignments are calls to Decimal methods, which we can ensure to return int64.
                #print("Call...", node.func.attr)
                return 'NewFromInt'
            elif node.__class__.__name__ == 'Constant':
                try:
                    int(str(node.value))
                    return 'NewFromInt'
                except ValueError:
                    return 'NewFromFloat'
            elif node.__class__.__name__ == 'BinOp':
                # For math operations, the type depends on the operators.
                #print("Call...", node.left, node.op, node.right)
                return self._get_decimal_constructor_from_node(node.left)
        raise NotImplementedError("unsupported node type {}".format(
            node.__class__.__name__
        ))

    def _conv_call(self, node):
        caller = self.to_code(node.func)

        # Fix calls to the Round function (Go's Decimal doesn't accept a rounding parameter,
        # so we need to map it to another function here.)
        if caller[-1] == 'Round' and len(node.args) > 1:
            if node.args[-1] == 'ROUND_DOWN':
                caller[-1] = 'RoundCash'
            node.args = node.args[:1]

        # Similarly for the Div function.
        elif caller[-1] == 'Div' and len(node.args) > 1:
            # FIXME: Div does not support ROUND_DOWN :-(
            caller[-1] = 'DivRound'
            node.args = node.args[:2]

        # Fix integer initialization-
        elif caller[-1] == 'NewFromInt':
            caller[-1] = self._get_decimal_constructor_from_node(node.args[0])

        args = []
        for (idx, arg) in enumerate(node.args):
            args += self.to_code(arg)
            if idx != len(node.args) - 1:
                args.append(self.call_args_delim)

        return (
            caller +
            [self.callable_exec_parens[0]] +
            args +
            [self.callable_exec_parens[1]]
        )

    def _write_method(self, method):
        #print("METH", dir(method))
        self.writer.nl()
        if method.comment:
            self._write_comment(method.comment, False)
        signature = 'func ({instance} *{cls}) {name}()'.format(
            instance=self.instance_var,
            cls=self.class_name,
            name=method.name
        )
        # actual method body
        with self.writer.indent(signature):
            self._write_stmt_body(method)

    def convert_to_go(self, value):
        """ Converts java pseudo code into valid java code """
        tree = ast.parse(prepare_expr(value))
        node = tree.body[0].value
        return ''.join(self.to_code(node))
