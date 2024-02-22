package config

import (
	alerting "connaisseur/internal/alert"
	"connaisseur/internal/policy"
	"connaisseur/internal/utils"
	"connaisseur/internal/validator"
	"fmt"
	"os"
	"strings"

	"github.com/gobwas/glob"
	"github.com/sirupsen/logrus"
	"gopkg.in/yaml.v3"
)

type Config struct {
	// list of validators
	Validators []validator.Validator `yaml:"validators" validate:"min=1,dive"`
	// list of rules
	Rules []policy.Rule `yaml:"policy" validate:"min=1,dive"`
	// list of alerts
	Alerting alerting.Config `yaml:"alerting"`
}

// Loads a config file from the given path and returns a Config struct
// containing a list of validators, rules and alerts.
func Load(baseDir string, pathElements ...string) (*Config, error) {
	var conf Config
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
	) // #nosec G304 This is a false positive displayed by Gosec that displays a "Potential file inclusion via variable" warning. However, the sanitizer function SafeFileName(...) is called before.
	if err != nil {
		return nil, fmt.Errorf("error loading file: %s", err)
	}

	dec := yaml.NewDecoder(configFile)
	// validates that only known fields, marked with struct tags (`yaml:"..."`)
	// are used. otherwise, an error is returned.
	dec.KnownFields(true)

	if err = dec.Decode(&conf); err != nil {
		return nil, fmt.Errorf("error parsing file: %s", err)
	}

	err = conf.validate()
	if err != nil {
		logrus.Fatal(err)
	}
	logrus.Debugf("config validated without errors: %+v", conf)

	return &conf, nil
}

// Gets a validator by its name from the config. If no name is given,
// the default validator is returned.
func (c Config) Validator(key string) (*validator.Validator, error) {
	// if no key is given, use "default"
	if key == "" {
		key = "default"
	}

	for _, validator := range c.Validators {
		if validator.Name == key {
			return &validator, nil
		}
	}
	return nil, fmt.Errorf("validator \"%s\" not found", key)
}

// Gets the most specific matching rule for a given image from the config.
func (c Config) MatchingRule(image string) (*policy.Rule, error) {
	// start with empty pattern
	bestMatch := policy.NewMatch(policy.Rule{}, "")

	for _, rule := range c.Rules {
		pattern := rule.Pattern

		// prepend wildcard if not present
		if !strings.HasPrefix(pattern, "*") {
			pattern = fmt.Sprintf("*%s", pattern)
		}
		if !strings.HasSuffix(pattern, "*") {
			pattern = fmt.Sprintf("%s*", pattern)
		}

		g := glob.MustCompile(pattern)

		if g.Match(image) {
			match := policy.NewMatch(
				rule,
				image,
			)
			bestMatch = match.Compare(bestMatch)
		}
	}

	if bestMatch.Rule.Pattern == "" {
		return nil, fmt.Errorf("no matching rule")
	}
	return &bestMatch.Rule, nil
}

func (c Config) validate() error {
	return utils.Validate(c)
}
