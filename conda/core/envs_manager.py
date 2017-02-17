# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from logging import getLogger
from os import getcwd
from os.path import isdir, join

from .. import CondaError
from .._vendor.auxlib.path import expand
from ..base.constants import ENVS_DIR_MAGIC_FILE, ROOT_ENV_NAME
from ..base.context import context
from ..common.compat import text_type
from ..exceptions import CondaEnvironmentNotFoundError, CondaValueError
from ..gateways.disk.create import create_envs_directory
from ..gateways.disk.test import file_path_is_writable

try:
    from cytoolz.itertoolz import concatv
except ImportError:
    from .._vendor.toolz.itertoolz import concatv

log = getLogger(__name__)


class EnvsDirectory(object):
    _is_writable = None

    def __init__(self, envs_dir):
        self.envs_dir = envs_dir
        self.catalog_file = join(envs_dir, ENVS_DIR_MAGIC_FILE)

    @property
    def is_writable(self):
        # lazy and cached
        # This method takes the action of creating an empty package cache if it does not exist.
        #   Logic elsewhere, both in conda and in code that depends on conda, seems to make that
        #   assumption.
        if self._is_writable is None:
            if isdir(self.envs_dir):
                self._is_writable = file_path_is_writable(self.catalog_file)
            else:
                log.debug("env directory '%s' does not exist", self.envs_dir)
                self._is_writable = create_envs_directory(self.envs_dir)
        return self._is_writable

    @classmethod
    def first_writable(cls, envs_dirs=None):
        return cls.all_writable(envs_dirs)[0]

    @classmethod
    def all_writable(cls, envs_dirs=None):
        if envs_dirs is None:
            envs_dirs = context.envs_dirs
        writable_caches = tuple(filter(lambda c: c.is_writable,
                                       (cls(ed) for ed in envs_dirs)))
        if not writable_caches:
            raise CondaError("No writable envs directories found in\n"
                             "%s" % text_type(envs_dirs))
        return writable_caches

    @classmethod
    def locate_prefix_by_name(cls, name, envs_dirs=None):
        """Find the location of a prefix given a conda env name."""
        if name == ROOT_ENV_NAME:
            return context.root_prefix

        for envs_dir in concatv(envs_dirs or context.envs_dirs, (getcwd(),)):
            prefix = join(envs_dir, name)
            if isdir(prefix):
                return prefix

        raise CondaEnvironmentNotFoundError(name)


def get_prefix(ctx, args, search=True):
    """Get the prefix to operate in

    Args:
        ctx: the context of conda
        args: the argparse args from the command line
        search: whether search for prefix

    Returns: the prefix
    Raises: CondaEnvironmentNotFoundError if the prefix is invalid
    """
    if getattr(args, 'name', None):
        if '/' in args.name:
            raise CondaValueError("'/' not allowed in environment name: %s" %
                                  args.name, getattr(args, 'json', False))
        if args.name == ROOT_ENV_NAME:
            return ctx.root_dir
        if search:
            return EnvsDirectory.locate_prefix_by_name(args.name)
        else:
            # need first writable envs_dir
            envs_dir = EnvsDirectory.first_writable()
            return join(envs_dir, args.name)
    elif getattr(args, 'prefix', None):
        return expand(args.prefix)
    else:
        return ctx.default_prefix
