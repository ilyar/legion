#
#    Copyright 2017 EPAM Systems
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
legion k8s functions
"""
import logging
import os
import typing

import docker
import docker.errors
from docker.models.containers import Container
from docker.models.images import Image as DockerImage

from legion.sdk.containers import headers
from legion.sdk import config, utils
from legion.sdk.containers.definitions import ModelBuildParameters

from legion.sdk.model import load_meta_model, PROPERTY_TRAINING_WORKING_DIRECTORY
from legion.sdk.utils import get_installed_packages, get_list_of_requirements, copy_file, copy_directory_contents

LOGGER = logging.getLogger(__name__)
MODEL_TARGET_WORKSPACE = '/app'


def build_docker_client():
    """
    Create docker client

    :return: :py:class:`docker.Client`
    """
    client = docker.from_env()
    return client


def find_host_model_port(model_container: Container) -> int:
    """
    Find exposed on host model port
    :param model_container: model container
    :return exposed ports
    """
    model_ports: typing.Dict[str, typing.Any] = model_container.attrs['NetworkSettings']['Ports']

    for _, host_port in model_ports.items():
        if host_port:
            return host_port[0]['HostPort']

    raise ValueError(f'Can not find exposed port of model container {model_container.id}')


def get_docker_container_id_from_cgroup_line(line):
    """
    Get docker container id from proc cgroups line

    :argument line: line from /proc/<pid>/cgroup
    :type line: str
    :return: str -- container ID
    """
    parts = line.split('/')

    try:
        if 'docker' in parts:
            docker_pos = parts.index('docker')
            return parts[docker_pos + 1]
        elif 'kubepods' in parts:
            kubepods_pos = parts.index('kubepods')
            return parts[kubepods_pos + 3]
        else:
            raise Exception('Cannot find docker or kubepods tag in cgroups')
    except Exception as container_detection_error:
        raise Exception('Cannot find container ID in line {}: {}'.format(line, container_detection_error))


def get_current_docker_container_id():
    """
    Get ID of current docker container using proc cgroups

    :return: str -- current container id
    """
    with open('/proc/self/cgroup') as file:
        lines = [line.strip('\n') for line in file]
        longest_line = max(lines, key=len)
        return get_docker_container_id_from_cgroup_line(longest_line)


def commit_image(client, container_id=None):
    """
    Commit container and return image sha commit id

    :param client: Docker client
    :type client: :py:class:`docker.client.DockerClient`
    :param container_id: (Optional) id of target container. Current if None
    :type container_id: str
    :return: str -- docker image id
    """
    if not container_id:
        container_id = get_current_docker_container_id()

    container = client.containers.get(container_id)
    image = container.commit()
    LOGGER.info('Image %s has been captured', image.id)

    return image.id


def get_docker_log_line_content(log_line):
    """
    Get string from Docker log line object

    :param log_line: docker log line object
    :type log_line: str or dict
    :return: str -- log line
    """
    str_line = ''
    if isinstance(log_line, str):
        str_line = log_line
    elif isinstance(log_line, dict):
        if 'stream' in log_line and isinstance(log_line['stream'], str):
            str_line = log_line['stream']
        else:
            str_line = repr(log_line)

    return str_line.rstrip('\n')


def _check_python_packages() -> None:
    """
    Raise exception if there are missed python packages
    """
    LOGGER.info('Checking package state')

    installed_packages = set(get_installed_packages())
    requirements = set(get_list_of_requirements())
    missed_packages = requirements - installed_packages

    if missed_packages:
        missed_packages_requirements_list = ['{}=={}'.format(name, version)
                                             for (name, version) in missed_packages]
        raise Exception('Some packages are missed: {}'.format(', '.join(missed_packages_requirements_list)))


def _copy_model_files(working_directory: str, model_file: str, target_model_file: str) -> None:
    """
    Copy model files to the workspace

    :param working_directory: working directory
    :param model_file: a serialized model file
    :param target_model_file: path to the target model file location
    """
    try:
        LOGGER.info('Copying model binary from {!r} to {!r}'
                    .format(model_file, target_model_file))
        copy_file(model_file, target_model_file)
    except Exception as model_binary_copy_exception:
        LOGGER.exception('Unable to move model binary to persistent location',
                         exc_info=model_binary_copy_exception)
        raise

    try:
        LOGGER.info('Copying model workspace from {!r} to {!r}'.format(working_directory, MODEL_TARGET_WORKSPACE))
        copy_directory_contents(working_directory, MODEL_TARGET_WORKSPACE)
    except Exception as model_workspace_copy_exception:
        LOGGER.exception('Unable to move model workspace to persistent location',
                         exc_info=model_workspace_copy_exception)
        raise


def prepare_build(working_directory: str, model_id: str, model_file: str) -> None:
    """
    Execute some actions before building image

    :param working_directory: working directory
    :param model_id: model id
    :param model_file: path to model file (in the temporary directory)
    :return: docker.models.Image
    """
    _copy_model_files(working_directory, model_file, os.path.join(working_directory, model_id))


def build_docker_image(client: docker.client.DockerClient, params: ModelBuildParameters,
                       container_id: typing.Optional[str] = None) -> DockerImage:
    """
    Build docker image from current image with addition files

    :param container_id: id of container that will be committed. Further It will be used as base for model image
    :param params: Model docker build parameters
    :param client: Docker client
    :return: model docker image
    """
    LOGGER.info('Building docker image from model {!r}...'.format(params.model_file))

    if not os.path.exists(params.model_file):
        raise Exception('Cannot find model binary {}'.format(params.model_file))

    container = load_meta_model(params.model_file)
    model_id = container.model_id
    model_version = container.model_version
    workspace_path = container.meta_information.get(PROPERTY_TRAINING_WORKING_DIRECTORY, os.getcwd())
    LOGGER.info('Building model %s (id: %s, version: %s) in directory %s',
                params.model_file, model_id, model_version, workspace_path)

    local_image_tag = params.local_image_tag
    if not local_image_tag:
        local_image_tag = 'legion-model-{}:{}.{}'.format(model_id, model_version, utils.deduce_extra_version())

    image_labels = generate_docker_labels_for_image(params.model_file, model_id)

    prepare_build(workspace_path, model_id, params.model_file)

    with utils.TemporaryFolder('legion-docker-build') as temp_directory:
        target_model_file = os.path.join(MODEL_TARGET_WORKSPACE, model_id)

        # Copy additional files for docker build
        additional_directory = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            '..', 'templates', 'docker_files'
        ))
        utils.copy_directory_contents(additional_directory, temp_directory.path)

        # ALL Filesystem modification below next line would be ignored
        captured_image_id = commit_image(client, container_id)

        if workspace_path.count(os.path.sep) > 1:
            symlink_holder = os.path.abspath(os.path.join(workspace_path, os.path.pardir))
        else:
            symlink_holder = '/'

        # Remove old workspace (if exists), create path to old workspace's parent, create symlink
        symlink_create_command = 'rm -rf "{0}" && mkdir -p "{1}" && ln -s "{2}" "{0}"'.format(
            workspace_path,
            symlink_holder,
            MODEL_TARGET_WORKSPACE
        )
        LOGGER.info('Executing %s', symlink_create_command)

        docker_file_content = utils.render_template('Dockerfile.tmpl', {
            'MODEL_PORT': config.LEGION_PORT,
            'DOCKER_BASE_IMAGE_ID': captured_image_id,
            'MODEL_ID': model_id,
            'MODEL_FILE': target_model_file,
            'CREATE_SYMLINK_COMMAND': symlink_create_command
        })

        labels = {k: str(v) if v else None
                  for (k, v) in image_labels.items()}

        with open(os.path.join(temp_directory.path, 'Dockerfile'), 'w') as file:
            file.write(docker_file_content)

        LOGGER.info('Building docker image in folder {}'.format(temp_directory.path))
        try:
            image, _ = client.images.build(
                tag=local_image_tag,
                nocache=True,
                path=temp_directory.path,
                rm=True,
                labels=labels
            )

            LOGGER.info('Image has been built: %s', image)
        except docker.errors.BuildError as build_error:
            LOGGER.error('Cannot build image: {}. Build logs: '.format(build_error))
            for log_line in build_error.build_log:
                LOGGER.error(get_docker_log_line_content(log_line))
            raise

        return image


def generate_docker_labels_for_image(model_file, model_id):
    """
    Generate docker image labels from model file

    :param model_file: path to model file
    :type model_file: str
    :param model_id: model id
    :type model_id: str
    :return: dict[str, str] of labels
    """
    model_meta = load_meta_model(model_file)

    base = {
        headers.DOMAIN_MODEL_ID: model_id,
        headers.DOMAIN_MODEL_VERSION: model_meta.model_version,
        headers.DOMAIN_CLASS: 'pyserve',
        headers.DOMAIN_CONTAINER_TYPE: 'model'
    }

    for key, value in model_meta.meta_information.items():
        if hasattr(value, '__iter__') and not isinstance(value, str):
            formatted_value = ', '.join(item for item in value)
        else:
            formatted_value = str(value)

        base[headers.DOMAIN_PREFIX + key] = formatted_value

    return base


def generate_docker_labels_for_container(image):
    """
    Build container labels from image labels (copy)

    :param image: source Docker image
    :type image: :py:class:`docker.models.image.Image`
    :return: dict[str, str] of labels
    """
    return image.labels


def push_image_to_registry(client, image, external_image_name):
    """
    Push docker image to registry

    :param client: Docker client
    :type client: :py:class:`docker.client.DockerClient`
    :param image: Docker image
    :type image: :py:class:`docker.models.images.Image`
    :param external_image_name: target Docker image name (with repository)
    :type external_image_name: str
    :return: None
    """
    docker_registry = external_image_name
    version = None

    registry_delimiter = docker_registry.find('/')
    if registry_delimiter < 0:
        raise Exception('Invalid registry format')

    registry = docker_registry[:registry_delimiter]
    image_name = docker_registry[registry_delimiter + 1:]

    version_delimiter = image_name.find(':')
    if version_delimiter > 0:
        version = image_name[version_delimiter + 1:]
        image_name = image_name[:version_delimiter]

    docker_registry_user = config.DOCKER_REGISTRY_USER
    docker_registry_password = config.DOCKER_REGISTRY_PASSWORD
    auth_config = None

    if docker_registry_user and docker_registry_password:
        auth_config = {
            'username': docker_registry_user,
            'password': docker_registry_password
        }

    image_and_registry = '{}/{}'.format(registry, image_name)

    image.tag(image_and_registry, version)
    LOGGER.info('Pushing {}:{} to {}'.format(image_and_registry, version, registry))

    client.images.push(image_and_registry, tag=version, auth_config=auth_config)
    LOGGER.info('Successfully pushed image {}:{}'.format(image_and_registry, version))

    image_with_version = '{}/{}:{}'.format(registry, image_name, version)
    utils.send_header_to_stderr(headers.IMAGE_TAG_EXTERNAL, image_with_version)


def build_model_docker_image(params: ModelBuildParameters, container_id: typing.Optional[str] = None) -> str:
    """
    Build model docker image

    :param container_id: container id to capture as base image
    :param params: params to build model docker image
    :return: name of built model docker image
    """
    client = build_docker_client()

    image = build_docker_image(
        client, params, container_id
    )

    utils.send_header_to_stderr(headers.IMAGE_ID_LOCAL, image.id)

    if image.tags:
        utils.send_header_to_stderr(headers.IMAGE_TAG_LOCAL, image.tags[0])

    if params.push_to_registry:
        push_image_to_registry(client, image, params.push_to_registry)

    return params.local_image_tag
