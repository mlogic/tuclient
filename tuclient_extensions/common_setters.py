"""Common setters"""
# Copyright (c) 2017-2019 Yan Li, TuneUp.ai <yanli@tuneup.ai>.
# All rights reserved.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License version 2.1 as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see
# https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html
from __future__ import absolute_import, division, print_function, unicode_literals

__author__ = 'Yan Li'
__copyright__ = 'Copyright (c) 2017-2019 Yan Li, TuneUp.ai <yanli@tuneup.ai>. All rights reserved.'
__license__ = 'LGPLv2.1'
__docformat__ = 'reStructuredText'

import functools
import importlib
from .setter_misc import *
import re
from tuclient import *
# typing.NamedTuple is better than collections.namedtuple because the former allows
# setting the types of fields.
from typing import Callable, Dict, List, NamedTuple, Set


# We can't use the following better format because we need to support Python 2
#    name: str
#    calc_param_value_func: Callable
# calc_param_value_func is a callable for calculating the actual parameter value
# from the float value between -1 and 1 that we receive from the engine.
ParameterInfo = NamedTuple('ParameterInfo', [('full_name', str),
                                             ('short_name', str),
                                             ('config_file', str),
                                             ('calc_param_value_func', Callable),
                                             ('post_set_func_index', int)])
# The mapping from an action's index to its post_set function's index
ActionIndexToPostSetFuncIndexMap = Dict[int, int]


