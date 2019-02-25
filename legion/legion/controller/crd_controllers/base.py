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
legion Base Controller for CRD
"""
import copy
import threading
import typing
import logging

import kubernetes.client

import legion.k8s.crd
import legion.k8s.watch
import legion.k8s.definitions as defs
import legion.controller.crd_controllers.merge

from .definitions import *

LOGGER = logging.getLogger(__name__)


def build_selector_string(filter_dict: dict) -> str:
    return ','.join('{}={}'.format(*pair) for pair in filter_dict.items())


class CRDController:
    TARGET_CRD_CLASS: legion.k8s.crd.BaseCRD = None
    MONITOR_CHILD: bool = False
    CHILD_TYPES: typing.List[ChildReferenceDeclaration] = None

    def __init__(self, k8s_client):
        self._k8s_client = k8s_client

        self._threads = []
        self._crd_watch_thread = None
        self._build_watch_thread()

    def _build_watch_thread(self) -> None:
        self._crd_watch_thread = threading.Thread(target=self._crd_monitor_thread,
                                                  name='Monitor for tracking {} changes'.format(self.TARGET_CRD_CLASS))
        self._threads.append(self._crd_watch_thread)

    def run(self):
        for thread in self._threads:
            thread.run()

    @property
    def threads(self):
        return self.threads

    def _find_child_instances(self, namespace: str, crd_id: str) -> ChildInstanceCollection:
        buffer = []

        for child_type in self.CHILD_TYPES:
            for instance in self._find_child_instances_with_type(child_type, namespace, crd_id):
                buffer.append(ChildInstancePair(child_type.type,
                                                instance.metadata.labels.get(defs.LEGION_CRD_SUB_NAME),
                                                instance))

        return tuple(buffer)

    def _find_child_instances_with_type(self,
                                        child_type: ChildReferenceDeclaration,
                                        namespace: str,
                                        crd_id: str) -> typing.Tuple[object]:
        label_selector = build_selector_string({
            defs.LEGION_CRD_OWNER_ID: crd_id,
            defs.LEGION_CRD_OWNER_TYPE: self.TARGET_CRD_CLASS.KIND
        })

        api = child_type.api_group(self._k8s_client)
        listing_function = 'list_namespaced_{}'.format(child_type.singular)
        listing_function_instance = getattr(api, listing_function)
        instances = listing_function_instance(namespace=namespace,
                                              label_selector=label_selector).items
        return tuple(instances)

    def _get_namespaced_cr(self, crd_type: type, namespace: str, crd_name: str):
        api = kubernetes.client.CustomObjectsApi(self._k8s_client)
        dict_value = api.get_namespaced_custom_object(
            defs.LEGION_CRD_GROUP,
            crd_type.VERSION,
            namespace,
            crd_type.PLURAL,
            crd_name
        )
        return crd_type(dict_value)

    def _crd_monitor_thread(self):
        api = kubernetes.client.CustomObjectsApi(self._k8s_client)
        watch = legion.k8s.watch.ResourceWatch(
            api.list_cluster_custom_object,
            defs.LEGION_CRD_GROUP,
            self.TARGET_CRD_CLASS.VERSION,
            self.TARGET_CRD_CLASS.PLURAL,
            object_constructor=self.TARGET_CRD_CLASS
        )

        for event_type, event_object in watch.stream:  # type: (str, legion.k8s.crd.BaseCRD)
            desired_state = None
            actual_child = tuple()

            if event_object.uid:
                actual_child = self._find_child_instances(event_object.namespace, event_object.uid)

            if event_type == defs.EVENT_ADDED:
                desired_state = self.on_create(event_object, actual_child)
            elif event_type == defs.EVENT_MODIFIED:
                desired_state = self.on_update(event_object, actual_child)
            elif event_type == defs.EVENT_DELETED:
                desired_state = self.on_delete(event_object, actual_child)
            else:
                LOGGER.error('Unknown event {!r} for object {!r}'.format(event_type, event_object))

            if desired_state is not None:
                self._synchronize_state_of_crd(event_object, actual_child, desired_state)
            else:
                LOGGER.debug('Any actions are ignored: desired state is None')

    def _update_crd_status(self, event_object: legion.k8s.crd.BaseCRD, new_status: dict) -> None:
        api = kubernetes.client.CustomObjectsApi(self._k8s_client)
        new_body = copy.deepcopy(event_object.k8s_instance)
        if 'status' not in new_body:
            new_body['status'] = dict()

        new_body['status'].update(new_status)

        api.patch_namespaced_custom_object(
            defs.LEGION_CRD_GROUP,
            self.TARGET_CRD_CLASS.VERSION,
            event_object.namespace,
            self.TARGET_CRD_CLASS.PLURAL,
            event_object.name,
            new_body
        )

    def _get_info_about_child_instance(self, instance_type: type) -> ChildReferenceDeclaration:
        for item in self.CHILD_TYPES:
            if item.type == instance_type:
                return item

        raise Exception('Unknown type {}'.format(instance_type))

    def _remove_child_instance(self, event_object: legion.k8s.crd.BaseCRD, instance: ChildInstancePair) -> None:
        decl = self._get_info_about_child_instance(instance.type)

        api = decl.api_group(self._k8s_client)
        delete_function = 'delete_namespaced_{}'.format(decl.singular)
        delete_function_instance = getattr(api, delete_function)

        delete_options = kubernetes.client.V1DeleteOptions(
            grace_period_seconds=0
        )

        LOGGER.debug('Removing from namespace {!r} resource {} '.format(event_object.namespace, instance.name))
        result = delete_function_instance(instance.instance.metadata.name, event_object.namespace, delete_options)
        LOGGER.debug('Resource deleted: {}'.format(result))

    def _add_child_instance(self, event_object: legion.k8s.crd.BaseCRD, instance: ChildInstancePair) -> None:
        decl = self._get_info_about_child_instance(instance.type)
        k8s_instance = instance.instance
        k8s_hash = legion.controller.crd_controllers.merge.compute_k8s_object_hash(k8s_instance)

        if k8s_instance.metadata.labels is None:
            k8s_instance.metadata.labels = {}

        k8s_instance.metadata.labels[defs.LEGION_CRD_OWNER_ID] = event_object.uid
        k8s_instance.metadata.labels[defs.LEGION_CRD_OWNER_TYPE] = self.TARGET_CRD_CLASS.KIND
        k8s_instance.metadata.labels[defs.LEGION_CRD_OWNER_NAME] = event_object.name
        k8s_instance.metadata.labels[defs.LEGION_CRD_SUB_NAME] = instance.name
        k8s_instance.metadata.labels[defs.LEGION_CRD_CHILD_REVISION] = k8s_hash

        api = decl.api_group(self._k8s_client)
        create_function = 'create_namespaced_{}'.format(decl.singular)
        create_function_instance = getattr(api, create_function)

        LOGGER.debug('Creating in namespace {!r} resource {} '.format(event_object.namespace, instance.name))
        result = create_function_instance(event_object.namespace, k8s_instance)
        LOGGER.debug('Resource created: {}'.format(result))

    def _inplace_update_child_instance(self, event_object: legion.k8s.crd.BaseCRD, instance: ChildInstancePair) -> None:
        decl = self._get_info_about_child_instance(instance.type)
        k8s_instance = instance.instance
        k8s_hash = legion.controller.crd_controllers.merge.compute_k8s_object_hash(k8s_instance)

        if k8s_instance.metadata.labels is None:
            k8s_instance.metadata.labels = {}
        k8s_instance.metadata.labels[defs.LEGION_CRD_CHILD_REVISION] = k8s_hash

        api = decl.api_group(self._k8s_client)
        patch_function = 'patch_namespaced_{}'.format(decl.singular)
        patch_function_instance = getattr(api, patch_function)

        LOGGER.debug('Updating in namespace {!r} resource {} '.format(event_object.namespace, instance.name))
        result = patch_function_instance(k8s_instance.metadata.name, event_object.namespace, k8s_instance)
        LOGGER.debug('Resource created: {}'.format(result))

    def _synchronize_state_of_crd(self,
                                  event_object: legion.k8s.crd.BaseCRD,
                                  actual_child: ChildInstanceCollection,
                                  desired_state: DesiredState):

        merge_result = legion.controller.crd_controllers.merge.merge(event_object,
                                                                     actual_child,
                                                                     desired_state,
                                                                     self.CHILD_TYPES)

        # 1st - Update status
        if merge_result.state_update:
            self._update_crd_status(event_object, merge_result.state_update)

        # 2nd remove instances
        for instance in merge_result.remove_child:
            self._remove_child_instance(event_object, instance)

        # 3rd create instances
        for instance in merge_result.create_child:
            self._add_child_instance(event_object, instance)

        # 4th inplace update instances
        for instance in merge_result.inplace_update_child:
            self._inplace_update_child_instance(event_object, instance)

    def on_create(self, crd_instance: legion.k8s.crd.BaseCRD, actual_child: ChildInstanceCollection) -> DesiredState:
        return self.on_update(crd_instance, actual_child)

    def on_update(self, crd_instance: legion.k8s.crd.BaseCRD, actual_child: ChildInstanceCollection) -> DesiredState:
        raise NotImplementedError('on_update function of {} is not implemented'.format(self.__class__.__name__))

    def on_delete(self, crd_instance: legion.k8s.crd.BaseCRD, actual_child: ChildInstanceCollection) -> DesiredState:
        return DesiredState(child=None,
                            status=None)

    def on_child_update(self, child_instance):
        pass
