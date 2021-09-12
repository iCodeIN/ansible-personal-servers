# https://github.com/stoned/ansible-jsonnet-lookup
# (c) 2018, Stoned Elipot <stoned.elipot@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import (absolute_import, division, print_function)
from typing import Any, Dict, Tuple

from ansible.utils.color import hostcolor
__metaclass__ = type

DOCUMENTATION = """
    lookup: jsonnet
    author: Stoned Elipot <stoned.elipot@gmail.com>
    version_added: "2.7"
    short_description: retrieve contents of file after templating with Jsonnet
    description:
      - The jsonnet lookup returns templated Jsonnet documents. The
        documents are looked up like regular template files.
      - Any Jinja2 expression can be evaluated from the Jsonnet document,
        hence any Ansible variable's value is available, with the provided
        "native" function ```ansible_expr```. It takes one argument,
        a Jinja2 expression, as a string, and returns its evaluation.
        The Jinja2 expression can be a bare string.
    requirements:
      - jsonnet (python library https://pypi.org/project/jsonnet/)
    options:
      _terms:
        description:
          - List of files to process.
      ext_vars:
        description:
          - A mapping for key and string values defining so called
            "external variables" for the Jsonnet processing.
          -  cf. https://jsonnet.org/learning/tutorial.html
      "ext_codes, tla_vars, tla_codes, max_trace, max_stack, gc_min_objects, gc_growth_trigger":
         description:
           - Other keyword arguments supported by Jsonnet Python API.
           - cf. https://jsonnet.org/ref/bindings.html
"""

EXAMPLES = """
- name: show templating results
  debug: msg="{{ lookup('jsonnet', 'some_template.jsonnet') }}"

- name: set facts from json produced by jsonnet
  set_fact: myvar="{{ lookup('jsonnet', 'some_template.jsonnet') }}"

- name: set facts from json produced by jsonnet with external variables provided
  set_fact: myvar="{{ lookup('jsonnet', 'some_template.jsonnet', ext_vars=a_mapping) }}"
  vars:
    a_mapping:
      var1: value1
      var2: value2

# Examples of Jinja2 expression evaluation in Jsonnet document:
#  std.native("ansible_expr")("{{ 1 + 1 }}")
#  std.native("ansible_expr")("ansible_all_ipv4_addresses")
"""

RETURN = """
_raw:
   description: Jsonnet document after processing
"""

from ansible import constants as C
from ansible.config.manager import ensure_type
from ansible.errors import AnsibleError, AnsibleFileNotFound, AnsibleAction, AnsibleActionFail
from ansible.module_utils._text import to_bytes, to_text, to_native
from ansible.module_utils.parsing.convert_bool import boolean
from ansible.module_utils.six import string_types
from ansible.plugins.action import ActionBase
from ansible.template import generate_ansible_template_vars, AnsibleEnvironment
from ansible.utils.display import Display

import json
import yaml
import os
import shutil
import stat
import tempfile

try:
    import _jsonnet
    HAS_JSONNET = True
except ImportError:
    HAS_JSONNET = False

display = Display()

"""
Args:
    src: source path in templates
    dest: dest on remote host
    mode: unix-permissions
"""

JSON_FORMAT = 'json'
YAML_FORMAT = 'yaml'
supported_formats = [JSON_FORMAT, YAML_FORMAT]


