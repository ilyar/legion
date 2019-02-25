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
Controllers logic
"""
import logging
import threading

import kubernetes.client

import legion.k8s.crd.vcs
import legion.k8s.definitions as defs
import legion.k8s.watch
import legion.k8s.utils


LOGGER = logging.getLogger(__name__)


class CRDControllerCatcher:
    def __init__(self, crd_version, crd_plural, callback, constructor):
        self._thread = threading.Thread(target=self._catch,
                                        name='Controller logic thread')

        self._crd_version = crd_version
        self._crd_plural = crd_plural
        self._client = legion.k8s.utils.build_client()
        self._api = kubernetes.client.CustomObjectsApi(self._client)

        self._watch = legion.k8s.watch.ResourceWatch(
            self._api.list_cluster_custom_object,
            defs.LEGION_CRD_GROUP,
            crd_version,
            crd_plural,
            object_constructor=constructor
        )
        self._callback = callback

    def _catch(self):
        LOGGER.info('Starting Legion CRD {!r} {!r} monitoring'.format(self._crd_plural, self._crd_version))

        for event_type, event_object in self._watch.stream:
            self._callback(event_type, event_object)

    def run(self):
        return self._thread.run()

    def is_alive(self):
        return self._thread.is_alive()


class Controller:
    def __init__(self):
        self._monitors = []
        self._vcs_monitor = self._init_crd_monitor(legion.k8s.crd.vcs.VCS,
                                                   self.callback_vcs_crd)

    def _init_crd_monitor(self, crd_class, callback):
        monitor = CRDControllerCatcher(crd_class.VERSION,
                                       crd_class.PLURAL,
                                       callback,
                                       crd_class)
        self._monitors.append(monitor)
        return monitor

    def run(self) -> None:
        for monitor in self._monitors:
            monitor.run()

    def is_alive(self) -> bool:
        return all(monitor.is_alive() for monitor in self._monitors)

    def callback_vcs_crd(self, event_type: str, event_object: dict):
        x = 10
        if event_type == defs.EVENT_ADDED:
            pass
        elif event_type == defs.EVENT_MODIFIED:
            pass
        elif event_type == defs.EVENT_DELETED:
            pass

    def callback_model_trainings(self, event_type: str, event_object: dict):
        x = 20
