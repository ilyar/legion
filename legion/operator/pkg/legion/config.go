//
//    Copyright 2019 EPAM Systems
//
//    Licensed under the Apache License, Version 2.0 (the "License");
//    you may not use this file except in compliance with the License.
//    You may obtain a copy of the License at
//
//        http://www.apache.org/licenses/LICENSE-2.0
//
//    Unless required by applicable law or agreed to in writing, software
//    distributed under the License is distributed on an "AS IS" BASIS,
//    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//    See the License for the specific language governing permissions and
//    limitations under the License.
//

package legion

import (
	"fmt"
	"github.com/pkg/errors"
	"github.com/spf13/viper"
)

const (
	RepositoryURL          = "REPOSITORY_URL"
	PodName                = "POD_NAME"
	DockerRegistry         = "DOCKER_REGISTRY"
	SharedDirPath          = "SHARED_DIR_PATH"
	Reference              = "REFERENCE"
	ImagePrefix            = "BUILD_IMAGE_PREFIX"
	Namespace              = "NAMESPACE"
	GitSSHKeyPath          = "GIT_SSH_KEY_PATH"
	ModelFile              = "MODEL_FILE"
	ModelCommand           = "MODEL_COMMAND"
	BuilderImage           = "BUILDER_IMAGE"
	MetricHost             = "METRICS_HOST"
	MetricPort             = "METRICS_PORT"
	MetricEnabled          = "MODEL_CLUSTER_TRAIN_METRICS_ENABLED"
	PythonToolchainImage   = "PYTHON_TOOLCHAIN_IMAGE"
	DockerRegistryUser     = "DOCKER_REGISTRY_USER"
	DockerRegistryPassword = "DOCKER_REGISTRY_PASSWORD"
	JwtSecret              = "JWT_SECRET"
	JwtTtlMinutes          = "JWT_TTL_MINUTES"
	JwtMaxTtlMinutes       = "JWT_MAX_TTL_MINUTES"
	JwtExpDatetime         = "JWT_EXP_DATETIME"
	TemplateFolder         = "TEMPLATE_FOLDER"
	BuilderServiceAccount  = "BUILDER_SERVICE_ACCOUNT"
	WebhookSecretName      = "WEBHOOK_SECRET_NAME"
	WebhookServiceName     = "WEBHOOK_SERVICE_NAME"
	WebhookPort            = "WEBHOOK_PORT"
	MutatingWebhookName    = "MUTATING_WEBHOOK_NAME"
	ValidatingWebhookName  = "VALIDATING_WEBHOOK_NAME"
	LogFlushSize           = "LOG_FLUSH_SIZE"
	PrometheusMetricsPort  = "PROMETHEUS_METRICS_PORT"
	EdgeHost               = "EDGE_HOST"
	FeedbackEnabled        = "FEEDBACK_ENABLED"
	ModelTrainingName      = "MODEL_TRAINING_NAME"
	ModelOutputDataBinding = "MODEL_OUTPUT_DATA_BINDING"
	OutputTrainingDir      = "OUTPUT_TRAINING_DIR"
)

// TODO:
// It is just a first attempt of using viper
// Later we must to add default values and reading from a config file which mounts from k8s config map.
func SetUpBuilderConfig() {
	setNotEmptyParam(RepositoryURL)
	setNotEmptyParam(PodName)
	setNotEmptyParam(SharedDirPath)
	setNotEmptyParam(Reference)
	setNotEmptyParam(Namespace)
	setNotEmptyParam(GitSSHKeyPath)
	setNotEmptyParam(ModelTrainingName)
	setNotEmptyParam(ModelOutputDataBinding)
	setNotEmptyParam(OutputTrainingDir)
}

func SetUpOperatorConfig() {
	viper.SetConfigName("operator")

	setNotEmptyParam(BuilderImage)
	setNotEmptyParam(MetricHost)
	setNotEmptyParam(MetricPort)
	setNotEmptyParam(MetricEnabled)
	setNotEmptyParam(DockerRegistry)

	viper.SetDefault(ImagePrefix, "legion")
	panicIfError(viper.BindEnv(ImagePrefix))

	viper.SetDefault(BuilderServiceAccount, "legion-builder")
	panicIfError(viper.BindEnv(BuilderServiceAccount))

	panicIfError(viper.BindEnv(DockerRegistryUser))
	panicIfError(viper.BindEnv(DockerRegistryPassword))

	viper.SetDefault(Namespace, "legion")
	panicIfError(viper.BindEnv(Namespace))

	viper.SetDefault(PrometheusMetricsPort, 7777)
	panicIfError(viper.BindEnv(PrometheusMetricsPort))

	viper.SetDefault(PrometheusMetricsPort, 7777)
	panicIfError(viper.BindEnv(PrometheusMetricsPort))

	viper.SetDefault(EdgeHost, "https://edge.legion-test.epm.kharlamov.biz")
	panicIfError(viper.BindEnv(EdgeHost))

	viper.SetDefault(FeedbackEnabled, false)
	panicIfError(viper.BindEnv(FeedbackEnabled))
}

func SetUpWebhookConfig() {
	setNotEmptyParam(PythonToolchainImage)

	viper.SetDefault(Namespace, ";legion")
	panicIfError(viper.BindEnv(Namespace))

	viper.SetDefault(WebhookSecretName, "webhook-server-secret")
	panicIfError(viper.BindEnv(WebhookSecretName))

	viper.SetDefault(WebhookServiceName, "legion-webhook-server-service")
	panicIfError(viper.BindEnv(WebhookServiceName))

	viper.SetDefault(WebhookPort, 9876)
	panicIfError(viper.BindEnv(WebhookPort))

	viper.SetDefault(MutatingWebhookName, "legion-mutating-webhook-configuration")
	viper.SetDefault(ValidatingWebhookName, "legion-validating-webhook-configuration")

	viper.SetDefault(PrometheusMetricsPort, 7777)
	panicIfError(viper.BindEnv(PrometheusMetricsPort))
}

func SetUpEDIConfig() {
	viper.SetDefault(Namespace, "legion")
	panicIfError(viper.BindEnv(Namespace))

	viper.SetDefault(JwtTtlMinutes, 120)
	panicIfError(viper.BindEnv(JwtTtlMinutes))

	viper.SetDefault(JwtSecret, "")
	panicIfError(viper.BindEnv(JwtSecret))

	viper.SetDefault(JwtMaxTtlMinutes, 259200)
	panicIfError(viper.BindEnv(JwtMaxTtlMinutes))

	viper.SetDefault(JwtExpDatetime, "")
	panicIfError(viper.BindEnv(JwtExpDatetime))

	viper.SetDefault(TemplateFolder, "legion/operator/templates")
	panicIfError(viper.BindEnv(TemplateFolder))

	viper.SetDefault(LogFlushSize, 32)
	panicIfError(viper.BindEnv(LogFlushSize))
}

func setNotEmptyParam(paramName string) {
	panicIfError(viper.BindEnv(paramName))

	if !viper.IsSet(paramName) {
		panic(errors.New(fmt.Sprintf("The environment variable %s must be set", paramName)))
	}
}

func panicIfError(err error) {
	if err != nil {
		panic(err)
	}
}
