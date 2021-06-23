from __future__ import (absolute_import, division, print_function)
from typing import Callable
__metaclass__ = type

from ansible.errors import AnsibleError, AnsibleParserError
from ansible.plugins.lookup import LookupBase
from ansible.utils.display import Display
from ansible.vars.hostvars import HostVars

import os
import sys
from functools import reduce, partial
import itertools
import inspect
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple


BASEDIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(BASEDIR)
sys.path.append(os.path.join(BASEDIR, '..'))


from utils import *


display = Display()


################################################################################
################################################################################


HTTP = 'http'
TCP = 'tcp'
UDP = 'udp'

INDENT = '  '


################################################################################
################################################################################


Labels = List[str]
MiddlewareNames = List[str]
RendererResult = Tuple[Labels, MiddlewareNames]


################################################################################
################################################################################


global renderers
renderers = {}


def mk_f(data):
    return lambda: data


def copy_f_name(target: Callable, source: Callable):
    target.__name__ = source.__name__
    return target


def generify(f: Callable[..., Any]):
    def generify_actual(*args, **kwargs):
        if len(args) > 0:
            return f(*args, **kwargs)
        else:
            sig = inspect.signature(f)
            arg_names = sig.parameters.keys()

            return f(**{arg: kwargs[arg] for arg in kwargs.keys() & arg_names})
    return copy_f_name(generify_actual, f)


def __register(f, n, r):
    r[n] = f
    return f


register_custom = partial(__register, r=renderers)
def register(f): return register_custom(f, f.__name__)


def register_generified(f: Callable[..., RendererResult]):
    return register_custom(generify(f), f.__name__)


def local_mw(f: Callable[..., Labels]) -> Callable[..., RendererResult]:
    def local_mw_actual(**kwargs):
        name = mw_name(kwargs.get('sn'), f.__name__)
        fqdn_name = fqdn_mw_name(name)

        labels = generify(f)(**kwargs)

        return (
            [mw_label(f'{name}.{l}') for l in labels],
            [fqdn_name]
        )

    return register_custom(local_mw_actual, f.__name__)


def to_mw(f: Callable[..., Labels]) -> Callable[..., RendererResult]:
    def to_mw_actual(*args, **kwargs):
        return [f(*args, **kwargs), []]
    return to_mw_actual


def chain(*f: Callable[[], Tuple[List[str], List[str]]]):
    def reducer(result, f):
        fr = f()
        return [result[0] + fr[0], result[1] + fr[1]]
    return reduce(reducer, f, [[], []])


################################################################################
################################################################################


def add_service_name(f: Callable[..., str]):
    def add_service_name_actual(service_name: str, *args, **kwargs):
        return [f'{service_name}.{l}' for l in f(*args, **kwargs)]

    return add_service_name_actual


def labels(label: Callable[[str], str]) -> Callable[..., Callable[..., Callable[..., Labels]]]:
    def func(f: Callable[..., Labels]) -> Callable[..., Labels]:
        def labels_actual(*args, **kwargs) -> Labels:
            return [label(l) for l in f(*args, **kwargs)]
        return labels_actual
    return func


def traefik_label(rest: str) -> str:
    return f'- "traefik.{rest}"'


def service_name_labels(protocol: str, label: Callable[[str, str], str]):
    def service_name_labels_actual(f):
        f_name = f.__name__
        f = generify(f)
        f_dec = to_mw(labels(lambda rest: label(rest, protocol))(add_service_name(f)))
        register_custom(f_dec, f_name)
        return f_dec
    return service_name_labels_actual


def router_label(rest: str, protocol: str) -> str:
    return traefik_label(f'{protocol}.routers.{rest}')


def router_labels(protocol: str) -> Callable[..., List[str]]:
    return service_name_labels(protocol, router_label)


def service_label(rest: str, protocol: str) -> str:
    return traefik_label(f'{protocol}.services.{rest}')


def service_labels(protocol: str):
    return service_name_labels(protocol, service_label)


def mw_label(rest: str) -> str:
    return traefik_label(f'http.middlewares.{rest}')


def mw_name(sn: str, mw: str) -> str:
    return f'{sn}_{mw}'


def fqdn_mw_name(name: str) -> str:
    return f'{name}@docker'


def external_mw(name: str) -> str:
    return ([], [name])


################################################################################
################################################################################


@register_generified
def auth():
    return external_mw('authelia@docker')


@local_mw
def basic_auth(users: str) -> List[str]:
    return [f'basicauth.users={espace_yaml(users)}']


@local_mw
def add_trailing_slash() -> List[str]:
    return [
        'redirectregex.regex=^(https?://[^/]+/[a-z0-9_]+)$$',
        'redirectregex.replacement=$${1}/',
        'redirectregex.permanent=true'
    ]


@local_mw
def strip_path(path: str) -> List[str]:
    return [
        f'stripprefix.prefixes={path}',
        f'stripprefix.forceslash=true'
    ]


@local_mw
def replace_path(path: str) -> List[str]:
    return [f'replacepath.path={path}']


