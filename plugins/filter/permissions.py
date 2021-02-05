import os
import sys
from typing import List, Tuple, Optional, Iterator
from functools import *

BASEDIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(BASEDIR)
sys.path.append(os.path.join(BASEDIR, '..'))


from declarations import Volume, Permissions


def volumes_to_permissions(data: List[Tuple[Volume, str, Optional[str]]]) -> List[Permissions]:
    def f(d):
        p = Permissions(folder=d[0]['local_folder'], user=d[1])
        if len(d) > 2:
            p['group'] = d[2]
        return p

    return list(map(f, data))


class FilterModule(object):
    ''' Ansible core jinja2 filters '''

    def filters(self):
        return {
            volumes_to_permissions.__name__: volumes_to_permissions
        }
