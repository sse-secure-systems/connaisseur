package alerting

import (
	"connaisseur/internal/utils"
	"context"
	"fmt"
	"os"

	"github.com/sirupsen/logrus"
	"gopkg.in/yaml.v3"
)

type Config struct {
	ClusterId      string        `yaml:"clusterIdentifier"`
	AdmitRequests  RequestSender `yaml:"admitRequest"`
	RejectRequests RequestSender `yaml:"rejectRequest"`
}

type RequestSender struct {
	Receivers []Sender `validate:"dive"`
}

type Sender interface {
	// Send sends out the notifications and writes an error to the channel.
	// If the Sender's FailOnError is false, this will always be nil.
	// Otherwise, the error will be not nil if the sending of the notification
	// failed.
	Send(context.Context, NotificationValues, chan<- error)
	// FailOnError returns whether the Sender will raise an error during sending
	// if sending fails or whether it will just accept failure.
	FailOnError() bool
	// Name returns a human-readable name for the Sender.
	Name() string
}

func (r *RequestSender) UnmarshalYAML(unmarshal func(interface{}) error) error {
	var rData struct {
		Receivers []*Channel `yaml:"receivers"`
	}
	if err := unmarshal(&rData); err != nil {
		return err
	}

	castedSenders := make([]Sender, 0, len(rData.Receivers))
	for idx, s := range rData.Receivers {
		s.ChannelName = fmt.Sprintf("%s-%d", s.TemplateFile, idx)
		castedSenders = append(castedSenders, s)
	}
	r.Receivers = castedSenders
	return nil
}

func LoadConfig(baseDir string, pathElements ...string) (*Config, error) {
	var alerting Config
	file, err := utils.SafeFileName(baseDir, pathElements...)
	if err != nil {
		return nil, fmt.Errorf(
			"error sanitizing file with baseDir %s and pathElements %+q",
			baseDir,
			pathElements,
		)
	}

	configFile, err := os.Open(
		file,
	) // #nosec G304 false positive since SafeFileName is called before
	if err != nil {
		return nil, fmt.Errorf("error loading file: %s", err)
	}

	dec := yaml.NewDecoder(configFile)
	// validates that only known fields, marked with struct tags (`yaml:"..."`)
	// are used. otherwise, an error is returned.
	dec.KnownFields(true)

	if err = dec.Decode(&alerting); err != nil {
		return nil, fmt.Errorf("error parsing file: %s", err)
	}

	err = alerting.validate()
	if err != nil {
		logrus.Fatal(err)
	}
	logrus.Debugf("alerting config validated without errors: %+v", alerting)

	return &alerting, nil
}

func (a *Config) validate() error {
	return utils.Validate(a)
}
