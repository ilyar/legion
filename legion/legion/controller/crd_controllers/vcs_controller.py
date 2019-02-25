import typing

from .base import CRDController, ChildReferenceDeclaration, DesiredState
from legion.k8s.crd.vcs import VCS

import kubernetes.client.apis
import kubernetes.client.models


class VCSController(CRDController):
    TARGET_CRD_CLASS = VCS
    MONITOR_CHILD = False

    CHILD_TYPES = (
        ChildReferenceDeclaration(type=kubernetes.client.models.V1Secret,
                                  api_group=kubernetes.client.apis.CoreV1Api,
                                  plural='secrets',
                                  singular='secret'),
    )

    def on_update(self, crd_instance: VCS, actual_child: typing.Tuple[object, ...]):
        return DesiredState(
            child={
                kubernetes.client.models.V1Secret: (self.create_secret_from_vcs(crd_instance), )
            },
            status={}
        )

    @staticmethod
    def create_secret_from_vcs(vcs_instance: VCS):
        return kubernetes.client.models.V1Secret(
            metadata=kubernetes.client.models.V1ObjectMeta(
                name=vcs_instance.name,
                # namespace=vcs_instance.namespace,
                # labels={
                #     defs.LEGION_CRD_LABEL_TYPE: vcs_instance.KIND,
                #     defs.LEGION_CRD_OWNER_ID: vcs_instance.id,
                #     defs.LEGION_CRD_OWNER_NAME: vcs_instance.name
                # },
                annotations={
                    vcs_instance.ANNOTATION_URI: vcs_instance.uri,
                    vcs_instance.ANNOTATION_DEF_REF: vcs_instance.default_reference
                }
            ),
            data={
                'key': vcs_instance.private_key
            }
        )
