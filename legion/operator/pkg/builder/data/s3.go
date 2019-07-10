package data

import (
	"fmt"
	"github.com/aws/aws-sdk-go/aws"
	awssession "github.com/aws/aws-sdk-go/aws/session"
	awss3 "github.com/aws/aws-sdk-go/service/s3"
	"github.com/aws/aws-sdk-go/service/s3/s3manager"
	legionv1alpha1 "github.com/legion-platform/legion/legion/operator/pkg/apis/legion/v1alpha1"
	"net/url"
	"os"
	logf "sigs.k8s.io/controller-runtime/pkg/runtime/log"
)

var logS3 = logf.Log.WithName("builder")

type s3 struct {
	dataBinding *legionv1alpha1.DataBindingSpec
	session     *awssession.Session
}

func newS3(dataBinding *legionv1alpha1.DataBindingSpec) *s3 {
	sess, err := awssession.NewSession(&aws.Config{
		Region: aws.String(dataBinding.Region)},
	)
	if err != nil {
		panic(err)
	}

	return &s3{dataBinding: dataBinding, session: sess}
}

func (s3 *s3) DownloadFile(localPath string) error {
	file, err := os.Create(localPath)
	if err != nil {
		logS3.Error(err, "Create empty file", "file name", localPath)
		return err
	}

	downloader := s3manager.NewDownloader(s3.session)

	parse, err := url.Parse(s3.dataBinding.URI)
	if err != nil {
		logS3.Error(err, "Parsing data binding URI", "data binding uri", s3.dataBinding.URI)
		return err
	}

	logS3.Info("Start downloading data from s3", "bucket name", parse.Host, "key", parse.Path)

	_, err = downloader.Download(file,
		&awss3.GetObjectInput{
			Bucket: &parse.Host,
			Key:    &parse.Path,
		})
	if err != nil {
		logS3.Error(err, "Download data from s3", "bucket name", parse.Host, "key", parse.Path)
		return err
	}

	logS3.Info("Downloading data from s3 finished", "bucket name", parse.Host, "key", parse.Path)

	return nil
}

func (s3 *s3) UploadFile(localFileName string) error {
	uploader := s3manager.NewUploader(s3.session)

	parse, err := url.Parse(s3.dataBinding.URI)
	if err != nil {
		logS3.Error(err, "Parsing data binding URI", "data binding uri", s3.dataBinding.URI)
		return err
	}

	file, err := os.Open(localFileName)
	if err != nil {
		logS3.Error(err, "Open the file", "file name", localFileName)
		return err
	}

	defer file.Close()

	s3Key := aws.String(fmt.Sprintf("%s/%s", parse.Path, localFileName))
	_, err = uploader.Upload(&s3manager.UploadInput{
		Bucket: aws.String(parse.Host),
		Key:    s3Key,
		Body:   file,
	})

	if err != nil {
		logS3.Error(err, "Upload data to s3 failed", "bucket name", parse.Host, "key", s3Key)
		return err
	}

	logS3.Info("Uploading data to s3 finished", "bucket name", parse.Host, "key", s3Key)

	return nil
}
