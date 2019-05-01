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
from typing import Callable, Dict, List, NamedTuple


# We can't use the following better format because we need to support Python 2
#    name: str
#    set_func: Callable
# set_func is a callable for setting a parameter according to a float value between -1 and 1.
ParameterInfo = NamedTuple('ParameterInfo', [('name', str), ('set_func', Callable), ('post_set_func_index', int)])
ConfigFileChangeAction = NamedTuple('ConfigFileChangeAction', [('line_regex_obj', object), ('new_line', str),
                                                               ('param_value', str)])
# The mapping from an action's index to its post_set function's index
ActionIndexToPostSetFuncIndexMap = Dict[int, int]


class Setter(SetterExtensionBase):
    """Common setters"""

    def __init__(self, logger, host, config=None):
        """Create a Common Setter instance

        :param logger: logger
        :param config: a ConfigBase instance for accessing configuration options
        """
        super(Setter, self).__init__(logger, host, config)
        for config_file in config.get_config()['common_setters_config_files'].split(', '):
            if not os.path.isabs(config_file):
                # Get the absolute pathname for the config file
                config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../' + config_file)
            config = ConfigFile(logger, 'client', host, config_file, config.get_config())

        # Used by `_config_file_set_func()`
        self._config_file_change_queue = dict()  # type: Dict[str, List[ConfigFileChangeAction]]

        # Load settings for the common setters from config. Parameters are ground by their
        # intervals.
        parameter_names = config.get_config()['common_setters_params'].split(', ')
        parameter_names.sort()
        # Parameters grouped by interval
        self._parameters = dict()      # type: Dict[int, List[ParameterInfo]]
        # A list of all post_set_funcs' callable objects. A parameter stores an index to refer
        # to tis post_set_func inside this list. By doing this, we are able to call each
        # post_set_func only once even when more than one parameter uses the same
        # post_set_func.
        self._post_set_funcs = []      # type: List[Callable]
        func_name_to_post_set_func_index_map = dict()  # type: Dict[str, int]

        for name in parameter_names:
            interval = int(config.get_config()[name + '_interval'])
            if interval not in self._parameters:
                self._parameters[interval] = []
            # Does this parameter require a config file?
            if name + '_config_file' in config.get_config():
                config_file = config.get_config()[name + '_config_file']
                # Test if the file is readable
                with open(config_file) as f:
                    f.read()
                # Make sure the regex is compilable
                regex = config.get_config()[name + '_config_line_regex']
                regex_obj = re.compile(regex, flags=re.MULTILINE)

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

                self._parameters[interval].append(ParameterInfo(host+'/'+name, functools.partial(
                    self._config_file_set_func, calc_param_value_func, config_file, regex_obj,
                    config.get_config()[name + '_config_new_line']
                ), post_set_func_index))
            elif name + '_sysctl' in config.get_config():
                raise NotImplementedError('Common setter {name} requires sysctl interface, which is not implemented yet.')
            else:
                raise ValueError("Common setter {name} doesn't have correct parameter information.")

        # Prefix each parameter by our hostname before finishing
        self._parameter_names = [host+'/'+x for x in parameter_names]

    def _config_file_set_func(self, param_value_func, config_file, line_regex_obj, new_line, action_value):
        # type: (Callable, str, object, str, float) -> None
        """Set the parameter in a config file

        This function only puts the change into a queue, because we need to group the
        change to the same configuration file to reduce overhead.

        :param param_value_func: a callable for calculating the parameter value from action value
        :param config_file: name of the config file
        :param line_regex_obj: regular expression Pattern object for matching the line to be changed
        :param new_line: new line to be put into the config file
        :param action_value: new value for the parameter"""
        if config_file not in self._config_file_change_queue:
            self._config_file_change_queue[config_file] = []
        self._config_file_change_queue[config_file].append(ConfigFileChangeAction(line_regex_obj,
                                                                                  new_line,
                                                                                  param_value_func(action_value)))

    def _commit_config_file_changes(self):
        for config_file, changes in self._config_file_change_queue.items():
            with open(config_file) as f:
                file_data = f.read()
                for change in changes:
                    # Fill new_line with the actual parameter
                    new_line = change.new_line.replace('$value$', change.param_value)
                    # Put the new_line into the config file
                    file_data = re.sub(change.line_regex_obj, new_line, file_data)

            with open(config_file, 'w') as f:
                f.write(file_data)

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
        assert len(self._config_file_change_queue) == 0
        # We use a set to track the index of the post_set_func we need to call,
        # so that we only call each post_set_func once at most.
        post_set_funcs_to_call = set()
        for param_info, action_value in zip(self._parameters[interval], actions):
            param_info.set_func(action_value)
            if param_info.post_set_func_index >= 0:
                post_set_funcs_to_call.add(param_info.post_set_func_index)
        self._commit_config_file_changes()
        # Clear the queue after committing changes
        self._config_file_change_queue = dict()
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
        if self._collectd is not None:
            self._collectd.stop()
