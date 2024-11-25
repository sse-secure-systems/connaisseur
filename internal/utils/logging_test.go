package utils

import (
	"connaisseur/internal/constants"
	"io"
	"testing"

	"github.com/google/go-containerregistry/pkg/logs"
	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/assert"
)

func TestLogLevel(t *testing.T) {
	var testCases = []struct {
		logLevel string
		want     logrus.Level
	}{
		{
			logLevel: "debug",
			want:     logrus.DebugLevel,
		},
		{
			logLevel: "info",
			want:     logrus.InfoLevel,
		},
		{
			logLevel: "warn",
			want:     logrus.WarnLevel,
		},
		{ // We don't support multiple values for warn level
			logLevel: "warning",
			want:     logrus.InfoLevel,
		},
		{
			logLevel: "error",
			want:     logrus.ErrorLevel,
		},
		{
			logLevel: "fatal",
			want:     logrus.FatalLevel,
		},
		{
			logLevel: "panic",
			want:     logrus.InfoLevel,
		},
		{
			logLevel: "foo",
			want:     logrus.InfoLevel,
		},
		{
			logLevel: "",
			want:     logrus.InfoLevel,
		},
		{
			logLevel: "fATaL",
			want:     logrus.FatalLevel,
		},
	}
	for _, tc := range testCases {
		logLevel := LogLevel(tc.logLevel)
		assert.Equal(t, tc.want, logLevel)
	}
}

func TestConnaisseurLogLevel(t *testing.T) {
	var testCases = []struct {
		logLevel string
		want     logrus.Level
	}{
		{
			logLevel: "debug",
			want:     logrus.DebugLevel,
		},
		{
			logLevel: "fATaL",
			want:     logrus.FatalLevel,
		},
	}
	for _, tc := range testCases {
		(*testing.T).Setenv(t, constants.LogLevel, tc.logLevel)
		logLevel := ConnaisseurLogLevel()
		assert.Equal(t, tc.want, logLevel)
	}
}

func TestConnaisseurLogFormat(t *testing.T) {
	var testCases = []struct {
		logFormat string
		want      constants.ConnaisseurLogFormat
	}{
		{
			logFormat: "json",
			want:      constants.LogFormatJson,
		},
		{
			logFormat: "json-pretty",
			want:      constants.LogFormatJsonPretty,
		},
	}
	for _, tc := range testCases {
		(*testing.T).Setenv(t, constants.LogFormat, tc.logFormat)
		logFormat := ConnaisseurLogFormat()
		assert.Equal(t, tc.want, logFormat)
	}
}

func TestCompare(t *testing.T) {
	var testCases = []struct {
		level1   logrus.Level
		level2   logrus.Level
		expected int
	}{
		{
			logrus.DebugLevel,
			logrus.DebugLevel,
			0,
		},
		{
			logrus.InfoLevel,
			logrus.DebugLevel,
			1,
		},
		{
			logrus.DebugLevel,
			logrus.InfoLevel,
			-1,
		},
		{
			logrus.WarnLevel,
			logrus.DebugLevel,
			1,
		},
		{
			logrus.ErrorLevel,
			logrus.DebugLevel,
			1,
		},
		{
			logrus.FatalLevel,
			logrus.DebugLevel,
			1,
		},
		{
			logrus.WarnLevel,
			logrus.InfoLevel,
			1,
		},
		{
			logrus.ErrorLevel,
			logrus.WarnLevel,
			1,
		},
		{
			logrus.FatalLevel,
			logrus.ErrorLevel,
			1,
		},
		{ // Levels used by Connaisseur are greater than other levels
			logrus.PanicLevel,
			logrus.DebugLevel,
			-1,
		},
		{ // Levels not used by Connaisseur are distinguished
			logrus.PanicLevel,
			logrus.TraceLevel,
			0,
		},
	}
	for _, tc := range testCases {
		assert.Equal(t, tc.expected, compare(tc.level1, tc.level2))
		assert.Equal(t, -tc.expected, compare(tc.level2, tc.level1))
	}
}

func TestInitiateThirdPartyLibraryLogging(t *testing.T) {
	var testCases = []string{
		"debug",
		"info",
		"warn",
		"error",
	}
	for _, tc := range testCases {
		t.Setenv(constants.LogLevel, tc)
		InitiateThirdPartyLibraryLogging()
		level := LogLevel(tc)

		if compare(level, logrus.DebugLevel) <= 0 {
			assert.IsType(t, logTranslator{}, logs.Debug.Writer())
		} else {
			assert.IsType(t, io.Discard, logs.Debug.Writer())
		}
		if compare(level, logrus.InfoLevel) <= 0 {
			assert.IsType(t, logTranslator{}, logs.Progress.Writer())
		} else {
			assert.IsType(t, io.Discard, logs.Progress.Writer())
		}
		if compare(level, logrus.WarnLevel) <= 0 {
			assert.IsType(t, logTranslator{}, logs.Warn.Writer())
		} else {
			assert.IsType(t, io.Discard, logs.Warn.Writer())
		}

		// Cleanup
		logs.Debug.SetOutput(io.Discard)
		logs.Progress.SetOutput(io.Discard)
		logs.Warn.SetOutput(io.Discard)
	}
}

func TestWrite(t *testing.T) {
	var output struct {
		out []interface{}
	}
	writer := func(args ...interface{}) {
		output.out = args
	}
	translator := logTranslator{writer}

	_, err := translator.Write([]byte{104, 101, 108, 108, 111})
	assert.Nil(t, err)
	assert.Equal(t, 1, len(output.out))
	assert.IsType(t, "", output.out[0])
	assert.Equal(t, "hello", output.out[0].(string))
}
