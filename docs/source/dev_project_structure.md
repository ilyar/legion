# Project structure

## What is it inside Legion?
Core:
* Python 3.6 – as main development language
* Ansible – as tool for implementing infra-as-a-code
* Kubernetes – as runtime platform
* Docker – as containerization engine for runtime platform
* Grafana – as metrics dashboard
* Prometheus – as storage for cluster metrics
* FluentD – as logging aggregator for cluster logs and feedback loop
* EDGE – as model API traffic manager
* EDI – model manager
* Toolchains - APIs for adding to ML Legion capabilities

Optional:
* Airflow – as optional ETL engine


# Repositories structure
## Legion
Project **Legion** locates in GitHub Repository [legion-platform/legion](https://github.com/legion-platform/legion) and contains of next items:

* Legion application - several Docker images:
  * EDI
  * EDGE
  * FluentD
  * Toolchain application
* HELM packages:
  * legion-core HELM chart
  * legion HELM chart
* Legion Python source codes
* Legion Operator (not released yet)

### Legion's repository directory structure
* `containers` - all Legion components that are distributed as docker images. [Details](containers/README.md)
* `docs` - documentation that describes Legion platform, architecture, usage and etc.
* `examples` - examples of machine learning models that could be trained and deployed in Legion, examples base on public available models (such as sklearn digit classifier, MovieLens model, Logistic Regression classifier on Census Income Data) and some syntetic models. [Details](examples/README.md)
* `helms` - Legion Helm packages (distribution packages for Kubernetes).
* `legion` - source code of Legion python packages.
* `scripts` - utilitary scripts for CI/CD process.

## Infra-specific repositories
For deploying purposes there are platform-specific repositories that contains platform-specific deploying logic.

**Legion AWS** locates in GitHub Repository [legion-platform/legion-aws](https://github.com/legion-platform/legion-aws) and contains:
* Ansible playbooks
* Jenkinsfiles for Jenkins CI/CD jobs
* Infrastructure specific containers:
  * Ansible
  * Kube-elb-security - kubernetes controller that creates AWS security group rules for service ELB like ingress-nginx with granding access from all kubernetes nodes. It is useful if your services with Type LoadBalancer having firewall restrictions.
  * Kube-fluentd
  * Oauth2-proxy

## Additional integrations repositories

