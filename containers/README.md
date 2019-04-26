## Directory information

This directory contains all Legion components that are distributed as docker images.

### Components
* **edge** is a model API Gateway based on OpenResty. [Details in documentation](../docs/source/edge.md)
* **edi** is a service which allows managing model deployments inside Kubernetes. [Details in documentation](../docs/source/edi.md)
* **fluentd** is a `fluentd-elasticsearch` image with S3 plugin. [Details in documentation](../docs/source/feedback-loop.md)
* **operator** is a handler for Legion's custom resources. [Details in documentation](../docs/source/legion-crds.md)
* **pipeline-agent** is a docker image for CI/CD process. Inside this Docker image almost all build stages are being executed.
* **toolchains** contains implementation of toolchains (model extension API) for each supported platform. [Details in documentation](../docs/source/toolchains.md)


## How to build
### Using Makefile
To build these images you may use Makefile from the root folder of repository.

* To build all images call `make build-all-docker-images`
* To build some images call `make build-docker-edi` (`build-docker-<name of folder>`)

### Manually
If you want to build these images without Make, you have to run `docker build` command from the root repository's context (e.g. `docker build -t legionplatform/k8s-edi:latest -f containers/edi/Dockerfile .`)