package data

import (
	"fmt"
	legionv1alpha1 "github.com/legion-platform/legion/legion/operator/pkg/apis/legion/v1alpha1"
	"github.com/pkg/errors"
)

type ObjectStorage interface {
	DownloadFile(string) error
	UploadFile(string) error
}

func NewObjectStorage(dataBinding *legionv1alpha1.DataBindingSpec) ObjectStorage {
	switch dataBinding.Type {
	case legionv1alpha1.S3Type:
		return newS3(dataBinding)
	default:
		// impossible situation
		panic(errors.New(fmt.Sprintf("Unxpected databinding type: %s", dataBinding.Type)))
	}
}
