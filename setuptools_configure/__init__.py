import collections
import functools
import itertools
import os
import re
import shutil
import subprocess
import sys
from distutils import log
from distutils.cmd import Command
from distutils.errors import (
    DistutilsError, DistutilsFileError, DistutilsSetupError)
from distutils.text_file import TextFile

import argparse
import setuptools

identifier_pattern = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

delimiter = '@'
substitution_pattern = re.compile(
    r"""
    {delimiter}
    (?:
    (?P<escaped>{delimiter})   |  # Escape sequence of two delimiters
    (?P<named>{id}){delimiter}    # delimiter, identifier and delimiter
    )"""
    .format(id=identifier_pattern.pattern,
            delimiter=delimiter),
    re.VERBOSE
)

config_pattern = re.compile(
    r"(?P<name>{}) \s* = \s* (?P<value>.*)"
    .format(identifier_pattern.pattern),
    re.VERBOSE
)


class ConfigureError(Exception):
    pass


class SubstitutionError(Exception):
    pass


def format_program_list(programs):
    if len(programs) > 1:
        return '{} or {}'.format(', '.join(programs[:-1]), programs[-1])
    else:
        return programs[0]


def do_find_program(programs, default=None, path=None, include_defaults=True):
    if isinstance(programs, str):
        programs = [programs]
    log.info("Looking for %s", format_program_list(programs))
    if path is None:
        path = os.environ.get("PATH", os.defpath)
    if include_defaults:
        path = path.split(os.pathsep)
        defaults = ['/bin', '/sbin', '/usr/local/bin', '/usr/local/sbin',
                    '/usr/bin', '/usr/sbin']
        for directory in defaults:
            if directory not in path:
                path.append(directory)
        path = os.pathsep.join(path)
    for program in programs:
        exec_path = shutil.which(program, path=path)
        if exec_path is not None:
            return exec_path
    return default


@functools.wraps(do_find_program)
def find_program(programs, default=None, path=None, include_defaults=True):
    def find_program_wrapper(substitutions):
        nonlocal programs, default, path
        programs = substitute(programs, substitutions)
        default = substitute(default, substitutions)
        path = substitute(path, substitutions)
        return do_find_program(programs, default=default, path=path,
                               include_defaults=include_defaults)
    return find_program_wrapper


def do_require_program(programs, default=None, path=None,
                       include_defaults=True):
    if isinstance(programs, str):
        programs = [programs]
    exec_path = do_find_program(programs, path=path,
                                include_defaults=include_defaults)
    if exec_path is not None:
        return exec_path
    if (default is not None and
            os.path.exists(default) and
            os.access(default, os.R_OK | os.X_OK) and
            not os.path.isdir(default)):
        return default
    raise ConfigureError("Could not find required program {}"
                         .format(format_program_list(programs)))


@functools.wraps(do_require_program)
def require_program(programs, default=None, path=None, include_defaults=True):
    def require_program_wrapper(substitutions):
        nonlocal programs, default, path
        programs = substitute(programs, substitutions)
        default = substitute(default, substitutions)
        path = substitute(path, substitutions)
        return do_require_program(programs, default=default, path=path,
                                  include_defaults=include_defaults)
    return require_program_wrapper


def do_execute_process(args):
    log.info("Executing %s", ' '.join(args))
    process = subprocess.Popen(args,
                               stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               universal_newlines=True,
                               close_fds=True,
                               restore_signals=True)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise ConfigureError("error executing {}:\n{}"
                             .format(' '.join(args), stderr))
    return stdout.strip()


@functools.wraps(do_execute_process)
def execute_process(args):
    def execute_process_wrapper(substitutions):
        nonlocal args
        args = substitute(args, substitutions)
        return do_execute_process(args)
    return execute_process_wrapper


def _expand(substitutions, name, referenced):
    if name not in substitutions:
        raise SubstitutionError("Can't expand unknown variable {}".format(name))
    val = _substitute(substitutions[name], substitutions, referenced)
    # cache the result
    substitutions[name] = val
    return val


def _replace(substitutions, referenced, match):
    # Ensure local copy
    referenced = list(referenced)
    name = match.group('named')
    if name is not None:
        if name in referenced:
            referenced.append(name)
            raise SubstitutionError("Cycle detected: {}"
                                    .format('->'.join(referenced)))
        referenced.append(name)
        return _expand(substitutions, name, referenced)
    if match.group('escaped') is not None:
        return delimiter
    raise AssertionError('Expression must match either named or escaped')


def _substitute(value, substitutions, referenced):
    if callable(value):
        return value(substitutions)
    if delimiter not in value:
        return value
    return substitution_pattern.sub(
        functools.partial(_replace, substitutions, referenced), value)


def substitute(value, substitutions):
    if isinstance(value, str) or callable(value):
        return _substitute(value, substitutions, [])
    if isinstance(value, collections.Mapping):
        return type(value)((substitute(k, substitutions),
                            substitute(v, substitutions))
                           for k, v in value.items())
    if isinstance(value, collections.Sequence):
        return type(value)(substitute(v, substitutions) for v in value)
    return value


def flatten(substitutions):
    for key, value in substitutions.items():
        substitutions[key] = substitute(value, substitutions)


