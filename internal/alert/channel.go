package alerting

import (
	"bytes"
	"connaisseur/internal/utils"
	"context"
	"encoding/json"
	"fmt"
	"time"

	"io"
	"net/http"
	"strings"

	"text/template"

	"github.com/sirupsen/logrus"
)

type Channel struct {
	// unique name of the channel
	ChannelName string
	// url to send the notification to
	URL string `yaml:"receiverUrl" validate:"required,url"`
	// priority of the notification the lower the higher priority
	Priority *int `yaml:"priority" validate:"omitempty,gte=0"`
	// additional JSON fields for the alert body (not message)
	PayloadFields map[string]interface{} `yaml:"payloadFields" validate:"omitempty,min=1,dive"`
	// list of headers to send with the notification
	Headers []string `yaml:"customHeaders" validate:"omitempty,min=1,dive,required,contains=:"`
	// not used by code. only there, so that
	// strict parsing does not fail
	TemplateFile string `yaml:"template" validate:"required"`
	// whether to fail validation if the Sending fails
	Fail bool `yaml:"failIfAlertSendingFails"`
}

// Send generates a notification, based on the Channel's TemplateFile and sends it to the Channel's
// URL.
func (ch *Channel) Send(ctx context.Context, opts NotificationValues, errorChannel chan<- error) {
	var errOut error

	defer func() {
		if errOut != nil {
			logrus.Error(errOut)
		}

		select {
		case <-ctx.Done():
			return
		default:
			// report error if FailOnError is set
			if ch.Fail {
				errorChannel <- errOut
			}
		}
	}()

	// immediately report no error if FailOnError is false
	if !ch.Fail {
		errorChannel <- nil
	}

	if ch.Priority == nil {
		opts.Priority = 3
	} else {
		opts.Priority = *ch.Priority
	}
	opts.Timestamp = time.Now().UTC().String()

	buf, err := ch.generateNotificationMessage(opts)
	if err != nil {
		errOut = err
		logrus.Warnf("couldn't generate alert message: %s", errOut)
		return
	}

	// only send notification if the message isn't empty
	if buf.String() != "" {
		logrus.Debugf(
			"sending notification for receiver %s to %s",
			ch.ChannelName,
			ch.URL,
		)

		req, err := http.NewRequest("POST", ch.URL, buf)
		if err != nil {
			errOut = fmt.Errorf(
				"failed to create request for notification of receiver %s: %s",
				ch.ChannelName,
				err,
			)
			return
		}

		// Set default content type application/json. Can be overwritten by custom header
		req.Header.Set("Content-Type", "application/json")

		for _, header := range ch.Headers {
			hKeyValue := strings.SplitN(header, ":", 2)
			if len(hKeyValue) != 2 {
				errOut = fmt.Errorf(
					"header configuration for notification of receiver %s is invalid. Not all headers are valid: %s",
					ch.ChannelName,
					ch.Headers,
				)
				return
			}
			req.Header.Set(hKeyValue[0], hKeyValue[1])
		}

		client := &http.Client{}
		resp, err := client.Do(req)
		if err != nil {
			errOut = fmt.Errorf(
				"failed to send notification for receiver %s: %s",
				ch.ChannelName,
				err,
			)
			logrus.Warn(errOut)
			return
		}

		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			body, _ := io.ReadAll(resp.Body)
			errOut = fmt.Errorf(
				"failed to send notification for receiver %s: %s",
				ch.ChannelName,
				string(body),
			)
			logrus.Warn(errOut)
			return
		}
	} else {
		logrus.Warnf("skipping notification for receiver %s as message is empty", ch.ChannelName)
	}
}

func (ch *Channel) generateNotificationMessage(
	opts NotificationValues,
) (*bytes.Buffer, error) {
	// transform the Jinja templates into something Go can work with
	tmplStr, err := transformTemplate(ch.TemplateFile)
	if err != nil {
		return nil, fmt.Errorf(
			"failed to transform template for receiver %s: %s",
			ch.ChannelName,
			err,
		)
	}
	tmpl := template.New(ch.ChannelName)
	tmpl, err = tmpl.Parse(tmplStr)
	if err != nil {
		return nil, fmt.Errorf("failed to parse template file: %s", err)
	}

	// escape all string values to prevent json unmarshalling security vulnerabilities
	utils.JsonEscapeStruct(&opts)
	// render the template with the notification values
	buf := bytes.NewBufferString("")
	err = tmpl.Execute(buf, opts)
	if err != nil {
		return nil, fmt.Errorf(
			"failed to render template for receiver %s: %v",
			ch.ChannelName,
			err,
		)
	}

	// transform rendered template (which should be JSON at this point) into a
	// map, so additional payload fields can be added
	tmplMap := map[string]interface{}{}
	if buf.String() != "" && buf.String() != "{}" {
		err = json.Unmarshal(buf.Bytes(), &tmplMap)
		if err != nil {
			return nil, fmt.Errorf(
				"failed to unmarshal rendered template for receiver %s: %v",
				ch.ChannelName,
				err,
			)
		}
	} else {
		// return empty buffer if the rendered template is empty
		// even though payload fields could be added, it would be pointless
		return &bytes.Buffer{}, nil
	}

	// add additional payload fields
	tmplMap = templateWithPayloadFields(tmplMap, ch.PayloadFields)
	tmplWithPayload, err := json.Marshal(tmplMap)
	if err != nil {
		return nil, fmt.Errorf(
			"failed to marshal rendered template for receiver %s: %v",
			ch.ChannelName,
			err,
		)
	}

	return bytes.NewBuffer(tmplWithPayload), nil
}

func (ch *Channel) FailOnError() bool {
	return ch.Fail
}

func (ch *Channel) Name() string {
	return ch.ChannelName
}
