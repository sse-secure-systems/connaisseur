package utils

import (
	"connaisseur/internal/constants"
	"os"
	"strconv"
	"strings"

	"github.com/sirupsen/logrus"
)

// Checks if a feature flag, given as env var, is set to true.
func FeatureFlagOn(flagKey string) bool {
	flag, err := strconv.ParseBool(os.Getenv(flagKey))
	if err != nil {
		switch flagKey {
		case constants.AutomaticChildApproval:
			flag = true
		case constants.AutomaticUnchangedApproval:
			flag = false
		case constants.DetectionMode:
			flag = false
		}
		logrus.Warnf("invalid value '%s' for feature flag '%s', defaulting to %t", os.Getenv(flagKey), flagKey, flag)
	}
	return flag
}

func BlockAllResources() bool {
	rvm := os.Getenv(constants.ResourceValidationMode)

	switch strings.ToLower(rvm) {
	case "all":
		return true
	case "podsonly":
		return false
	default:
		logrus.Infof("invalid value '%s' for resource validation mode, defaulting to 'all'", rvm)
		return true
	}
}
