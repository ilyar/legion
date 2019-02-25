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
import base64
import binascii
import logging
import typing

from legion.k8s.crd.base import BaseCRD
import legion.k8s.definitions as defs

LOGGER = logging.getLogger(__name__)


class VCS(BaseCRD):
    VERSION: str = 'v1'
    KIND: str = 'VCS'
    PLURAL: str = 'vcss'
    SINGULAR: str = 'vcs'

    ANNOTATION_URI: str = defs.LEGION_CRD_ANNOTATION_ROOT + '.uri'
    ANNOTATION_DEF_REF: str = defs.LEGION_CRD_ANNOTATION_ROOT + '.defaultRef'

    @property
    def uri(self) -> typing.Optional[str]:
        return self.spec.get('uri')

    @property
    def default_reference(self) -> typing.Optional[str]:
        return self.spec.get('defaultRef')

    @property
    def private_key(self) -> typing.Optional[str]:
        value = self.spec.get('privateKey')
        if not value:
            return None
        return value

    @property
    def private_key_decoded(self) -> typing.Optional[str]:
        key = self.private_key
        if not key:
            return None

        try:
            decoded = base64.b64decode(key, validate=True).decode('utf-8')
        except binascii.Error as encoding_error:
            raise Exception('Invalid encoding for VCS key in base64 format: {}'.format(encoding_error))
        return decoded

