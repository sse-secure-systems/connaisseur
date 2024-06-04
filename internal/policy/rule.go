package policy

type Rule struct {
	// Pattern to match against
	Pattern string `yaml:"pattern" validate:"required"`
	// Name of the validator to use. If empty will use default validator
	Validator string `yaml:"validator"`
	// RuleOptions for the validation
	With RuleOptions `yaml:"with"`
}

type RuleOptions struct {
	// Name of trust root to use or all-quantifier '*'
	TrustRoot string `yaml:"trustRoot"`
	// flag to indicate whether to verify the image against a transparency log (cosign)
	VerifyTLog *bool `yaml:"verifyInTransparencyLog"` // pointer to distinguish false and unset
	// flag to indicate whether to check for signed certificate timestamps in transparency log (cosign)
	VerifySCT *bool `yaml:"verifySCT"` // pointer to distinguish false and unset
	// threshold of cosign signatures to require
	Threshold int `yaml:"threshold" validate:"gte=0"`
	// list of trust roots whose signatures need to
	// be valid to verify the image (cosign)
	Required []string `yaml:"required" validate:"excluded_with=Delegations,omitempty,min=1,dive,required"`
	// list of delegations whose signatures need to
	// be valid to verify the image (notaryv1)
	Delegations []string `yaml:"delegations" validate:"excluded_with=Required,omitempty,min=1,dive,required"`
	// flag to indicate whether to mutate the image (default)
	// or to insecurely skip its mutation and only validate
	// that an image exists that would pass validation
	ValidationMode string `yaml:"mode" validate:"omitempty,oneof=mutate insecureValidateOnly"`
}
