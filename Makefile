SHELL := /bin/bash

PROJECTNAME := $(shell basename "$(PWD)")
PYLINT_FOLDER=target/pylint
PYDOCSTYLE_FOLDER=target/pydocstyle
PROJECTS_PYLINT=sdk cli services toolchain tests
PROJECTS_PYCODESTYLE="sdk cli services toolchain"
BUILD_PARAMS=
LEGION_VERSION=0.11.0
SANDBOX_PYTHON_TOOLCHAIN_IMAGE=
CREDENTIAL_SECRETS=.secrets.yaml
ROBOT_FILES=**/*.robot
CLUSTER_NAME=
PATH_TO_PROFILES_DIR=profiles
E2E_PYTHON_TAGS=
COMMIT_ID=
TEMP_DIRECTORY=
TAG=

-include .env

.EXPORT_ALL_VARIABLES:

.PHONY: install-all install-cli install-services install-sdk

all: install-all

## install-all: Install all python packages
install-all: install-sdk install-services install-cli install-python-toolchain install-robot

## install-sdk: Install sdk python package
install-sdk:
	cd legion/sdk && \
		pip3 install ${BUILD_PARAMS} -e . && \
		python setup.py sdist && \
    	python setup.py bdist_wheel

## install-cli: Install cli python package
install-cli:
	cd legion/cli && \
		pip3 install ${BUILD_PARAMS} -e . && \
		python setup.py sdist && \
    	python setup.py bdist_wheel

## install-services: Install services python package
install-services:
	cd legion/services && \
		pip3 install ${BUILD_PARAMS} -e . && \
		python setup.py sdist && \
    	python setup.py bdist_wheel

## install-python-toolchain: Install python toolchain
install-python-toolchain:
	cd legion/toolchains/python && \
		pip3 install ${BUILD_PARAMS} -e . && \
		python setup.py sdist && \
    	python setup.py bdist_wheel

## install-robot: Install robot tests
install-robot:
	cd legion/robot && \
		pip3 install ${BUILD_PARAMS} -e . && \
		python setup.py sdist && \
    	python setup.py bdist_wheel

## build-all-docker-images: build all docker images
build-all-docker-images: build-docker-edge build-docker-edi build-docker-fluentd build-docker-operator build-docker-pipeline-agent build-docker-toolchains

## dbuild-docker-edge: Build edge docker image
build-docker-edge:
	docker build -t legion/k8s-edge:latest -f containers/edge/Dockerfile .

## build-docker-edi: Build edi docker image
build-docker-edi:
	docker build -t legion/k8s-edi:latest -f containers/edi/Dockerfile .

## build-docker-fluentd: Build edi docker image
build-docker-fluentd:
	docker build -t legion/k8s-fluentd:latest -f containers/fluentd/Dockerfile .

## build-docker-operator: Build all operator's docker images
build-docker-operator: build-docker-operator-server build-docker-operator-model-builder

## build-docker-operator-server: Build operator server docker image
build-docker-operator-server:
	docker build --target operator -t legion/k8s-operator:latest -f containers/operator/Dockerfile .

## build-docker-operator-model-builder: Build model builder docker image (operator's sidecar)
build-docker-operator-model-builder:
	docker build --target model-builder -t legion/k8s-model-builder:latest -f containers/operator/Dockerfile .

## build-docker-pipeline-agent: Build pipeline agent docker image
build-docker-pipeline-agent:
	docker build -t legion/python-pipeline:latest -f containers/pipeline/Dockerfile .

## build-docker-toolchains: Build all toolchains
build-docker-toolchains: build-docker-python-toolchain

## build-docker-python-toolchain: Build python toolchain docker image
build-docker-python-toolchain:
	docker build -t legion/python-toolchain:latest -f containers/toolchains/python/Dockerfile .

## push-model-builder: Push model builder docker image
push-model-builder:
	@if [ "${TAG}" == "" ]; then \
	    echo "TAG not defined, please define TAG variable" ; exit 1 ;\
	fi
	docker tag legion/k8s-model-builder:latest nexus.cc.epm.kharlamov.biz:443/legion/k8s-model-builder:${TAG}
	docker push nexus.cc.epm.kharlamov.biz:443/legion/k8s-model-builder:${TAG}

## push-operator: Push operator docker image
push-operator:
	@if [ "${TAG}" == "" ]; then \
	    echo "TAG not defined, please define TAG variable" ; exit 1 ;\
	fi
	docker tag legion/k8s-operator:latest nexus.cc.epm.kharlamov.biz:443/legion/k8s-operator:${TAG}
	docker push nexus.cc.epm.kharlamov.biz:443/legion/k8s-operator:${TAG}

## install-unittests: Install unit tests
install-unittests:
	cd legion/tests/unit/requirements/ && pipenv install

## lint: Lints source code
lint:
	scripts/lint.sh

## build-docs: Build legion docs
build-docs: build-docs-builder
	docker run --rm -v $(PWD)/docs:/var/docs --workdir /var/docs legion/docs-builder:latest /generate.sh


## build-docs-builder: Build docker image that can build documentation
build-docs-builder:
	docker build -t legion/docs-builder:latest -f containers/docs-builder/Dockerfile .

## unittests: Run unit tests
unittests:
	@if [ "${SANDBOX_PYTHON_TOOLCHAIN_IMAGE}" == "" ]; then \
	    docker build -t legion/python-toolchain:latest -f containers/toolchains/python/Dockerfile . ;\
	fi

	mkdir -p target
	mkdir -p target/cover

	DEBUG=true VERBOSE=true nosetests --processes=10 \
	          --process-timeout=600 \
	          --with-coverage \
	          --cover-package legion \
	          --with-xunitmp \
	          --xunitmp-file target/nosetests.xml \
	          --cover-xml \
	          --cover-xml-file=target/coverage.xml \
	          --cover-html \
	          --cover-html-dir=target/cover \
	          --logging-level DEBUG \
	          -v legion/tests/unit

## e2e-robot: Run e2e robot tests
e2e-robot:
	pabot --verbose --processes 6 \
	      -v PATH_TO_PROFILES_DIR:profiles \
	      --listener legion.robot.process_reporter \
	      --outputdir target legion/tests/e2e/robot/tests/${ROBOT_FILES}

## e2e-python: Run e2e python tests
e2e-python:
	mkdir -p target
	nosetests ${E2E_PYTHON_TAGS} --with-xunitmp \
	          --logging-level DEBUG \
	          --xunitmp-file target/nosetests.xml \
	          -v legion/tests/e2e/python

## update-python-deps: Update all python dependecies in the Pipfiles
update-python-deps:
	scripts/update_python_deps.sh

help: Makefile
	@echo "Choose a command run in "$(PROJECTNAME)":"
	@sed -n 's/^##//p' $< | column -t -s ':' |  sed -e 's/^/ /'
	@echo
