package validation

import (
	"connaisseur/internal/caching"
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	"connaisseur/internal/utils"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/sirupsen/logrus"
)

type CachedEntry struct {
	// Validated reference of the cached image
	Digest string `json:"digest"`
	// Error that occurred during previous validation
	Error string `json:"error"`
}

// Skips the validation if the validation result of the given image is
// cached or if the image should be automatically approved based on
// the configured features.
func Skip(
	ctx context.Context,
	image *image.Image,
	previousImages []string,
	parentImageFunc func(ctx context.Context) []string,
) (skip bool, skipReason, validatedDigest string, validationError error) {
	if automaticUnchangedApproval(image, previousImages) {
		return true, "unchanged image reference", image.Digest(), nil
	}

	if automaticChildApproval(ctx, image, parentImageFunc) {
		return true, "automatic approval of child image reference", image.Digest(), nil
	}

	digest, cacheErr, err := getCachedDigest(ctx, image)
	if err != nil {
		logrus.Debugf("error getting cached digest: %s", err)
		return false, "", "", nil
	}

	return true, "cache hit", digest, cacheErr
}

// automaticUnchangedApproval checks if the AUTOMATIC_UNCHANGED_APPROVAL feature flag is turned on
// and if the image is present in the list of old images. If both conditions are true,
// the function returns true, indicating that the validation check should be skipped.
func automaticUnchangedApproval(
	img *image.Image,
	previousImages []string,
) bool {
	if utils.FeatureFlagOn(constants.AutomaticUnchangedApproval) {
		for _, containerImage := range previousImages {
			if containerImage == img.OriginalString() {
				return true
			}
		}
	}
	return false
}

// automaticChildApproval, if enabled, returns whether the image under consideration was already
// approved as part of the parent's approval process.
//
// Note that automatic child approval doesn't work with pod-only validation as otherwise it
// would effectively create an allow-all validator.
func automaticChildApproval(ctx context.Context, img *image.Image, parentImageFunc func(ctx context.Context) []string) bool {
	if utils.FeatureFlagOn(constants.AutomaticChildApproval) {
		// Combination of automatic child approval and pod-only validation is insecure
		// as any pods that are part of another workload object will be admitted regardless
		// of their associated trust data. Thus we need to catch this case here
		if !utils.BlockAllResources() {
			logrus.Warn("insecure configuration detected: automatic child approval enabled, while only pod admissions are rejected. Pretending automatic child approval was disabled")
			return false
		}

		parentImages := parentImageFunc(ctx)

		logrus.Debugf("parent container images: %+v", parentImages)
		for _, pImg := range parentImages {
			if pImg == img.OriginalString() {
				return true
			}
		}
	}

	return false
}

// getCachedDigest retrieves the digest of a cached image.
// The function takes a context and a name.Reference as input, and returns the digest of the image
// as a string,
// as well as any errors that occurred during the retrieval process.
// If the image is not found in the cache, the function returns a cache miss error.
// If the cached entry contains an error message, the function returns that error message.
// If the cached value is not a valid image, the function returns an error indicating that the
// cached value is not an image.
func getCachedDigest(
	ctx context.Context,
	img *image.Image,
) (cachedDigest string, cachedError, err error) {
	cache := ctx.Value(constants.Cache).(caching.Cacher)

	val, err := cache.Get(ctx, img.OriginalString())
	if err != nil {
		if strings.Contains(err.Error(), "dial tcp") {
			logrus.Warnf("error connecting to cache: %s", err)
		}
		return "", nil, fmt.Errorf("cache miss for image %s: %s", img.OriginalString(), err)
	}

	cached := CachedEntry{}
	if err := json.Unmarshal([]byte(val), &cached); err != nil {
		return "", nil, fmt.Errorf("error unmarshalling cached entry: %s", err)
	}

	if cached.Error != "" {
		return "", errors.New(cached.Error), nil
	}

	if cached.Digest == "" {
		return "", nil, fmt.Errorf("empty cached digest")
	}

	return cached.Digest, nil, nil
}
