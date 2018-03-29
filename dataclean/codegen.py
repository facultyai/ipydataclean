from __future__ import division

import builtins
import re
from collections import namedtuple

try:
    from inspect import signature
except ImportError:  # Python 2
    from funcsigs import signature

from inspect import getsourcelines, ismethod, isclass, isfunction, ismodule
from textwrap import dedent

def indent(text, prefix):
    """Adds 'prefix' to the beginning of lines in 'text'."""

    def prefixed_lines():
        for line in text.splitlines(True):
            yield (prefix + line if line.strip() else line)
    return ''.join(prefixed_lines())

ClosureVars = namedtuple('ClosureVars', 'nonlocals globals builtins unbound')

def getclosurevars(func):
    """
    Get the mapping of free variables to their current values.

    Returns a named tuple of dicts mapping the current nonlocal, global
    and builtin references as seen by the body of the function. A final
    set of unbound names that could not be resolved is also provided.
    """
    # From the Python3 inspect module, vendored here for Python2 compatibility

    if ismethod(func):
        func = func.__func__

    if not isfunction(func):
        raise TypeError("'{!r}' is not a Python function".format(func))

    code = func.__code__
    # Nonlocal references are named in co_freevars and resolved
    # by looking them up in __closure__ by positional index
    if func.__closure__ is None:
        nonlocal_vars = {}
    else:
        nonlocal_vars = {
            var : cell.cell_contents
            for var, cell in zip(code.co_freevars, func.__closure__)
       }

    # Global and builtin references are named in co_names and resolved
    # by looking them up in __globals__ or __builtins__
    global_ns = func.__globals__
    builtin_ns = global_ns.get("__builtins__", builtins.__dict__)
    if ismodule(builtin_ns):
        builtin_ns = builtin_ns.__dict__
    global_vars = {}
    builtin_vars = {}
    unbound_names = set()
    for name in code.co_names:
        if name in ("None", "True", "False"):
            # Because these used to be builtins instead of keywords, they
            # may still show up as name references. We ignore them.
            continue
        try:
            global_vars[name] = global_ns[name]
        except KeyError:
            try:
                builtin_vars[name] = builtin_ns[name]
            except KeyError:
                unbound_names.add(name)

    return ClosureVars(nonlocal_vars, global_vars,
                       builtin_vars, unbound_names)


CODE_INDENT = '    '

EXPORT_FUNCTION_SIGNATURE = 'def exported_pipeline(df):\n'

STEP_CODE_PREFIX = indent('\ndataframe = df.copy()\n\n', CODE_INDENT)

STEP_CODE_SUFFIX = indent('return dataframe', CODE_INDENT)


def replace(string, substitutions):
    """Replaces all substitutions in one pass to avoid conflicts"""

    substrings = sorted(substitutions, key=len, reverse=True)
    regex = re.compile('|'.join(map(re.escape, substrings)))
    return regex.sub(lambda match: substitutions[match.group(0)], string)


def render_code(function, **params):
    """
    Generate the code of a function with text replacement of arguments.

    Renders the code of a python function applying textual substitutions of
    input arguments with their repr/value.

    Parameters
    ----------
    function : function
        Python function to render.

        This function should have any code to be output within lines [2:-1] of
        the code as written. For intended usage this means that the signature,
        the one line docstring, and the return statement are ommitted when
        rendering. One should also take care the function does not use text
        which may clash with substitutions made when calling this function.

    Returns
    -------
    str
        The text of the input function with arguments replaced, indented once.
    """

    substitutions = {}
    comment = ''

    if 'code_comment' in params:
        for line in params['code_comment'].split('\n'):
            comment += '# ' + line + '\n'

    code = getsourcelines(function)

    # [2:-1] slice removes signature, docstring and return statement
    code = dedent("".join(code[0][2:-1]))

    for arg_name in signature(function).parameters.keys():
        if arg_name in params:
            # repr of a type, e.g. repr(int) doesn't produce valid python
            if isinstance(params[arg_name], type):
                substitutions[arg_name] = params[arg_name].__name__
            else:
                substitutions[arg_name] = repr(params[arg_name])

    if substitutions:
        code = replace(code, substitutions)

    return indent(comment + code, CODE_INDENT)


def get_module_dependencies(function):
    """
    Generate the import statements required for a function

    Parameters
    ----------
    function : function
        Python function for which to generate import statements.

    Returns
    -------
    import list: list of str
        The import statements required for a function, indented once.

        For any closure variables not themselves a module or imported from one,
        the generated statement will attempt to bind the repr() of the variable
        to the variable name.
    """

    import_list = []
    import_statement = None

    for name, imported in getclosurevars(function).globals.items():

        if hasattr(imported, "__module__"):
            import_statement = 'from {0} import {1}'.format(
                imported.__module__,
                imported.__name__
            )

            if (imported.__name__ != name):
                import_statement += ' as {0}'.format(name)

            import_statement += '\n'

        elif ismodule(imported):
            import_statement = 'import {0}'.format(imported.__name__)

            if (imported.__name__ != name):
                import_statement += ' as {0}'.format(name)

            import_statement += '\n'

        else:
            import_statement = '{0} = {1}\n'.format(name, repr(imported))

        if import_statement:
            import_list.append(indent(import_statement, CODE_INDENT))

    return import_list
