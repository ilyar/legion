#
#    Copyright 2019 EPAM Systems
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#
"""
Local commands for legion cli
"""
import argparse
import logging
import os
import stat
import uuid

from legion.sdk import config, utils
from legion.sdk.containers.definitions import ModelBuildParameters
from legion.sdk.containers.docker import build_model_docker_image

BUILD_TYPE_DOCKER_SOCKET = 'docker-socket'
BUILD_TYPE_DOCKER_REMOTE = 'docker-remote'

LOGGER = logging.getLogger(__name__)


def build_model(args):
    """
    Build model

    :param args: command arguments
    :type args: :py:class:`argparse.Namespace`
    :return: None
    """
    model_file = args.model_file
    if not model_file:
        model_file = config.MODEL_FILE

    if not model_file:
        raise Exception('Model file has not been provided')

    params = ModelBuildParameters(model_file,
                                  str(uuid.uuid4()),
                                  args.docker_image_tag,
                                  args.push_to_registry)

    model_image = build_model_docker_image(params, args.container_id)

    LOGGER.info('The image %s has been built', model_image)


def sandbox(args):
    """
    Create local sandbox
    It generates bash script to run sandbox


    :param args: command arguments with .image, .force_recreate
    :type args: :py:class:`argparse.Namespace`
    :return: None
    """
    work_directory = '/work-directory'

    local_fs_work_directory = os.path.abspath(os.getcwd())

    legion_data_directory = '/opt/legion/'
    model_file = 'model.bin'

    arguments = dict(
        local_fs=local_fs_work_directory,
        image=args.image,
        work_directory=work_directory,
        legion_data_directory=legion_data_directory,
        model_file=model_file,
        remove_arguments='--rm' if config.SANDBOX_CREATE_SELF_REMOVING_CONTAINER else '',
        docker_socket_path=config.SANDBOX_DOCKER_MOUNT_PATH
    )
    cmd = utils.render_template('sandbox-cli.sh.tmpl', arguments)

    path_to_activate = os.path.abspath(os.path.join(os.getcwd(), 'legion-activate.sh'))

    if os.path.exists(path_to_activate) and not args.force_recreate:
        print('File {} already existed, ignoring creation of sandbox'.format(path_to_activate))
        return

    with open(path_to_activate, 'w') as activate_file:
        activate_file.write(cmd)

    current_mode = os.stat(path_to_activate)
    os.chmod(path_to_activate, current_mode.st_mode | stat.S_IEXEC)

    print('Sandbox has been created!')
    print('To activate run {!r} from command line'.format(path_to_activate))


def generate_parsers(main_subparser: argparse._SubParsersAction) -> None:
    """
    Generate cli parsers

    :param main_subparser: parent cli parser
    """
    build_model_parser = main_subparser.add_parser('build',
                                                   description='build model into new docker image (should be run '
                                                               'in the docker container)')
    build_model_parser.add_argument('--model-file',
                                    type=str, help='serialized model file name')
    build_model_parser.add_argument('--docker-image-tag',
                                    type=str, help='docker image tag')
    build_model_parser.add_argument('--push-to-registry',
                                    type=str, help='docker registry address')
    build_model_parser.add_argument('--container-id',
                                    help='If parameters is empty than legionctl will commit current container')
    build_model_parser.set_defaults(func=build_model)

    sandbox_parser = main_subparser.add_parser('create-sandbox', description='create sandbox')
    sandbox_parser.add_argument('--image',
                                type=str,
                                default=config.SANDBOX_PYTHON_TOOLCHAIN_IMAGE,
                                help='explicitly set toolchain python image')
    sandbox_parser.add_argument('--force-recreate',
                                action='store_true',
                                help='recreate sandbox if it already existed')
    sandbox_parser.set_defaults(func=sandbox)
