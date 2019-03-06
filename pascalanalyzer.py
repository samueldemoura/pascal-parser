import csv
import sys

DEBUG = 1

TOKEN = 0  # literal contents of symbol
SYMBOL = 1 # type of symbol
LINE = 2   # line at which symbol was found

class BailoutException(Exception):
    '''Exception type that does not necessarily imply parsing error.'''
    def __init__(self, message=None):
        super(BailoutException, self).__init__(message)
        if DEBUG:
            print(' \x1b[1;36m* Bailout raised:\x1b[0m {}'.format(message))

def methodwrapper(func):
    '''Function wrapper for debugging purposes.'''
    if DEBUG:
        def wrapper(*args, **kwargs):
            print(
                ' \x1b[1;31m* Calling\x1b[0m \x1b[1;33m{}\x1b[0m with sym = \x1b[1;34m{}\x1b[0m' \
                .format(func.__name__, args[0].sym[TOKEN])
                )
            return_value = func(*args, **kwargs)
            print(
                ' \x1b[1;32m* Leaving\x1b[0m \x1b[1;33m{}\x1b[0m with sym = \x1b[1;34m{}\x1b[0m' \
                .format(func.__name__, args[0].sym[TOKEN])
                )
            return return_value
    else:
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

    return wrapper

class ScopeStack:
    '''Stack class for scope management.'''
    def __init__(self):
        self.mark = ['@']
        self._stack = []

    def new_scope(self):
        '''Inserts a scope marking in the stack.'''
        self._stack.append(self.mark)

    def create_id(self, identifier, identifier_type):
        '''Tries to create an identifier.'''
        for i in self._stack[::-1]:
            if i[0] == self.mark:
                break
            if i[0] == identifier:
                raise Exception(
                    'Tried to redefine already existing identifier `{}`.' \
                    .format(identifier)
                    )

        self._stack.append((identifier, identifier_type))

    def search(self, identifier):
        '''Looks for an identifier.'''
        for i in self._stack[::-1]:
            if i[0] == identifier:
                return i[1]
        raise Exception('Identifier `{}` was used before declaration.'.format(identifier))

    def end_scope(self):
        '''Leaves the current scope.'''
        self._stack.reverse()
        self._stack = self._stack[self._stack.index(self.mark)+1:]
        self._stack.reverse()

