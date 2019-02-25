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
legion Controller for CRD ModelTraining
"""
import typing

import kubernetes.client.apis
import kubernetes.client.models

import legion.config
from legion.k8s import utils as k8s_utils
from .base import CRDController, ChildInstanceCollection, ChildReferenceDeclaration, DesiredState, ChildInstancePair
from legion.k8s.crd.model_training import ModelTraining
from legion.k8s.crd.vcs import VCS


class ModelTrainingController(CRDController):
    TARGET_CRD_CLASS = ModelTraining
    MONITOR_CHILD = True

    CHILD_TYPES = (
        ChildReferenceDeclaration(type=kubernetes.client.models.V1Secret,
                                  api_group=kubernetes.client.apis.CoreV1Api,
                                  plural='secrets',
                                  singular='secret',
                                  trackChangesFields=('data',)),
        ChildReferenceDeclaration(type=kubernetes.client.models.V1Pod,
                                  api_group=kubernetes.client.apis.CoreV1Api,
                                  plural='pods',
                                  singular='pod',
                                  trackChangesFields=('spec',)),
    )

    CHILD_POD_NAME = 'training-pod'
    CHILD_POD_CONTAINER_MODEL_NAME = 'model'
    CHILD_POD_CONTAINER_VCS_NAME = 'model'

    CHILD_SECRET_NAME = 'checkout-secret'

    def on_update(self, crd_instance: ModelTraining, actual_child: ChildInstanceCollection):
        vcs: VCS = self._get_namespaced_cr(VCS, crd_instance.namespace, crd_instance.vcs)

        return DesiredState(
            child=(
                ChildInstancePair(type=kubernetes.client.models.V1Secret,
                                  name=self.CHILD_SECRET_NAME,
                                  instance=self.create_secret_from_mt(crd_instance, vcs)),
                ChildInstancePair(type=kubernetes.client.models.V1Pod,
                                  name=self.CHILD_POD_NAME,
                                  instance=self.create_pod_from_mt(crd_instance, vcs)),
            ),
            status={}
        )

    @staticmethod
    def create_pod_from_mt(crd_instance: ModelTraining, vcs: VCS) -> kubernetes.client.models.V1Pod:
        vcs_branch = vcs.default_reference
        if crd_instance.customVcsBranch:
            vcs_branch = crd_instance.customVcsBranch

        bootup_mount = '/bootup/'

        start_command = [
            '/bin/sh',
        ]

        start_args = [
            '-c',
            'python3 {}bootstrapper.py python {}'.format(bootup_mount, crd_instance.entrypoint),
        ]

        #if crd_instance.arguments:
        #    start_args.extend(crd_instance.arguments)

        return kubernetes.client.models.V1Pod(
            metadata=kubernetes.client.models.V1ObjectMeta(
                name=crd_instance.name + '-training-pod',
                namespace=crd_instance.namespace,
            ),
            spec=kubernetes.client.models.V1PodSpec(
                restart_policy='Never',
                volumes=[
                     kubernetes.client.V1Volume(
                         name='docker-socket',
                         host_path=kubernetes.client.V1HostPathVolumeSource(
                             path='/var/run/docker.sock'
                         )
                     ),
                     kubernetes.client.V1Volume(
                         name='git-checkout-secret',
                         secret=kubernetes.client.V1SecretVolumeSource(
                             secret_name=crd_instance.name + '-training-git-creds'
                         )
                     ),
                     kubernetes.client.V1Volume(
                         name='bootup',
                         config_map=kubernetes.client.V1ConfigMapVolumeSource(
                             name=legion.config.TOOLCHAIN_BOOTUP_SCRIPT_PYTHON
                         )
                     )
                ],
                containers=[
                    kubernetes.client.models.V1Container(
                        name='training-pod',
                        image=crd_instance.image,
                        image_pull_policy=None,
                        command=start_command,
                        args=start_args,
                        env=[
                            kubernetes.client.V1EnvVar(
                                name='MODEL_TRAIN_METRICS_ENABLED',
                                value='false'
                            ),
                            kubernetes.client.V1EnvVar(
                                name='GIT_CHECKOUT_REPO_URI',
                                value=vcs.uri
                            ),
                            kubernetes.client.V1EnvVar(
                                name='GIT_CHECKOUT_REPO_REF',
                                value=vcs_branch
                            ),
                        ],
                        resources=kubernetes.client.models.V1ResourceRequirements(
                            limits={
                                'cpu': crd_instance.resources_cpu,
                                'memory': crd_instance.resources_ram
                            },
                            requests={
                                'cpu': k8s_utils.reduce_cpu_resource(crd_instance.resources_cpu),
                                'memory': k8s_utils.reduce_mem_resource(crd_instance.resources_ram)
                            }
                        ),
                        volume_mounts=[
                            kubernetes.client.V1VolumeMount(
                                mount_path='/var/run/docker.sock',
                                name='docker-socket'
                            ),
                            kubernetes.client.V1VolumeMount(
                                mount_path=bootup_mount,
                                name='bootup'
                            )
                        ]
                    )
                ]
            )
        )

    @staticmethod
    def create_secret_from_mt(crd_instance: ModelTraining, vcs: VCS) -> kubernetes.client.models.V1Secret:
        return kubernetes.client.models.V1Secret(
            metadata=kubernetes.client.models.V1ObjectMeta(
                name=crd_instance.name + '-training-git-creds',
                namespace=crd_instance.namespace,
                annotations={
                    vcs.ANNOTATION_URI: vcs.uri,
                    vcs.ANNOTATION_DEF_REF: vcs.default_reference
                }
            ),
            data={
                'key': vcs.private_key
            }
        )
