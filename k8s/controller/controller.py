from flask import Flask, request, jsonify

application = Flask(__name__)


def build_model_deployment_service(name, namespace):
    return {
        'kind': 'Service',
        'apiVersion': 'v1',
        'metadata': {
            'name': name,
            'namespace': namespace,
        },
        'spec': {
            'ports': [
                {
                    'name': 'api',
                    'protocol': 'TCP',
                    'port': 5000,
                    'targetPort': 'api'
                }
            ],
            'selector': {
                'legion.model-deployment-name': name
            },
            'type': 'ClusterIP'
        }
    }


def build_model_deployment_deployment(name, namespace, image, replicas):
    return {
        'kind': 'Deployment',
        'apiVersion': 'extensions/v1beta1',
        'metadata': {
            'name': name,
            'namespace': namespace,
            'labels': {
                'legion.model-deployment-name': name
            },
        },
        'spec': {
            'replicas': replicas,
            'selector': {
                'matchLabels': {
                    'legion.model-deployment-name': name
                }
            },
            'template': {
                'metadata': {
                    'labels': {
                        'legion.model-deployment-name': name
                    },
                },
                'spec': {
                    'containers': [
                        {
                            'name': 'model',
                            'image': image,
                            'ports': [
                                {
                                    'name': 'api',
                                    'containerPort': 5000,
                                    'protocol': 'TCP'
                                }
                            ],
                            'env': [
                                {
                                    'name': 'STATSD_HOST',
                                    'value': 'legion-company-a-graphite.company-a'
                                },
                                {
                                    'name': 'STATSD_PORT',
                                    'value': '80'
                                }
                            ],
                            'resources': {},
                            'livenessProbe': {
                                'httpGet': {
                                    'path': '/healthcheck',
                                    'port': 5000,
                                    'scheme': 'HTTP'
                                },
                                'initialDelaySeconds': 2,
                                'timeoutSeconds': 2,
                                'periodSeconds': 10,
                                'successThreshold': 1,
                                'failureThreshold': 10
                            },
                            'readinessProbe': {
                                'httpGet': {
                                    'path': '/healthcheck',
                                    'port': 5000,
                                    'scheme': 'HTTP'
                                },
                                'initialDelaySeconds': 2,
                                'timeoutSeconds': 2,
                                'periodSeconds': 10,
                                'successThreshold': 1,
                                'failureThreshold': 5
                            },
                            'imagePullPolicy': 'IfNotPresent'
                        }
                    ],
                    'terminationGracePeriodSeconds': 30,
                    'serviceAccountName': 'model',
                    'serviceAccount': 'model'
                }
            }
        },
    }


def build_model_deployment_resources(name, namespace, image, replicas):
    return [
        build_model_deployment_service(name, namespace),
        build_model_deployment_deployment(name, namespace, image, replicas)
    ]


@application.route('/sync-model', methods=['POST'])
def hello_world():
    json_request = request.json

    parent = json_request['parent']
    children = json_request['children']
    finalizing = json_request['finalizing']

    deployment_spec = parent['spec']

    return jsonify(
        status={},
        children=build_model_deployment_resources(parent['metadata']['name'],
                                                  parent['metadata']['namespace'],
                                                  deployment_spec['image'],
                                                  deployment_spec['replicas'])
    )
