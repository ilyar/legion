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

package builder

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/hpcloud/tail"
	legionv1alpha1 "github.com/legion-platform/legion/legion/operator/pkg/apis/legion/v1alpha1"
	"github.com/legion-platform/legion/legion/operator/pkg/builder/data"
	"github.com/legion-platform/legion/legion/operator/pkg/legion"
	"github.com/legion-platform/legion/legion/operator/pkg/utils"
	"github.com/pkg/errors"
	"github.com/spf13/viper"
	"io/ioutil"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/kubernetes"
	"math/rand"
	"os"
	"path"
	"sigs.k8s.io/controller-runtime/pkg/client"
	logf "sigs.k8s.io/controller-runtime/pkg/runtime/log"
	"strconv"
	"syscall"
	"time"
)

var (
	log                 = logf.Log.WithName("builder")
	logModel            = logf.Log.WithName("model")
	trainingSleepPeriod = 3 * time.Second
)

const (
	beginningOfContainerId = "docker://"
	modelTrainingFile      = "mt.yaml"
	stdoutPipe             = "dev.stdout"
	trainingPidFile        = "training.pid"
)

type ModelBuilder struct {
	clientset            *kubernetes.Clientset
	k8sClient            client.Client
	modelTraining        *legionv1alpha1.ModelTraining
	toolchainIntegration *legionv1alpha1.ToolchainIntegrationSpec
}

func NewModelBuilder() (*ModelBuilder, error) {
	manager, err := utils.NewManager()
	if err != nil {
		return nil, err
	}
	k8sClient := manager.GetClient()

	clientset, err := kubernetes.NewForConfig(manager.GetConfig())

	if err != nil {
		log.Error(err, "Can't create k8s client")
		return nil, err
	}

	modelTraining := &legionv1alpha1.ModelTraining{}
	if err := k8sClient.Get(context.TODO(), types.NamespacedName{
		Name:      viper.GetString(legion.ModelTrainingName),
		Namespace: viper.GetString(legion.Namespace),
	}, modelTraining); err != nil {
		return nil, err
	}

	toolchainInteg := &legionv1alpha1.ToolchainIntegration{}
	if err := k8sClient.Get(context.TODO(), types.NamespacedName{
		Name:      modelTraining.Spec.Toolchain,
		Namespace: viper.GetString(legion.Namespace),
	}, toolchainInteg); err != nil {
		return nil, err
	}

	return &ModelBuilder{
		clientset:            clientset,
		k8sClient:            k8sClient,
		modelTraining:        modelTraining,
		toolchainIntegration: &toolchainInteg.Spec,
	}, nil
}

// ModelConfig build contains the following steps:
//   1) Download specified git repository to the shared directory between model and builder pods
//   2) Start model entrypoint script\playbook
//   3) Extract model information from model file and save in annotations of current pod
//   3) Launch legionctl command to build a model docker image
func (mb *ModelBuilder) Start() (err error) {
	commitID, err := utils.CloneUserRepo(
		viper.GetString(legion.SharedDirPath),
		viper.GetString(legion.RepositoryURL),
		viper.GetString(legion.GitSSHKeyPath),
		viper.GetString(legion.Reference),
	)
	if err != nil {
		log.Error(err, "Error occurs during cloning project")
		return err
	}

	if err := mb.updateAnnotations(map[string]string{legion.ModelCommitID: commitID}); err != nil {
		log.Error(err, "Cannot save the commit id")
	}

	log.Info("Change current working dir", "new worker dir", viper.GetString(legion.SharedDirPath))
	if err := os.Chdir(viper.GetString(legion.SharedDirPath)); err != nil {
		log.Error(err, "Changing current working dir failed", "new worker dir", viper.GetString(legion.SharedDirPath))
		return err
	}

	if err := mb.downloadData(); err != nil {
		log.Error(err, "Downloading training data failed", "mt name", mb.modelTraining.Name)
		return err
	}

	mtBytes, err := json.Marshal(mb.modelTraining)
	if err != nil {
		return err
	}

	err = ioutil.WriteFile(modelTrainingFile, mtBytes, 0644)
	if err != nil {
		return err
	}

	stdoutFile := path.Join(viper.GetString(legion.SharedDirPath), stdoutPipe)
	trainingPidFile := path.Join(viper.GetString(legion.SharedDirPath), trainingPidFile)

	if err := mb.startTraining(trainingPidFile, stdoutFile); err != nil {
		log.Error(err, "Starting of training failed")

		return err
	}

	if err := mb.waitTrainingFinish(trainingPidFile); err != nil {
		return err
	}

	outputZipName := fmt.Sprintf("%s-%s-%s.zip", mb.modelTraining.Name, mb.modelTraining.ResourceVersion,
		commitID)

	log.Info("Start to zip the dir", "dir", viper.GetString(legion.OutputTrainingDir), "archive name",
		outputZipName)
	err = utils.ZipDir(viper.GetString(legion.OutputTrainingDir), outputZipName)
	if err != nil {
		log.Info("Zipping the dir failed", "dir", viper.GetString(legion.OutputTrainingDir), "archive name",
			outputZipName)
		return err
	}

	if err := mb.saveResult(outputZipName); err != nil {
		return err
	}

	if err := mb.updateAnnotations(map[string]string{
		legion.TrainingOutputZip:         outputZipName,
		legion.TrainingOutputDataBinding: viper.GetString(legion.ModelOutputDataBinding),
	}); err != nil {
		log.Error(err, "Cannot save the annotations on pod")
	}

	return
}