class TypeControlStack:
    '''Stack class for type checking.'''
    def __init__(self):
        self._stack = []
        self.precedence = {
            'not': (4, self.not_op),
            'and': (3, self.logical_op),
            'or': (3, self.logical_op),
            '*': (3, self.add_sub_or_mult_op),
            '/': (3, self.div_op),
            '+': (2, self.add_sub_or_mult_op),
            '-': (2, self.add_sub_or_mult_op),
            '<=': (1, self.relational_op),
            '>=': (1, self.relational_op),
            '<>': (1, self.relational_op),
            '=': (1, self.relational_op),
            '<': (1, self.relational_op),
            '>': (1, self.relational_op),
            ':=': (0, self.attribution)
        }

    #
    # Basic stack manipulation operations
    #
    def push(self, id_type):
        '''Pushes a type to the top of the stack.'''
        self._stack.append(id_type)

    def top(self):
        '''Returns the top of the stack.'''
        return self._stack[-1]

    def subtop(self):
        '''Returns the type below the top of the stack.'''
        return self._stack[-2]

    def update_top(self, id_type):
        '''Pops out top 2 types and replaces them with new type.'''
        self._stack.pop()
        self._stack.pop()
        self.push(id_type)

    def evaluate(self):
        '''Converts stack to postfix notation and evalutes to check if types are compatible.'''
        out = self.to_postfix()
        self._stack = []

        for element in out:
            # Check for operator and operate top two operands
            if element in self.precedence:
                self.precedence[element][1]()
            else:
                # Found operand, push to stack.
                self.push(element)

    #
    # Conversion to postfix notation
    #
    def to_postfix(self):
        '''Creates new stack from current, in postfix notation.'''
        out = []

        def isnt_higher_precedence(a, b):
            try:
                return True if self.precedence[a][0] <= self.precedence[b][0] else False
            except KeyError:
                return False

        for element in self._stack:
            if element == ')':
                # Pop from stack into output until the matching ( is found
                while self.subtop() != '(':
                    out.append(self._stack.pop())
                self._stack.pop() # Throw out remainder (
                continue

            if element in self.precedence:
                # Found an operator.
                while self._stack and isnt_higher_precedence(element, self.top()):
                    out.append(self._stack.pop())
                self._stack.append(element)
                continue

            # Doesn't fall into any of the above. Send directly to output.
            out.append(element)

        return out

    #
    # Type control logic
    #
    def add_sub_or_mult_op(self):
        # + | - | *
        if self.top() == 'integer' and self.subtop() == 'integer':
            self.update_top('integer')
            return

        if self.top() == 'real' and self.subtop() == 'real':
            self.update_top('real')
            return

        if self.top() == 'integer' and self.subtop() == 'real':
            self.update_top('real')
            return

        if self.top() == 'real' and self.subtop() == 'integer':
            self.update_top('real')
            return

        raise Exception(
            'Incompatible types for operation: {} and {}'.format(self.top(), self.subtop())
            )

    def div_op(self):
        # /
        if self.top() == 'integer' and self.subtop() == 'integer':
            self.update_top('real')
            return

        if self.top() == 'real' and self.subtop() == 'real':
            self.update_top('real')
            return

        if self.top() == 'integer' and self.subtop() == 'real':
            self.update_top('real')
            return

        if self.top() == 'real' and self.subtop() == 'integer':
            self.update_top('real')
            return

        raise Exception(
            'Incompatible types for operation: {} and {}'.format(self.top(), self.subtop())
            )

    def logical_op(self):
        # and | or
        if self.top() == 'boolean' and self.subtop() == 'boolean':
            self.update_top('boolean')
        else:
            raise Exception(
                'Incompatible types for logical operation: {} and {}' \
                .format(self.top(), self.subtop())
            )

    def relational_op(self):
        # <= | >= | <> | = | < | >
        if self.top() == 'integer' and self.subtop() == 'integer':
            self.update_top('boolean')
            return

        if self.top() == 'real' and self.subtop() == 'real':
            self.update_top('boolean')
            return

        if self.top() == 'integer' and self.subtop() == 'real':
            self.update_top('boolean')
            return

        if self.top() == 'real' and self.subtop() == 'integer':
            self.update_top('boolean')
            return

        raise Exception(
            'Incompatible types for operation: {} and {}'.format(self.top(), self.subtop())
            )

    def attribution(self):
        # :=
        if self.top() == self.subtop():
            # Attribution does not return a new type, just pop
            self._stack.pop()
            self._stack.pop()
        else:
            raise Exception(
                'Incompatible types for attribution: {} and {}' \
                .format(self.top(), self.subtop())
            )

    def not_op(self):
        # not
        if self.top() == 'boolean':
            pass # `not` operator still leaves a boolean
        else:
            raise Exception(
                'Incompatible types for not operation: {}' \
                .format(self.top())
                )