class configure(Command):
    description = "Configure .in files by substituting @-variables"
    user_options = []

    # noinspection PyAttributeOutsideInit
    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        substitutions = getattr(self.distribution, 'substitutions', {})
        configure_files = getattr(self.distribution, 'configure_files', [])
        constants_module = getattr(self.distribution, 'constants_module', None)

        for src_name in configure_files:
            log.info("Configuring {}".format(src_name))
            dst_name = src_name[:-3]
            try:
                with open(src_name, 'r') as src, open(dst_name, 'w') as dst:
                    for lineno, line in enumerate(src):
                        try:
                            value = substitute(line, substitutions)
                        except SubstitutionError as e:
                            msg = "{}, line {}: {} ".format(src_name, lineno, e)
                            raise DistutilsError(msg) from e
                        dst.write(value)
            except OSError as e:
                raise DistutilsFileError("{}: {}"
                                         .format(e.strerror, e.filename)) from e
        if constants_module:
            package, ignore, module_name = constants_module.rpartition('.')
            for prefix in prefixes(package):
                directory = self.distribution.package_dir.get(prefix)
                if directory is not None:
                    break
            if directory is None:
                directory = os.curdir
            dst_name = os.path.join(directory, package.replace('.', os.pathsep),
                                    module_name) + '.py'
            log.info("Generating constants module %s at %s",
                     constants_module, dst_name)
            try:
                with open(dst_name, 'w') as dst:
                    dst.writelines(itertools.starmap(
                        '{} = {!r}\n'.format, sorted(substitutions.items())))
            except OSError as e:
                raise DistutilsFileError("{}: {}"
                                         .format(e.strerror, e.filename)) from e


def prefixes(package):
    yield package
    prefix = package
    while prefix != '':
        prefix, sep, suffix = package.rpartition('.')
        yield prefix


def validate_configure_files(dist, attr, value):
    for file in value:
        if not file.endswith(".in") or file == '.in':
            raise DistutilsSetupError("Configure files must end with .in: {}"
                                      .format(file))


def validate_substitutions(dist, attr, value):
    for subst_var, subst_value in value.items():
        if not identifier_pattern.fullmatch(subst_var):
            raise DistutilsSetupError("{} is not a valid substitution variable "
                                      "name".format(subst_var))


def validate_constants_module(dist, attr, value):
    if all(map(str.isidentifier, value.split('.'))) is None:
        raise DistutilsSetupError("{} is not a valid module name    ".format(value))


def parse_cache(filename):
    substitutions = {}
    try:
        with open(filename, 'r') as cache:
            text_file = TextFile(filename, cache, strip_comments=True,
                                 lstrip_ws=True, rstrip_ws=True,
                                 skip_blanks=True, join_lines=True)
            line = text_file.readline()
            while line is not None:
                match = config_pattern.fullmatch(line)
                if not match:
                    raise ConfigureError("{}, {}".format(filename,
                                                         text_file.gen_error(
                                                             "Invalid configure cache")))
                substitutions[match.group("name")] = match.group("value")
                line = text_file.readline()
    except FileNotFoundError:
        pass
    return substitutions


def write_cache(filename, substitutions):
    log.info("Writing config cache to %s", filename)
    with open(filename, 'w') as cache:
        cache.writelines(itertools.starmap("{}={}\n".format,
                                           sorted(substitutions.items())))


def parse_commandline_substitutions(args):
    script_args = []
    substitutions = {}
    start = args.index('configure') + 1
    script_args.extend(args[:start])
    for index, arg in enumerate(args[start:]):
        match = config_pattern.fullmatch(arg)
        if match:
            substitutions[match.group('name')] = match.group('value')
        elif not arg.startswith('-'):
            script_args.extend(args[index:])
            break
        else:
            script_args.append(arg)
    return script_args, substitutions


def setup(**attrs):
    script_name = attrs.pop('scripts_name', os.path.basename(sys.argv[0]))
    script_args = attrs.pop('scripts_args', sys.argv[1:])
    # Some distutils arguments should be recognized
    parser = argparse.ArgumentParser(prog=script_name, add_help=False)
    parser.add_argument('-h', '--help', action='store_true')
    parser.add_argument('--help-commands', action='store_true')
    parser.add_argument('-v', '--verbose', dest='verbosity',
                        action='count', default=1)
    parser.add_argument('-q', '--quiet', dest='verbosity',
                        action='store_const', const=0)
    known_args, ignore = parser.parse_known_args(script_args)
    log.set_verbosity(known_args.verbosity)
    if not (known_args.help or known_args.help_commands):
        substitutions = attrs.pop('substitutions', {})
        substitutions.update({
            # Autoconf-style metadata
            'PACKAGE_NAME':         attrs.get('name'),
            'PACKAGE_VERSION':      attrs.get('version'),
            'PACKAGE_AUTHOR':       attrs.get('author'),
            'PACKAGE_AUTHOR_EMAIL': attrs.get('author_email'),
            'PACKAGE_LICENSE':      attrs.get('license'),
            'PACKAGE_URL':          attrs.get('url'),
        })
        cache_filename = 'config.cache'
        if 'configure' in script_args:
            script_args, cli_substitutions = parse_commandline_substitutions(script_args)
            substitutions.update(cli_substitutions)
            flatten(substitutions)
            write_cache(cache_filename, substitutions)
        else:
            substitutions.update(parse_cache(cache_filename))

        for name, value in attrs.items():
            attrs[name] = substitute(value, substitutions)
        attrs['substitutions'] = substitutions
    return setuptools.setup(script_name=script_name, script_args=script_args,
                            **attrs)