func (mb *ModelBuilder) startTraining(pidFile, stdoutFile string) error {
	if _, err := os.Stat(stdoutFile); !os.IsNotExist(err) {
		log.Info("The named pipe has already existed. Deleting it", "path", stdoutFile)

		if err := os.Remove(stdoutFile); err != nil {
			return err
		}
	}

	log.Info("Creating named pipe", "path", stdoutFile)
	err := syscall.Mkfifo(stdoutFile, 0777)
	if err != nil {
		return err
	}

	// Start log streaming
	go func() {
		t, err := tail.TailFile(stdoutFile, tail.Config{Follow: true, Pipe: true})
		if err != nil {
			log.Error(err, "Failed to start log streaming", "pipe", stdoutFile)

			return
		}

		log.Info("Starting logs streaming")

		for line := range t.Lines {
			logModel.Info(line.Text)
		}
	}()

	if _, err := os.Stat(legion.OutputTrainingDir); !os.IsNotExist(err) {
		log.Info("The output dir has already existed. Deleting it", "output dir", legion.OutputTrainingDir)

		if err := os.Remove(stdoutFile); err != nil {
			return err
		}
	}

	commands := []string{
		"/bin/bash", "-c",
		fmt.Sprintf("cd %s && %s --mt %s --target %s --pid-file %s &> %s &",
			viper.GetString(legion.SharedDirPath),
			mb.toolchainIntegration.Entrypoint,
			modelTrainingFile,
			viper.GetString(legion.OutputTrainingDir),
			pidFile,
			stdoutFile,
		),
	}

	if err := mb.execInModelPod(commands); err != nil {
		log.Error(err, "Error occurs during execution of model command")
		return err
	}

	return nil
}

func checkModelTrainingResult(pidFile string) (int, error) {
	bytesPidFile, err := ioutil.ReadFile(pidFile)
	if err != nil {
		log.Error(err, "Can't open pid file")
		return 0, err
	}

	stringPidFile := string(bytesPidFile)
	code, err := strconv.Atoi(stringPidFile)
	if err != nil {
		log.Error(err, "Can't decode int", "content", stringPidFile, "pid file", pidFile)
		return 0, err
	}

	return code, err
}

func (mb *ModelBuilder) waitTrainingFinish(pidFile string) error {
	for {
		log.Info("Sleeping")
		time.Sleep(trainingSleepPeriod)

		if _, err := os.Stat(pidFile); os.IsNotExist(err) {
			log.Info("Not exist")
			continue
		}

		trainingResult, err := checkModelTrainingResult(pidFile)
		if err != nil {
			return err
		}

		if trainingResult > 0 {
			commands := []string{"/bin/bash", "-c", fmt.Sprintf("ps -p %d", trainingResult)}

			// TODO: validate k8s errors!! We should return some value if training process failed
			if err := mb.execInModelPod(commands); err != nil {
				log.Error(err, "Training ends")

				trainingResult, err := checkModelTrainingResult(pidFile)
				if err != nil {
					return err
				}

				if trainingResult == 0 {
					return nil
				}

				return errors.New("Training process failed")
			}
		} else if trainingResult < 0 {
			return errors.New("Training process failed")
		} else {
			log.Info("Training finished successfully")
			return nil
		}
	}
}

