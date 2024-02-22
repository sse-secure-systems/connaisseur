package validation

import (
	"connaisseur/internal/caching"
	"connaisseur/internal/config"
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	"connaisseur/internal/kubernetes"
	"connaisseur/internal/utils"
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/sirupsen/logrus"
)

type ValidationInput struct {
	// Index and type of the container in the pod
	IdxsTypes []kubernetes.IdxType
	// Image to validate
	Image string
	// Previous images of the old object
	PreviousImages []string
	// Function to get images of parent objects
	ParentImagesFunc func(ctx context.Context) []string
}

type ValidationOutput struct {
	// Index and type of the container in the pod
	IdxsTypes []kubernetes.IdxType
	// Original image reference
	RawImage string
	// Validated qualified image reference
	NewImage string
	// Qualified image reference
	OldImage string
	// Error that occurred during validation
	Error error
	// Name of the validator that was used
	Validator string
	// Whether the image was skipped
	Skipped bool
	// Reason for skipping the image
	SkipReason string
	// Whether the image should only be validated
	// or also mutated
	ValidationMode string
}

// ValidateWorkloadObject sets off validation for all containers in the new WorkloadObject
// and returns a channel for the ValidationOutputs.
func ValidateWorkloadObject(
	ctx context.Context,
	new *kubernetes.WorkloadObject,
	old *kubernetes.WorkloadObject,
) <-chan ValidationOutput {
	containers := new.ConsolidatedContainers()
	previousImages := old.ImageSet()
	out := make(chan ValidationOutput, len(containers))
	for image, idxType := range containers {
		go ValidateImage(
			ctx,
			ValidationInput{
				IdxsTypes:        idxType,
				Image:            image,
				PreviousImages:   previousImages,
				ParentImagesFunc: new.ParentContainerImagesFromKubeAPI,
			},
			out,
		)
	}
	return out
}

// Matches a given image against a policy rule and uses the respective
// validator to validate the image. Sends results to the out channel.
func ValidateImage(ctx context.Context, in ValidationInput, out chan<- ValidationOutput) {
	var (
		img            *image.Image
		newImg         string
		oldImg         string
		digest         string
		errOut         error
		cacheErr       string
		validatorName  string
		skipped        bool
		skipReason     string
		validationMode string
		validatorType  string = "unknown"
	)

	defer func() {
		// either send a validation result or just return
		// if the context was cancelled
		select {
		case <-ctx.Done():
			IncValidationsTimeouted(validatorType, validatorName)
			return
		default:
			// check if new image still has a valid format, but only if no error occurred so far
			if errOut == nil {
				if _, err := image.New(newImg); err != nil {
					errOut = fmt.Errorf(
						"validated image reference %s has invalid format: %v",
						newImg,
						err,
					)
				}
			}

			// add metrics
			if errOut == nil {
				IncValidationsSuccessful(validatorType, validatorName)
			} else {
				IncValidationsFailed(validatorType, validatorName)
			}
			if skipped {
				IncValidationsSkipped(validatorType, validatorName, skipReason)
			}

			out <- ValidationOutput{
				IdxsTypes:      in.IdxsTypes,
				RawImage:       in.Image,
				NewImage:       newImg,
				OldImage:       oldImg,
				Error:          errOut,
				Validator:      validatorName,
				Skipped:        skipped,
				SkipReason:     skipReason,
				ValidationMode: validationMode,
			}
		}
	}()

	config := ctx.Value(constants.ConnaisseurConfig).(*config.Config)
	cache := ctx.Value(constants.Cache).(caching.Cacher)

	// parse Image
	img, err := image.New(in.Image)
	if err != nil {
		errOut = fmt.Errorf("invalid image reference")
		return
	}

	// get matching rule
	rule, err := config.MatchingRule(img.Name())
	if err != nil {
		errOut = err
		return
	}
	logrus.Debugf(
		"matched rule: %s for image %s with reqId %s",
		rule.Pattern,
		img.Name(),
		ctx.Value("reqId"),
	)

	// get validator
	validator, err := config.Validator(rule.Validator)
	if err != nil {
		errOut = err
		return
	}
	validatorType = validator.Type
	validatorName = validator.Name
	logrus.Debugf("validator: %s", validatorName)

	// get validation mode
	switch strings.ToLower(rule.With.ValidationMode) {
	case constants.MutateMode:
		validationMode = constants.MutateMode
	case constants.ValidateMode:
		validationMode = constants.ValidateMode
	default:
		validationMode = constants.MutateMode
	}

	// prepone static validators, as they are fast enough to not need any caching
	// mechanism
	if validator.Type == constants.StaticValidator {
		digest, err = validator.ValidateImage(ctx, img, rule.With)

		if err != nil {
			errOut = fmt.Errorf(
				"static deny for image %s using rule %s",
				img.OriginalString(),
				rule.Pattern,
			)
		} else {
			oldImg = img.Name()
			newImg = img.SetDigest(digest).Name()
			logrus.Infof("static allow for image %s using rule %s", img.OriginalString(), rule.Pattern)
		}
		return
	}

	// check if image validation should be skipped
	if skip, reason, digest, err := Skip(ctx, img, in.PreviousImages, in.ParentImagesFunc); skip {
		skipped = skip
		skipReason = reason
		errOut = err
		oldImg = img.Name()
		newImg = img.SetDigest(digest).Name()
		logrus.Infof("skipped validation: %s for image %s", reason, img.OriginalString())
		return
	}

	// validate image
	digest, errOut = validator.ValidateImage(
		ctx,
		img,
		rule.With,
	)

	if errOut != nil {
		errOut = fmt.Errorf(
			"error during %s validation of image %s: %v",
			validator.Type,
			img.OriginalString(),
			errOut,
		)
		cacheErr = errOut.Error()
	} else {
		oldImg = img.Name()
		newImg = img.SetDigest(digest).Name()
		logrus.Infof(
			"successfully validated image %s using rule %s and validator %s. Result is %s.",
			img.OriginalString(),
			rule.Pattern,
			validator.Name,
			newImg,
		)
	}

	// cache digest or error
	if cacheErr != "" || img.Digest() != "" {
		if cacheErr != "" {
			img.SetDigest("") // delete digest for clearer caching entries
		}

		err = cache.Set(
			ctx,
			img.OriginalString(),
			fmt.Sprintf(
				`{"digest":"%s","error":"%s"}`,
				utils.JsonEscapeString(img.Digest()),
				utils.JsonEscapeString(cacheErr),
			),
			constants.CacheExpirySeconds*time.Second,
		)
		if err != nil {
			logrus.Warnf("error caching digest: %v", err)
		}
	}
}