@local_mw
def replace_path_regex(regex: str, replacement: str) -> List[str]:
    return [
        f'replacepathregex.regex={espace_yaml(regex)}',
        f'replacepathregex.replacement={espace_yaml(replacement)}'
    ]


@local_mw
def redirect(old_path: str, new_path: str) -> List[str]:
    return [
        f'redirectregex.regex=^(.*){old_path}/?$$',
        f'redirectregex.replacement=$${1}{new_path}',
        f'redirectregex.permanent=true'
    ]


@local_mw
def fix_wss() -> List[str]:
    return ['headers.customrequestheaders.X-Forwarded-Proto=https']


@local_mw
def add_cors(methods: str, originlist: str, allowheaders: Optional[str] = None) -> List[str]:
    labels = [
        f'headers.accesscontrolallowmethods={methods}'
        f'headers.accesscontrolalloworiginlist={originlist}'
    ]

    if allowheaders is not None:
        labels.append(f'headers.accesscontrolallowheaders={allowheaders}')

    return labels


################################################################################
################################################################################


def labels_protocol_sn(labels: Callable[[str], Callable[[Callable[..., Labels]], Labels]],
                       renderer: Callable[..., List],
                       service_name: str,
                       protocol: str):
    return labels(protocol)(renderer)(service_name)


router_protocol_sn = partial(labels_protocol_sn, router_labels)
service_protocol_sn = partial(labels_protocol_sn, service_labels)


@labels(traefik_label)
def enable(variables):
    return [
        f'enable=true',
        f'docker.network={variables["network_names_discovery"]}'
    ]


@register_generified
def map_service_to_router(service_name: str, protocol: str):
    return router_protocol_sn(mk_f([f'service={service_name}']), service_name, protocol)


@register_generified
def entrypoints(service_name: str, protocol: str, entries: List[str]):
    return router_protocol_sn(mk_f([f'entrypoints={",".join(entries)}']), service_name, protocol)


################################################################################
################################################################################


@router_labels(HTTP)
def tls():
    return ['tls=true']


@router_labels(HTTP)
def letsencrypt(variables):
    return [f'tls.certresolver={variables["letsencrypt_resolver_name"]}']


@router_labels(HTTP)
def route(expression: str):
    return [f'rule={expression}']


@router_labels(HTTP)
def default_route(host: str, path: str):
    return [f'rule=Host(`{host}`) && PathPrefix(`{path}`)']


@register_generified
def service_port(service_name: str, protocol: str, port: int):
    return service_protocol_sn(mk_f([f'loadbalancer.server.port={str(port)}']), service_name, protocol)


@router_labels(HTTP)
def declare_middlewares(mws: List[str]):
    if (len(mws)) == 0:
        return []
    return [f'middlewares={",".join(mws)}']


################################################################################
################################################################################

@router_labels(TCP)
def tcp_host_sni(host_sni: str):
    return [f'rule=HostSNI(`{host_sni}`)']


@register_generified
def tcp_host_sni_any(service_name: str):
    return tcp_host_sni(service_name, '*')


################################################################################
################################################################################


RendererDeclaration = Dict[str, Dict[str, Any]]


@dataclass
class Options:
    service_name: str

    entrypoints: List[str] = field(default_factory=lambda: ['websecure'])
    port: int = 80
    domain: str = None
    strip_path: bool = True
    use_dns_root: bool = False
    use_auth: bool = True
    use_defaults: bool = True
    use_internal: bool = False
    path: str = None
    protocol: str = 'http'

    renderers: List[RendererDeclaration] = field(default_factory=dict)


def setup_protocol_handler(f) -> Tuple[Dict, Callable]:
    def setup_protocol_handler_actual(options: Options, variables: HostVars):
        def enrich(d: Dict[str, Any] = dict()):
            d.update({
                'sn': options.service_name,
                'service_name': options.service_name,
                'protocol': options.protocol,
                'variables': variables
            })

            return d

        local_renderers = {}

        if options.domain is None:
            options.domain = variables['dns_internal_root'] if options.use_internal else variables['dns_public_root']

        if options.path is None:
            options.path = "/" + options.service_name

        local_renderers['entrypoints'] = enrich({'entries': options.entrypoints})
        local_renderers['map_service_to_router'] = enrich()
        local_renderers['service_port'] = enrich({'port': options.port})

        return f(options, variables, local_renderers, enrich)

    return copy_f_name(setup_protocol_handler_actual, f)


def auto_execute(f):
    def auto_execute_actual(options: Options, variables: HostVars):
        local_renderers = f(options, variables)
        labels, declarations = chain(*map(lambda m: lambda: renderers[m[0]](**m[1]), local_renderers.items()))

        return sorted(itertools.chain(labels, declare_middlewares(options.service_name, declarations)[0]))

    return copy_f_name(auto_execute_actual, f)


def merge_renderers(local_renderers, options, enrich):
    local_renderers.update({k: enrich(v) for k, v in options.renderers.items()})
    return local_renderers


