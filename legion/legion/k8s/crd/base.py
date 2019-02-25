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
legion K8S CRD VCS
"""
import typing


class BaseCRD:
    VERSION = None
    KIND = None
    PLURAL = None

    def __init__(self, k8s_instance: dict):
        self._k8s_instance = k8s_instance

    @property
    def k8s_instance(self) -> dict:
        """
        Get K8S instance

        :return: dict -- K8S Instance
        """
        return self._k8s_instance

    @property
    def metadata(self) -> dict:
        return self.k8s_instance.get('metadata', {})

    @property
    def name(self) -> typing.Optional[str]:
        return self.metadata.get('name')

    @property
    def uid(self) -> typing.Optional[str]:
        return self.metadata.get('uid')

    @property
    def namespace(self) -> typing.Optional[str]:
        return self.metadata.get('namespace')

    @property
    def spec(self) -> dict:
        return self.k8s_instance.get('spec', {})

    @property
    def status(self) -> dict:
        return self.k8s_instance.get('status', {})

