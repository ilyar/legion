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
Flask app
"""

import logging

from flask import Flask, Blueprint

import legion.config
import legion.external.grafana
import legion.http
import legion.k8s
import legion.k8s.utils
import legion.model
import legion.controller.controller
import legion.controller.crd_controllers


LOGGER = logging.getLogger(__name__)
blueprint = Blueprint('controller', __name__)


@blueprint.route('/', methods=['GET'])
@legion.http.provide_json_response
def root():
    """
    Root endpoint for health-checks

    :return: dict -- root information
    """
    return {'status': 'OK'}


def create_application():
    """
    Create Flask application, register blueprints

    :return: :py:class:`Flask.app` -- Flask application instance
    """
    application = Flask(__name__,
                        static_url_path='')
    application.register_blueprint(blueprint)

    return application


def init_application(args=None):
    """
    Initialize configured Flask application instance
    Overall configuration priority: config_default.py, env::FLASK_APP_SETTINGS_FILES file,
    ENV parameters, CLI parameters

    :param args: arguments if provided
    :type args: :py:class:`argparse.Namespace` or None
    :return: :py:class:`Flask.app` -- application instance
    """
    application = create_application()
    legion.http.configure_application(application, args)

    # controller = legion.controller.controller.Controller()
    # controller.run()

    k8s_client = legion.k8s.utils.build_client()
    for controller in legion.controller.crd_controllers.ALL_CONTROLLERS:
        controller_instance = controller(k8s_client)
        controller_instance.run()

    return application


def serve(args):
    """
    Serve controller

    :param args: arguments
    :type args: :py:class:`argparse.Namespace`
    :return: None
    """
    logging.info('Legion controller server initializing')
    application = init_application(args)

    try:
        application.run(host=application.config['LEGION_API_ADDR'],
                        port=application.config['LEGION_API_PORT'],
                        debug=application.config['DEBUG'],
                        use_reloader=False)

        return application
    except Exception as run_exception:
        LOGGER.exception('EDI server exited with exception', exc_info=run_exception)