@register
@auto_execute
@setup_protocol_handler
def http(options: Options, variables: HostVars, local_renderers: RendererDeclaration, enrich: Callable):
    if options.use_dns_root:
        local_renderers['route'] = enrich({'expression': f'Host(`{options.domain}`)'})
    else:
        if 'route' not in options.renderers:
            local_renderers['default_route'] = enrich({'host': options.domain, 'path': f'{options.path}'})
        if options.use_defaults:
            local_renderers['add_trailing_slash'] = enrich()

    if options.use_defaults:
        local_renderers['fix_wss'] = enrich()

        if options.use_auth:
            local_renderers['auth'] = enrich()

        if options.strip_path and not options.use_dns_root:
            local_renderers['strip_path'] = enrich({'path': options.path})

    local_renderers['tls'] = enrich()

    if variables['is_dev'] == False:
        local_renderers['letsencrypt'] = enrich()

    return merge_renderers(local_renderers, options, enrich)


@register
@auto_execute
@setup_protocol_handler
def tcp(options: Options, variables: HostVars, local_renderers: RendererDeclaration, enrich: Callable):
    if options.use_defaults:
        local_renderers['tcp_host_sni_any'] = enrich()

    return merge_renderers(local_renderers, options, enrich)


@register
@auto_execute
@setup_protocol_handler
def udp(options: Options, variables: HostVars, local_renderers: RendererDeclaration, enrich: Callable):
    return merge_renderers(local_renderers, options, enrich)


################################################################################
################################################################################


class LookupModule(LookupBase):

    def run(self, terms: Tuple[Options], variables: HostVars = None, **kwargs) -> List[str]:

        # lookups in general are expected to both take a list as input and output a list
        # this is done so they work with the looping construct 'with_'.
        lines: List[str] = []
        lines.extend(enable(variables))

        for term in terms:
            options = Options(**term)
            lines.extend(renderers[options.protocol](options, variables))

        result = '\n'.join(itertools.chain(["labels:"], map(lambda l: f'{INDENT}{l}', lines)))

        return [result]


if __name__ == "__main__":
    wk_path = '/test'

    l = LookupModule()
    l.run([

        {'service_name': 'rss', 'renderers': {'redirect': {"old_path": "/rss/api", "new_path": "/rss/api/"}}}
        #{ 'service_name': 'test', 'path': '/example', 'use_auth': False, 'renderers': { 'basic_auth': { 'users': 'TODO' } } }
        #{ 'service_name': 'authelia', 'use_defaults': False, 'domain': 'login.realmar.net', 'port': 9091, 'use_dns_root': True }

        #{ 'service_name': 'pihole', 'port': 80,  },
        #{ 'service_name': 'pihole', 'protocol': 'tcp', 'port': 53, 'entrypoints': [ 'dns_tcp' ] },
        #{ 'service_name': 'pihole', 'protocol': 'udp', 'port': 53, 'entrypoints': [ 'dns_udp' ] }

        #{ 'service_name': 'openvpn', 'protocol': 'udp', 'port': 1194, 'entrypoints': [ 'openvpn_udp' ] }
        #{ 'service_name': 'realmar_net', 'use_dns_root': True }

        # { 'service_name': 'matrix_well_known', 'use_defaults': False, 'path': wk_path,
        #    'renderers': {
        #        'replace_path_regex': {
        #        "regex": "^" + wk_path + "(server|client)$",
        #        "replacement": "/well-known_$1.json"
        #        },
        #        'add_cors': {
        #        "originlist": "*",
        #        "methods": "GET,POST,PUT,DELETE,OPTIONS",
        #        "allowheaders": "Origin,X-Requested-With,Content-Type,Accept,Authorization"
        #        }
        #    } }

        #{ 'service_name': 'backup', 'use_internal': True }
        #{'service_name': 'jupyter', 'strip_path': False, 'renderers': {'redirect': {"old_path": "/jupyter", "new_path": "/jupyter/lab/"}}}#
        #{ 'domain': 'smarthome.realmar.net', 'service_name': 'smarthome', 'port': 8123, 'use_dns_root': True }
        #{'domain': 'internal.realmar.net', 'service_name': 'docker_registry_ui', 'path': '/registry'},
        #{'service_name': 'among_us', 'protocol': 'udp', 'port': 22023, 'entrypoints': ['among_us']}


        # {
        #    'domain': 'realmar.net',
        #    'service_name': 'chronograf',
        #    'port': 8080,
        #
        #    'strip_path': False,
        #    'renderers': {
        #        'strip_path': {'path': '/chronograf'},
        #        'redirect': {'old_path': '/a', 'new_path': '/b'}
        #    }
        # }



    ], variables={'is_dev': False, 'dns': {'public': {'root': 'realmar.net'}, 'internal': {'root': 'internal.realmar.net'}}, 'letsencrypt_resolver_name': 'letsencrypt', 'network_names': {'discovery': 'discovery'}})

    # , service_name="test", path="/test", middlewares=[
    #     ('strip_path', {'path': '/test'}),
    #     ('redirect', {'old_path': '/a', 'new_path': '/b'}),
    # ])
