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
legion K8S CRD Model Training
"""
import base64
import binascii
import logging
import typing

from legion.k8s.crd.base import BaseCRD
import legion.k8s.definitions as defs

LOGGER = logging.getLogger(__name__)


class ModelTraining(BaseCRD):
    VERSION: str = 'v1'
    KIND: str = 'ModelTraining'
    PLURAL: str = 'model-trainings'
    SINGULAR: str = 'model-training'

    @property
    def toolchain(self) -> typing.Optional[str]:
        return self.spec.get('toolchain')

    @property
    def image(self) -> typing.Optional[str]:
        return self.spec.get('image')

    @property
    def vcs(self) -> typing.Optional[str]:
        return self.spec.get('vcs')

    @property
    def customVcsBranch(self) -> typing.Optional[str]:
        return self.spec.get('customVcsBranch')

    @property
    def resources(self) -> dict:
        return self.spec.get('resources', {})

    @property
    def resources_ram(self) -> typing.Union[None, int, str]:
        return self.resources.get('ram')

    @property
    def resources_cpu(self) -> typing.Union[None, int, str]:
        return self.resources.get('cpu')

    @property
    def parameters(self) -> dict:
        return self.spec.get('parameters', {})

    @property
    def entrypoint(self) -> typing.Optional[str]:
        return self.spec.get('entrypoint')

    @property
    def arguments(self) -> typing.Tuple[typing.Union[str, int], ...]:
        return self.spec.get('arguments', tuple())

    @property
    def state(self) -> typing.Optional[str]:
        return self.status.get('state')

    @property
    def result(self) -> typing.Optional[str]:
        return self.status.get('result')

    @property
    def failure(self) -> typing.Optional[str]:
        return self.status.get('failure')