#
# Analyzer
#
class Analyzer:
    file = None # Input file handle
    tokens = [] # Token list
    counter = 0 # "Current token" counter
    sym = None
    scope_stack = ScopeStack()
    type_stack = TypeControlStack()

    def parse_tokens_into_list(self, filename):
        '''Parse tokens from input CSV file to token list.'''
        with open(filename, 'r') as file:
            reader = csv.reader(file)

            line = next(reader)
            if line != ['token', 'classification', 'line']:
                print('ERROR: Not a valid input file.')
                quit()

            for row in reader:
                self.tokens.append((row[0], row[1], row[2].strip()))

    def get_next_token(self):
        '''Returns next token in a (token, identifier, line) tuple.'''
        token = self.tokens[self.counter]
        self.counter += 1

        if DEBUG > 1:
            print(token)

        return token

    def start(self):
        '''Read first program token and fire off recursive calls.'''
        self.sym = self.get_next_token()
        if self.sym[TOKEN] == 'program':
            self.scope_stack.new_scope()
            self.program()
        else:
            raise Exception(
                'Program did not start with program keyword. Started with {} instead.' \
                .format(self.sym[TOKEN])
                )

    #
    # Token methods
    #
    @methodwrapper
    def program(self):
        # Try to read program identifier
        self.sym = self.get_next_token()
        if self.sym[SYMBOL] == 'identifier':
            self.scope_stack.create_id(self.sym[TOKEN], 'program_declaration')
        else:
            raise Exception(
                'Error parsing {} at line {}: missing program name identifier.' \
                .format(self.sym[TOKEN], self.sym[LINE])
                )

        # Read ; after program identifier
        self.sym = self.get_next_token()
        if self.sym[TOKEN] != ';':
            raise Exception('Missing ; at line {}.'.format(self.sym[LINE]))

        # Determine what comes after that
        self.sym = self.get_next_token()
        self.var_declarations()
        self.subprogram_declarations()
        self.compound_command()

        if self.sym[TOKEN] != '.':
            raise Exception('File did not end with a `.`!')


    @methodwrapper
    def var_declarations(self):
        # var list_of_var_declarations | <empty>
        if self.sym[TOKEN] == 'var':
            self.sym = self.get_next_token()
            self.list_of_var_declarations()


    @methodwrapper
    def list_of_var_declarations(self):
        # list_of_ids: type; list_of_var_declarations_l
        list_ids = self.list_of_ids()

        if self.sym[TOKEN] != ':':
            raise Exception('Missing : at line {}'.format(self.sym[LINE]))

        self.sym = self.get_next_token()
        aux_type = self.sym[TOKEN]
        self.type()

        for i in list_ids:
            self.scope_stack.create_id(i, aux_type)

        if self.sym[TOKEN] != ';':
            raise Exception('Missing ; at line {}'.format(self.sym[LINE]))

        self.sym = self.get_next_token()
        self.list_of_var_declarations_l()


    @methodwrapper
    def list_of_var_declarations_l(self):
        # list_of_ids: type; list_of_var_declarations_l | <empty>
        try:
            list_ids = self.list_of_ids()
        except BailoutException:
            # if there's not a list_of_ids here, it's optional anyways so bail out
            return

        if self.sym[TOKEN] != ':':
            raise Exception('Missing : at line {}'.format(self.sym[LINE]))

        self.sym = self.get_next_token()
        aux_type = self.sym[TOKEN]
        self.type()

        for i in list_ids:
            self.scope_stack.create_id(i, aux_type)

        if self.sym[TOKEN] != ';':
            raise Exception('Missing ; at line {}'.format(self.sym[LINE]))

        self.sym = self.get_next_token()
        self.list_of_var_declarations_l()


    @methodwrapper
    def list_of_ids(self):
        # id list_of_ids_l
        if self.sym[SYMBOL] == 'identifier':
            aux = [self.sym[TOKEN]]
            self.sym = self.get_next_token()
            return aux + self.list_of_ids_l()
        else:
            raise BailoutException(
                'Expected an identifier but got {} at line {}' \
                .format(self.sym[SYMBOL], self.sym[LINE])
                )


    @methodwrapper
    def list_of_ids_l(self):
        # , id list_of_ids_l | <empty>
        if self.sym[TOKEN] != ',':
            return [] # right-side production

        self.sym = self.get_next_token()
        if self.sym[SYMBOL] == 'identifier':
            aux = [self.sym[TOKEN]]
            self.sym = self.get_next_token()
            return aux + self.list_of_ids_l()


    @methodwrapper
    def type(self):
        # integer | real | boolean
        if self.sym[TOKEN] not in ['integer', 'real', 'boolean']:
            raise Exception(
                '{} is not a valid type at line {}.'.format(self.sym[TOKEN], self.sym[LINE])
                )
        self.sym = self.get_next_token()


    @methodwrapper
    def subprogram_declarations(self):
        # subprogram_declarations_l
        self.subprogram_declarations_l()


    @methodwrapper
    def subprogram_declarations_l(self):
        # subprogram_declaration; subprogram_declarations_l | <empty>
        try:
            self.subprogram_declaration()
        except BailoutException:
            # if there's no procedure keyword, bail out since it's optional
            return

        # TODO: should this throw an exception or just ignore since it's
        # technically optional? test carefully later
        if self.sym[TOKEN] != ';':
            raise Exception(
                'Expected ; at line {}, got {} instead.'.format(self.sym[LINE], self.sym[TOKEN])
                )

        self.sym = self.get_next_token()
        self.subprogram_declarations_l()


    @methodwrapper
    def subprogram_declaration(self):
        # procedure id arguments;
        # var_declarations
        # subprograms_declarations
        # compound_command
        if self.sym[TOKEN] != 'procedure':
            raise BailoutException(
                'Expected procedure at line {}, got {} instead' \
                .format(self.sym[LINE], self.sym[TOKEN])
                )

        self.sym = self.get_next_token()
        if self.sym[SYMBOL] == 'identifier':
            self.scope_stack.create_id(self.sym[TOKEN], 'proc')
            self.scope_stack.new_scope()
        else:
            raise Exception(
                'Expected procedure identifier at line {}, got {} instead' \
                .format(self.sym[LINE], self.sym[TOKEN])
                )

        self.sym = self.get_next_token()
        self.arguments()

        if self.sym[TOKEN] != ';':
            raise Exception(
                'Expected ;, got {} at line {} instead' \
                .format(self.sym[TOKEN], self.sym[LINE])
                )

        self.sym = self.get_next_token()
        self.var_declarations()
        self.subprogram_declarations()
        self.compound_command()

        self.scope_stack.end_scope()


    @methodwrapper
    def arguments(self):
        # (list_of_parameters) | <empty>
        if self.sym[TOKEN] != '(':
            return # no arguments

        self.sym = self.get_next_token()
        self.list_of_parameters()

        if self.sym[TOKEN] != ')':
            raise Exception(
                'Expected ) at line {}, got {} instead' \
                .format(self.sym[LINE], self.sym[TOKEN])
                )

        self.sym = self.get_next_token()


    @methodwrapper
    def list_of_parameters(self):
        # list_of_ids: type list_of_parameters_l
        aux_ids = self.list_of_ids()

        if self.sym[TOKEN] != ':':
            raise Exception('Missing : at line {}'.format(self.sym[LINE]))

        self.sym = self.get_next_token()
        aux_type = self.sym[TOKEN]
        self.type()

        for identifier in aux_ids:
            self.scope_stack.create_id(identifier, aux_type)

        self.list_of_parameters_l()


    @methodwrapper
    def list_of_parameters_l(self):
        # ; list_of_ids: type list_of_parameters_l | <empty>
        if self.sym[TOKEN] != ';':
            return [] # multiple parameters are optional, bail out if there's no ;

        self.sym = self.get_next_token()
        aux_ids = self.list_of_ids()

        if self.sym[TOKEN] != ':':
            raise Exception('Missing : at line {}'.format(self.sym[LINE]))

        self.sym = self.get_next_token()
        aux_type = self.sym[TOKEN]
        self.type()

        for identifier in aux_ids:
           self.scope_stack.create_id(identifier, aux_type)

        self.list_of_parameters_l()


    @methodwrapper
    def compound_command(self):
        # begin
        # optional_commands
        # end
        if self.sym[TOKEN] != 'begin':
            raise BailoutException(
                'Expected begin at line {}, got {} instead' \
                .format(self.sym[LINE], self.sym[TOKEN])
                )

        self.scope_stack.new_scope()

        self.sym = self.get_next_token()
        self.optional_commands()

        self.scope_stack.end_scope()

        if self.sym[TOKEN] != 'end':
            raise Exception(
                'Expected end at line {}, got {} instead' \
                .format(self.sym[LINE], self.sym[TOKEN])
                )

        self.sym = self.get_next_token()


    @methodwrapper
    def optional_commands(self):
        # list_of_commands | <empty>
        try:
            self.list_of_commands()
        except BailoutException:
            return


    @methodwrapper
    def list_of_commands(self):
        # command list_of_commands_l
        self.command()
        self.list_of_commands_l()


    @methodwrapper
    def list_of_commands_l(self):
        # ; command list of commands_l | <empty>
        if self.sym[TOKEN] != ';':
            return # didn't start with ';', bail out since this production is optional

        self.sym = self.get_next_token()
        self.command()
        self.list_of_commands_l()


    @methodwrapper
    def command(self):
        # variable := expression |
        # procedure_activation   |
        # compound_command       |
        # if_statement           |
        # while_statement
        try:
            # variable := expression
            self.variable()
            if self.sym[TOKEN] == ':=':
                self.type_stack.push(self.sym[TOKEN]) # push :=
                self.sym = self.get_next_token()
                self.expression()

                # Leaving attribution, evaluate to make sure types are compatible
                self.type_stack.evaluate()
                return
            raise BailoutException # got an identifier but not a :=
        except BailoutException:
            pass

        try:
            self.procedure_activation()
            return
        except BailoutException:
            pass

        try:
            self.compound_command()
            return
        except BailoutException:
            pass

        try:
            # if expression then command else_production
            if self.sym[TOKEN] != 'if':
                raise BailoutException

            self.sym = self.get_next_token()
            self.expression()

            if self.sym[TOKEN] != 'then':
                raise Exception('Missing then after if at line {}.'.format(self.sym[LINE]))

            self.sym = self.get_next_token()
            self.command()
            self.else_production()
            return
        except BailoutException:
            pass

        try:
            # while expression do command
            if self.sym[TOKEN] != 'while':
                raise BailoutException

            self.sym = self.get_next_token()
            self.expression()

            if self.sym[TOKEN] != 'do':
                raise Exception('Missing do after while at line {}.'.format(self.sym[LINE]))

            self.sym = self.get_next_token()
            self.command()
            return
        except BailoutException:
            raise Exception('Expected a command at line {}.'.format(self.sym[LINE]))


    @methodwrapper
    def else_production(self):
        # else command | <empty>
        if self.sym[TOKEN] != 'else':
            return # right-side production

        self.sym = self.get_next_token()
        self.command()


    @methodwrapper
    def variable(self):
        # id
        if self.sym[SYMBOL] != 'identifier':
            raise BailoutException

        # Push the type of this identifier (if it exists) into type control stack
        self.type_stack.push(
            self.scope_stack.search(self.sym[TOKEN])
            )

        self.sym = self.get_next_token()


    @methodwrapper
    def procedure_activation(self):
        # id procedure_activation_l
        if self.sym[SYMBOL] != 'identifier':
            raise BailoutException

        self.sym = self.get_next_token()
        self.procedure_activation_l()


    @methodwrapper
    def procedure_activation_l(self):
        # list_of_expressions | <empty>
        try:
            self.list_of_expressions()
        except BailoutException:
            return # right-side production


    @methodwrapper
    def list_of_expressions(self):
        # expression list_of_expressions_l
        self.expression()
        self.list_of_expressions_l()


    @methodwrapper
    def list_of_expressions_l(self):
        # ,expression list_of_expressions_l | <empty>
        if self.sym[TOKEN] == ',':
            self.expression()
            self.list_of_expressions_l()


    @methodwrapper
    def expression(self):
        # simple_expression | simple_expression relational_op simple_expression
        self.simple_expression()

        try:
            self.relational_op()
        except BailoutException:
            # Leaving simple_expression without matching right-hand production,
            # evaluate to make sure types are compatible
            self.type_stack.evaluate()
            return # did not match right side of production

        self.simple_expression() # TODO: catch and raise new exception here?

        # Leaving expression, evaluate to make sure types are compatible
        self.type_stack.evaluate()


    @methodwrapper
    def simple_expression(self):
        # term simple_expression_l |
        # signal term simple_expression_l

        # first production
        try:
            self.term()
        except BailoutException:
            # second production
            try:
                self.signal()
            except BailoutException:
                raise Exception(
                    'Expected signal at line {}, got {} instead.' \
                    .format(self.sym[LINE], self.sym[TOKEN])
                    )
            # second production cont.
            self.term()
            self.simple_expression_l()
        # first production cont.
        self.simple_expression_l()


    @methodwrapper
    def simple_expression_l(self):
        # additive_op term simple_expression_l | <empty>
        try:
            self.additive_op()
        except BailoutException:
            return # right-side production

        self.term()
        self.simple_expression_l()


    @methodwrapper
    def term(self):
        # factor term_l
        self.factor()
        self.term_l()


    @methodwrapper
    def term_l(self):
        # mult_op factor term_l | <empty>
        try:
            self.mult_op()
        except BailoutException:
            return # right-side production

        self.factor()
        self.term_l()


    @methodwrapper
    def factor(self):
        # id                      |
        # id(list_of_expressions) |
        # num_int                 |
        # num_real                |
        # true                    |
        # false                   |
        # (expression)            |
        # not factor
        if self.sym[SYMBOL] == 'identifier':
            # first production
            self.sym = self.get_next_token()
            if self.sym[TOKEN] == '(':
                # second production
                self.type_stack.push(self.sym[TOKEN]) # push (
                self.list_of_expressions()
                if self.sym[TOKEN] != ')':
                    raise Exception('Unclosed parenthesis at line {}.'.format(self.sym[LINE]))
                self.type_stack.push(self.sym[TOKEN]) # push )
                return
            return

        # third & fourth productions
        try:
            self.type_num()
        except BailoutException:
            # fifth & sixth productions
            if self.sym[TOKEN] in ['true', 'false']:
                self.type_stack.push('boolean')
                self.sym = self.get_next_token()
                return

            # seventh
            if self.sym[TOKEN] == '(':
                self.type_stack.push(self.sym[TOKEN]) # push (
                self.sym = self.get_next_token()
                self.expression()
                if self.sym[TOKEN] != ')':
                    raise Exception('Unclosed parenthesis at line {}.'.format(self.sym[LINE]))
                self.type_stack.push(self.sym[TOKEN]) # push )
                self.sym = self.get_next_token()
            else:
                # eight
                if self.sym[TOKEN] == 'not':
                    self.type_stack.push(self.sym[TOKEN]) # push `not`
                    self.sym = self.get_next_token()
                    self.factor()
                else:
                    raise Exception(
                        'Expected factor at line {}, got {} instead.' \
                        .format(self.sym[LINE], self.sym[TOKEN])
                        )


    @methodwrapper
    def type_num(self):
        # integer | real
        if self.sym[SYMBOL] not in ['integer', 'real']:
            raise BailoutException(
                '{} is not a valid type at line {}, expected a number.' \
                .format(self.sym[TOKEN], self.sym[LINE])
                )

        self.type_stack.push(self.sym[SYMBOL])
        self.sym = self.get_next_token()


    @methodwrapper
    def signal(self):
        # + | -
        if self.sym[TOKEN] not in ['+', '-']:
            raise BailoutException
        self.sym = self.get_next_token()


    @methodwrapper
    def relational_op(self):
        # = | < | > | <= | >= | <>
        if self.sym[TOKEN] not in ['=', '<', '>', '<=', '>=', '<>']:
            raise BailoutException

        self.type_stack.push(self.sym[TOKEN])
        self.sym = self.get_next_token()


    @methodwrapper
    def additive_op(self):
        # + | - | or
        if self.sym[TOKEN] not in ['+', '-', 'or']:
            raise BailoutException

        self.type_stack.push(self.sym[TOKEN])
        self.sym = self.get_next_token()


    @methodwrapper
    def mult_op(self):
        # * | / | and
        if self.sym[TOKEN] not in ['*', '/', 'and']:
            raise BailoutException

        self.type_stack.push(self.sym[TOKEN])
        self.sym = self.get_next_token()


#
# Application entry point
#
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 pascalanalyzer.py <token csv file>')
        quit()

    analyzer = Analyzer()
    analyzer.parse_tokens_into_list(sys.argv[1])
    analyzer.start()
