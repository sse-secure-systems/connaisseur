package utils

import (
	"connaisseur/internal/constants"
	"os"
	"strings"

	"github.com/google/go-containerregistry/pkg/logs"
	"github.com/sirupsen/logrus"
)

// Returns the log level for the given string. If no valid value is given, "info" is returned.
func LogLevel(logLevel string) logrus.Level {
	switch strings.ToLower(logLevel) {
	case "debug":
		return logrus.DebugLevel
	case "info":
		return logrus.InfoLevel
	case "warn":
		return logrus.WarnLevel
	case "error":
		return logrus.ErrorLevel
	case "fatal":
		return logrus.FatalLevel
	default:
		return logrus.InfoLevel
	}
}

func ConnaisseurLogLevel() logrus.Level {
	return LogLevel(os.Getenv(constants.LogLevel))
}

func logFormat(logFormat string) constants.ConnaisseurLogFormat {
	switch strings.ToLower(logFormat) {
	case "json":
		return constants.LogFormatJson
	case "json-pretty":
		return constants.LogFormatJsonPretty
	default:
		// default for backwards compatibility
		return constants.LogFormatJsonPretty
	}
}

func ConnaisseurLogFormat() constants.ConnaisseurLogFormat {
	return logFormat(os.Getenv(constants.LogFormat))
}

func InitiateThirdPartyLibraryLogging() {
	currentLevel := ConnaisseurLogLevel()
	// Cosign uses debug logs.Debug to redirect registry request log
	// https://github.com/sigstore/cosign/blob/304ff16bc955b8dd1a069f9f932baaacad086cd2/cmd/cosign/cli/commands.go#L78
	if compare(logrus.DebugLevel, currentLevel) >= 0 {
		logs.Debug.SetOutput(logTranslator{logFunction: logrus.Debug})
	}
	if compare(logrus.InfoLevel, currentLevel) >= 0 {
		logs.Progress.SetOutput(logTranslator{logFunction: logrus.Info})
	}
	if compare(logrus.WarnLevel, currentLevel) >= 0 {
		logs.Warn.SetOutput(logTranslator{logFunction: logrus.Warn})
	}
}

type logTranslator struct {
	logFunction func(...interface{})
}

func (l logTranslator) Write(b []byte) (int, error) {
	l.logFunction(string(b[:]))
	return len(b), nil
}

func compare(level1, level2 logrus.Level) int {
	logLevels := []logrus.Level{
		logrus.DebugLevel,
		logrus.InfoLevel,
		logrus.WarnLevel,
		logrus.ErrorLevel,
		logrus.FatalLevel,
	}
	var idx1, idx2 = -1, -1
	for i, l := range logLevels {
		if level1 == l {
			idx1 = i
		}
		if level2 == l {
			idx2 = i
		}
	}
	diff := idx1 - idx2
	if diff < 0 {
		return -1
	}
	if diff > 0 {
		return 1
	}
	return 0
}