func (mb *ModelBuilder) saveResult(zipName string) error {
	dataBinding := &legionv1alpha1.DataBinding{}
	if err := mb.k8sClient.Get(context.TODO(), types.NamespacedName{
		Name:      viper.GetString(legion.ModelOutputDataBinding),
		Namespace: viper.GetString(legion.Namespace),
	}, dataBinding); err != nil {
		return err
	}

	storage := data.NewObjectStorage(&dataBinding.Spec)
	if err := storage.UploadFile(zipName); err != nil {
		return err
	}

	return nil
}

func (mb *ModelBuilder) downloadData() error {
	if len(mb.modelTraining.Spec.Data) == 0 {
		log.Info("Model training data is empty. Skip downloading", "mt name")

		return nil
	}
	for _, mtData := range mb.modelTraining.Spec.Data {
		log.Info("Start download training data", "mt name", mb.modelTraining.Name,
			"data binding dir", mtData)

		dataBindingSpec := mtData.DataBinding
		if mtData.DataBindingName != nil {
			dataBinding := &legionv1alpha1.DataBinding{}
			if err := mb.k8sClient.Get(context.TODO(), types.NamespacedName{
				Name:      *mtData.DataBindingName,
				Namespace: viper.GetString(legion.Namespace),
			}, dataBinding); err != nil {
				return err
			}

			dataBindingSpec = &dataBinding.Spec
		}

		storage := data.NewObjectStorage(dataBindingSpec)
		if err := storage.DownloadFile(mtData.Dir); err != nil {
			return err
		}
	}

	return nil
}

func (mb *ModelBuilder) updateAnnotations(newAnnotations map[string]string) error {
	podApi := mb.clientset.CoreV1().Pods(viper.GetString(legion.Namespace))
	pod, err := podApi.Get(viper.GetString(legion.PodName), metav1.GetOptions{})
	if err != nil {
		log.Error(err, "Getting the current pod")
		return err
	}

	annotations := pod.GetObjectMeta().GetAnnotations()
	if annotations == nil {
		annotations = make(map[string]string, 1)
	}

	for k, v := range newAnnotations {
		annotations[k] = v
	}

	pod.ObjectMeta.Annotations = annotations
	_, err = podApi.Update(pod)

	return err
}

func (mb *ModelBuilder) execInModelPod(commands []string) (err error) {
	config, err := utils.GetClientConfig()
	if err != nil {
		return err
	}

	log.Info("Execute remote command", "pod name", viper.GetString(legion.PodName), "container name",
		"model", "command", commands)
	err = utils.ExecToPodThroughAPI(
		commands, "model", viper.GetString(legion.PodName), viper.GetString(legion.Namespace), config,
	)

	if err != nil {
		log.Error(err, "Execute command in model pod")
		return err
	}

	return
}

func (mb *ModelBuilder) getModelContainerID() (result string, err error) {
	pod, err := mb.clientset.CoreV1().Pods(viper.GetString(legion.Namespace)).Get(
		viper.GetString(legion.PodName), metav1.GetOptions{},
	)

	if err != nil {
		log.Error(err, "Can't get pod %s", pod.Name)
		return "", err
	}

	for _, container := range pod.Status.ContainerStatuses {
		if container.Name == "model" {
			return container.ContainerID[len(beginningOfContainerId):], nil
		}
	}

	return "", errors.New("Can't find container with `model` name")
}

func (mb *ModelBuilder) buildModel(model legion.Model) (err error) {
	containerID, err := mb.getModelContainerID()

	if err != nil {
		return err
	}

	localImageTag := fmt.Sprintf("legion_ci_%s_%s_%d", model.Name, model.Version, rand.Int())
	externalImageTag := legion.BuildModelImageName(viper.GetString(legion.DockerRegistry), viper.GetString(legion.ImagePrefix),
		model.Name, model.Version)

	// It's a hack to return the model information
	err = mb.updateAnnotations(map[string]string{
		legion.ModelImageKey:   externalImageTag,
		legion.ModelNameKey:    model.Name,
		legion.ModelVersionKey: model.Version,
	})
	if err != nil {
		return err
	}

	legionctlCmd := fmt.Sprintf("legionctl --verbose build --container-id %s --docker-image-tag %s "+
		"--push-to-registry %s --model-file %s", containerID, localImageTag, externalImageTag, viper.GetString(legion.ModelFile),
	)
	commands := []string{
		"/bin/bash", "-c", fmt.Sprintf("cd %s && %s", viper.GetString(legion.SharedDirPath), legionctlCmd),
	}

	if err = mb.execInModelPod(commands); err != nil {
		log.Error(err, "Run legionctl command")
		return
	}

	return
}