class Setter(SetterExtensionBase):
    """Common setters"""

    @staticmethod
    def _find_config_file_abspath(config_file):
        # Get the absolute pathname for the config file. We search the
        # etc_dir/SNAP_DATA first. This makes it possible for the user
        # to carry a modified version there (config files in sitelib/tuclient are
        # immutable in the snap package).
        etc_dir = os.environ.get('SNAP_DATA', '/etc/tuclient')
        for config_home in (etc_dir, os.path.dirname(os.path.abspath(__file__))):
            config_file_abs = os.path.join(config_home, config_file)
            if os.path.exists(config_file_abs):
                return config_file_abs
        raise RuntimeError('Cannot find common setters config file ' + config_file)

    def __init__(self, logger, host, config=None):
        """Create a Common Setter instance

        :param logger: logger
        :param config: a ConfigBase instance for accessing configuration options
        """
        super(Setter, self).__init__(logger, host, config, 'common_setters')
        for config_file in config.get_config()['common_setters_config_files'].split(', '):
            if not os.path.isabs(config_file):
                config_file = self._find_config_file_abspath(config_file)
            logger.info(f'Loading common setters config file {config_file} '
                        '(if this is not the correct file, make sure you use the correct absolute path '
                        'for common_setters_config_files.')
            config = ConfigFile(logger, 'client', host, config_file, config.get_config())

        # Load settings for the common setters from config. Parameters are ground by their
        # intervals.
        parameter_names = config.get_config()['common_setters_params'].split(', ')
        parameter_names.sort()
        # Parameters grouped by interval
        self._parameters = dict()                      # type: Dict[int, List[ParameterInfo]]
        # A map from config file names to config file data
        self._config_file_data_map = dict()            # type: Dict[str, str]
        # Set of config file names grouped by interval
        self._config_file_sets = dict()                # type: Dict[int, Set[str]]
        # A list of all post_set_funcs' callable objects. A parameter stores an index to refer
        # to tis post_set_func inside this list. By doing this, we are able to call each
        # post_set_func only once even when more than one parameter uses the same
        # post_set_func.
        self._post_set_funcs = []                      # type: List[Callable]
        func_name_to_post_set_func_index_map = dict()  # type: Dict[str, int]
        # A map from parameter short names to values. Filled by _config_file_set_func()
        # each time new values are received. This map is used to calculate some
        # dependent parameter values, such as values that are calculated from other
        # parameter values. This map is used by _commit_config_file_changes.
        self._parameter_value_map = dict()             # type: Dict[str, Any]

        for name in parameter_names:
            interval = int(config.get_config()[name + '_interval'])
            if interval not in self._parameters:
                self._parameters[interval] = []
            if interval not in self._config_file_sets:
                self._config_file_sets[interval] = set()
            # Does this parameter require a config file?
            if name + '_config_file' in config.get_config():
                config_file = config.get_config()[name + '_config_file']
                self._config_file_sets[interval].add(config_file)
                if config_file not in self._config_file_data_map:
                    # Read the file data
                    with open(config_file) as f:
                        self._config_file_data_map[config_file] = f.read()
                # Make sure the regex is compilable
                regex = config.get_config()[name + '_config_line_regex']
                regex_obj = re.compile(regex, flags=re.MULTILINE)
                # Read the new line data
                new_line = config.get_config()[name + '_config_new_line']
                # Put the new_line into the config file
                self._config_file_data_map[config_file] = re.sub(regex_obj, new_line,
                                                                 self._config_file_data_map[config_file])

                if name + '_post_set_func' not in config.get_config():
                    # This parameter has no post_set_func
                    post_set_func_index = -1
                else:
                    post_set_func_name = config.get_config()[name + '_post_set_func']
                    if post_set_func_name not in func_name_to_post_set_func_index_map:
                        # load this func
                        name_sections = post_set_func_name.split('.')
                        module_name = '.'.join(name_sections[:-1])
                        func_name = name_sections[-1]
                        module = importlib.import_module(module_name)
                        func = getattr(module, func_name)
                        self._post_set_funcs.append(func)
                        func_name_to_post_set_func_index_map[post_set_func_name] = len(self._post_set_funcs) - 1

                    post_set_func_index = func_name_to_post_set_func_index_map[post_set_func_name]

                cand_val_str = config.get_config()[name + '_candidate_values']
                m = re.match(r"\[(\d+)[, ]*(\d+)\]", cand_val_str)
                if m is not None:
                    calc_param_value_func = functools.partial(param_value_from_range, float(m.group(1)),
                                                              float(m.group(2)))
                else:
                    raise ValueError('Cannot parse candidate values ' + cand_val_str)

                param_full_name = host + '/' + name
                logger.info('Loaded parameter information: name {param_full_name}, set interval {interval}, '
                            'config_file {config_file}, candidate values {cand_val_str}'.format(
                                param_full_name=param_full_name, interval=interval, config_file=config_file,
                                cand_val_str=cand_val_str))
                self._parameters[interval].append(ParameterInfo(param_full_name, name, config_file, calc_param_value_func,
                                                                post_set_func_index))
            elif name + '_sysctl' in config.get_config():
                raise NotImplementedError('Common setter {name} requires sysctl interface, which is not implemented '
                                          'yet.'.format(name=name))
            else:
                raise ValueError("Common setter {name} doesn't have correct parameter information.")

        # Prefix each parameter by our hostname before finishing
        self._parameter_names = [host+'/'+x for x in parameter_names]

    def _commit_config_file_changes(self, interval):
        for config_file in self._config_file_sets[interval]:
            config_file_data = self._config_file_data_map[config_file]
            for param_name, param_value in self._parameter_value_map.items():
                config_file_data = config_file_data.replace('$' + param_name + '$',
                                                            param_value)
            with open(config_file, 'w') as f:
                f.write(config_file_data)

    @overrides(SetterExtensionBase)
    def start(self):
        pass

    @overrides(SetterExtensionBase)
    def action(self, interval, actions):
        # type: (int, List[float]) -> None
        """Perform actions

        For test cases, if all parameters have the same interval, we can set interval
        to -1 and the actions will be applied to all parameters. The behavior is
        undefined if the parameters have more than one interval.
        :param interval: intervals for this batch of actions
        :param actions: a list of actions to perform"""
        if interval == -1:
            # TODO: This shouldn't be needed when TUE-224 is finished.
            assert len(self._parameters) == 1
            interval = list(self._parameters.keys())[0]
        assert len(self._parameters[interval]) == len(actions)

        # We use a set to track the index of the post_set_func we need to call,
        # so that we only call each post_set_func once at most.
        post_set_funcs_to_call = set()

        # We do not clear out old parameter values from self._parameter_value_map
        # each time we receive a new set of actions, because we need to keep
        # values that are only set in other intervals.
        for param_info, action_value in zip(self._parameters[interval], actions):
            self._parameter_value_map[param_info.short_name] = param_info.calc_param_value_func(action_value)
            if param_info.post_set_func_index >= 0:
                post_set_funcs_to_call.add(param_info.post_set_func_index)
        self._commit_config_file_changes(interval)

        # Call all unique post_set functions
        for i in post_set_funcs_to_call:
            self._post_set_funcs[i]()

    @property
    @overrides(SetterExtensionBase)
    def parameter_names(self):
        # type: () -> List[str]
        """Return the list of all parameters"""
        return self._parameter_names

    def stop(self):
        pass
