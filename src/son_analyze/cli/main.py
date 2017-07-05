# Copyright (c) 2015 SONATA-NFV, Thales Communications & Security
# ALL RIGHTS RESERVED.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Neither the name of the SONATA-NFV, Thales Communications & Security
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).


"""son-analyze command line tool"""

import sys
import os
import logging
import signal
import urllib.parse
import uuid
from argparse import ArgumentParser, Namespace, ArgumentTypeError
from pkg_resources import resource_filename  # type: ignore
import typing  # noqa pylint: disable=unused-import
from typing import List
from docker import APIClient  # type: ignore
from son_analyze import __version__
from son_analyze.cli import fetch_cmd
from son_analyze.core import types


_LOGGER = logging.getLogger(__name__)
_IMAGE_TAG = 'son-analyze-scikit'


def bootstrap(args: Namespace) -> None:
    """Create the images used by son-analyze in the current host"""
    cli = APIClient(base_url=args.docker_socket)
    root_context = os.path.realpath(
        resource_filename('son_analyze.cli', '../../..'))
    _LOGGER.info('The root context path is: %s', root_context)
    path = resource_filename('son_analyze.cli.resources',
                             'anaconda.Dockerfile')
    path = os.path.relpath(path, root_context)
    _LOGGER.info('The relative path to the bootstrap dockerfile is: %s', path)
    # import pdb; pdb.set_trace()
    for line in cli.build(path=root_context, tag=_IMAGE_TAG,
                          dockerfile=path, rm=True, decode=True):
        if "stream" in line:
            print('> ', line["stream"], end="")
        else:
            print(line)
            sys.exit(1)
    sys.exit(0)


def run(args: Namespace) -> None:
    """Run an analysis framework environment"""
    cli = APIClient(base_url=args.docker_socket)
    binds = {  # type: Dict[str, Dict[str, str]]
        '/dev/random': {
            'bind': '/dev/random'
        },
        '/dev/urandom': {
            'bind': '/dev/urandom'
        }
    }
    if args.dynamic_mount:
        field_name = os.path.realpath(
            resource_filename('son_analyze.cli', '../../..'))
        new_entry = {
            field_name: {
                'bind': '/son-analyze',
                'mode': 'rw'
            }
        }
        binds.update(new_entry)
    host_config = cli.create_host_config(
        port_bindings={8888: args.jupiter_port},
        binds=binds)
    container = cli.create_container(image=_IMAGE_TAG+':latest',
                                     labels=['com.sonata.analyze'],
                                     ports=[8888],
                                     host_config=host_config,
                                     command=['start-notebook.sh'])
    container_id = container.get('Id')
    cli.start(container=container_id)

    def cleanup():
        """Remove the container"""
        cli.remove_container(container=container_id, force=True)

    def signal_term_handler(unused1, unused2):  # noqa pylint: disable=unused-argument
        """Catch signal to clean the containers"""
        print('Interruption detected, stopping environment')
        cleanup()
        sys.exit(1)

    signal.signal(signal.SIGTERM, signal_term_handler)
    signal.signal(signal.SIGINT, signal_term_handler)

    print('Browse http://localhost:{} \n'
          'Type Ctrl-C to exit'.format(args.jupiter_port))
    exit_code = 0
    exit_code = cli.wait(container=container_id)
    cleanup()
    sys.exit(exit_code)


def version(args: Namespace) -> None:
    """Print the current version and exit"""
    msg = 'son-analyze version: {}'.format(__version__)
    if args.short:
        msg = __version__
    print(msg)
    sys.exit(0)


def resource_target(raw_target: str) -> types.ResourceTargetTuple:
    """Define the type of resource"""
    if ',' in raw_target:
        try:
            rvendor, rname, rversion = raw_target.split(',')
            return types.ResourceTargetTuple(vendor=rvendor, name=rname,
                                             version=rversion, uuid=None)
        except:
            raise ArgumentTypeError("Target must have the form: "
                                    "<vendor>,<name>,<version>")
    else:
        try:
            tid = str(uuid.UUID(raw_target))
            return types.ResourceTargetTuple(vendor=None, name=None,
                                             version=None, uuid=tid)
        except:
            raise ArgumentTypeError("Target uuid must have the form: "
                                    "<12345678-1234-1234-1234-123456789012>")


def url_type(raw_url: str) -> urllib.parse.ParseResult:
    """Define the type of a URL"""
    url = urllib.parse.urlparse(raw_url, scheme='http')
    isvalid = all(getattr(url, attr) for attr in ['scheme', 'netloc'])
    if isvalid:
        return url
    else:
        raise ArgumentTypeError("Url is not valid")


def fetch_func(args: Namespace) -> None:
    """Fetch data"""
    fetch_cmd.fetch_cmd(args.endpoint, args.kind, args.target)
    sys.exit(0)


def dispatch(raw_args: List) -> None:
    """Parse the raw_args and dispatch the control flow"""
    parser = ArgumentParser(description=('An analysis framework '
                                         'creation tool for Sonata'))
    parser.add_argument('-v', '--verbose', default=logging.WARNING,
                        action="store_const", dest="logLevel",
                        const=logging.INFO, help='increase verbosity')
    parser.add_argument('--docker-socket', type=str,
                        default='unix://var/run/docker.sock',
                        action='store',
                        help=('An uri to the docker socket '
                              '(default: %(default)s)'))

    def no_command(_: Namespace) -> None:
        """Print the help usage and exit"""
        parser.print_help()
        sys.exit(0)
    parser.set_defaults(func=no_command)
    subparsers = parser.add_subparsers()

    parser_version = subparsers.add_parser('version', help='Show the version')
    parser_version.add_argument('--short', default=False, action='store_true',
                                help='Shows only the version')
    parser_version.set_defaults(func=version)

    parser_bootstrap = subparsers.add_parser('bootstrap',
                                             help='Bootstrap son-analyze')
    parser_bootstrap.set_defaults(func=bootstrap)

    parser_run = subparsers.add_parser('run', help='Run an environment')
    parser_run.add_argument('--dynamic-mount', default=False,
                            action='store_true',
                            help=('(Dev) Dynamically mount the R code'
                                  ' inside the environment'))
    parser_run.add_argument('--port', type=int,
                            default=8888, action='store', dest='jupiter_port',
                            help=('The listening port for the Jupiter '
                                  'server (default: %(default)d)'))

    parser_run.set_defaults(func=run)

    parser_fetch = subparsers.add_parser('fetch', help='Fetch data/metrics')
    default_val = urllib.parse.urlparse(
        'http://sp.int2.sonata-nfv.eu:9090', scheme='http')
    help_msg = 'A Gatekeeper endpoint (default: {})'.format(
        default_val.geturl())
    parser_fetch.add_argument('--endpoint', action='store', help=help_msg,
                              metavar='URL', type=url_type,
                              default=default_val)
    parser_fetch.add_argument('kind', help="The resource's type",
                              type=str, choices=['nsd', 'vnfd'])
    parser_fetch.add_argument('target', type=resource_target,
                              help=('A resource specified by: '
                                    '<vendor>,<name>,<version> or <uuid>'))
    parser_fetch = parser_fetch.set_defaults(func=fetch_func)

    args = parser.parse_args(raw_args)
    logging.basicConfig(level=args.logLevel)
    args.func(args)
    assert False  # this line is impossible to reach


def main() -> None:
    """Main entry point for the son-analyze command line tool"""
    dispatch(sys.argv[1:])