class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):
        ''' handler for package operations '''

        #
        # Preamble
        #

        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        #
        # Options type validation
        #

        self.__validate_options()

        #
        # assign to local vars for ease of use
        #

        source = self._task.args.get('src', None)
        dest = self._task.args.get('dest', None)
        format = self._task.args.get('format', JSON_FORMAT)

        #
        # actual main module code
        #

        try:
            #
            # process args
            #

            source, dest = self.__process_args(source, dest)
            mode = self._task.args.get('mode', None)
            if mode == 'preserve':
                mode = '0%03o' % stat.S_IMODE(os.stat(source).st_mode)

            if format not in supported_formats:
                raise AnsibleActionFail(f"format must be one of the following: {supported_formats}")

            #
            # get absolute path of file or get from vault
            # get vault decrypted tmp file
            #

            source_path = self.__get_absolute_template_path(source)

            #
            # run template engine, get result, and prepare data for transfer to remote host
            # template the source data locally & get ready to transfer
            #

            try:
                templar = self.__create_templar(task_vars, source, dest,)

                #
                # run jsonnet compiler and get result
                #

                obj = self.__compile_jsonnet(templar, source_path)

                if format == JSON_FORMAT:
                    resultant = json.dumps(obj, indent=2)
                else:
                    resultant = yaml.dump(obj)

                # resultant = resultant + "\n"

            except AnsibleAction:
                raise
            except Exception as e:
                raise AnsibleActionFail("%s: %s" % (type(e).__name__, to_text(e)))
            finally:
                self._loader.cleanup_tmp_file(source_path)

            #
            # copy to remote host
            #

            self.__copy_to_remote(result, task_vars, resultant, source, dest, mode)

        except AnsibleAction as e:
            result.update(e.result)
        finally:
            self._remove_tmp_path(self._connection._shell.tmpdir)

        return result

    def __validate_options(self):
        # strings
        for s_type in ('src', 'dest', 'format'):
            if s_type in self._task.args:
                value = ensure_type(self._task.args[s_type], 'string')
                if value is not None and not isinstance(value, string_types):
                    raise AnsibleActionFail("%s is expected to be a string, but got %s instead" % (s_type, type(value)))
                self._task.args[s_type] = value

    def __process_args(self, source: str, dest: str) -> Tuple[str, str]:
        if source is None or dest is None:
            raise AnsibleActionFail("src and dest are required")
        else:
            try:
                source = self._find_needle('templates', source)
            except AnsibleError as e:
                raise AnsibleActionFail(to_text(e))

        return source, dest

    def __get_absolute_template_path(self, source: str) -> str:
        try:
            tmp_source = self._loader.get_real_file(source)
        except AnsibleFileNotFound as e:
            raise AnsibleActionFail("could not find src=%s, %s" % (source, to_text(e)))
        return to_bytes(tmp_source, errors='surrogate_or_strict').decode("utf-8")

    def __create_templar(self, task_vars: Any, source: str, dest: str) -> object:
        # set jinja2 internal search path for includes
        searchpath = task_vars.get('ansible_search_path', [])
        searchpath.extend([self._loader._basedir, os.path.dirname(source)])

        # We want to search into the 'templates' subdir of each search path in
        # addition to our original search paths.
        newsearchpath = []
        for p in searchpath:
            newsearchpath.append(os.path.join(p, 'templates'))
            newsearchpath.append(p)
        searchpath = newsearchpath

        # add ansible 'template' vars
        temp_vars = task_vars.copy()
        temp_vars.update(generate_ansible_template_vars(self._task.args.get('src', None), source, dest))

        # force templar to use AnsibleEnvironment to prevent issues with native types
        # https://github.com/ansible/ansible/issues/46169
        return self._templar.copy_with_new_env(environment_class=AnsibleEnvironment,
                                               searchpath=searchpath,
                                               available_variables=temp_vars)

    def __compile_jsonnet(self, templar, source_path) -> Dict:
        def ansible_expr(expr):
            return templar.template(expr, convert_bare=True)

        native_callbacks = {
            'ansible_expr': (('expr',), ansible_expr),
        }

        res = _jsonnet.evaluate_file(
            source_path,
            native_callbacks=native_callbacks)

        return json.loads(res)

    def __copy_to_remote(self, result: Any, task_vars: Any, resultant: str, source: str, dest: str, mode: str):
        new_task = self._task.copy()
        # mode is either the mode from task.args or the mode of the source file if the task.args
        # mode == 'preserve'
        new_task.args['mode'] = mode

        # remove 'template only' options:
        for remove in ('format',):
            new_task.args.pop(remove, None)

        local_tempdir = tempfile.mkdtemp(dir=C.DEFAULT_LOCAL_TMP)

        try:
            result_file = os.path.join(local_tempdir, os.path.basename(source))
            with open(to_bytes(result_file, errors='surrogate_or_strict'), 'wb') as f:
                f.write(to_bytes(resultant, encoding="utf-8", errors='surrogate_or_strict'))

            new_task.args.update(
                dict(
                    src=result_file,
                    dest=dest,
                ),
            )

            # call with ansible.legacy prefix to eliminate collisions with collections while still allowing local override
            copy_action = self._shared_loader_obj.action_loader.get('ansible.legacy.copy',
                                                                    task=new_task,
                                                                    connection=self._connection,
                                                                    play_context=self._play_context,
                                                                    loader=self._loader,
                                                                    templar=self._templar,
                                                                    shared_loader_obj=self._shared_loader_obj)
            result.update(copy_action.run(task_vars=task_vars))
        finally:
            shutil.rmtree(to_bytes(local_tempdir, errors='surrogate_or_strict'))
