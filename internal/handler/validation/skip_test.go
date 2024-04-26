package validation

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	"connaisseur/test/testhelper"
	"context"
	"fmt"
	"strconv"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestSkip(t *testing.T) {
	var testCases = []struct {
		img             string
		oldImages       []string
		unchangdEnabled bool
		cacheKey        string
		cacheValue      string
		expectedSkip    bool
		expectedReason  string
		expectedDigest  string
		expectedError   string
	}{
		{ // 1: Unchanged enabled, unchanged image
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{"docker.io/securesystemsengineering/testimage:signed"},
			true,
			"",
			"",
			true,
			"unchanged image reference",
			"",
			"",
		},
		{ // 2: Unchanged enabled, but false, not cached
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{},
			true,
			"",
			"",
			false,
			"",
			"",
			"",
		},
		{ // 3: Unchanged enabled, but false, cached
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{},
			true,
			"docker.io/securesystemsengineering/testimage:signed",
			`{"digest":"sha256:0123456789012345012345678901234501234567890123450123456789012345", "error": ""}`,
			true,
			"cache hit",
			"sha256:0123456789012345012345678901234501234567890123450123456789012345",
			"",
		},
		{ // 4: Unchanged enabled, but false, cached error
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{},
			true,
			"docker.io/securesystemsengineering/testimage:signed",
			`{"digest":"", "error": "much error"}`,
			true,
			"cache hit",
			"",
			"much error",
		},
		{ // 5: Unchanged disabled, cache hit
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{},
			false,
			"docker.io/securesystemsengineering/testimage:signed",
			`{"digest":"sha256:0123456789012345012345678901234501234567890123450123456789012345", "error": ""}`,
			true,
			"cache hit",
			"sha256:0123456789012345012345678901234501234567890123450123456789012345",
			"",
		},
		{ // 6: Unchanged disabled, cache miss
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{},
			false,
			"docker.io/securesystemsengineering/testimage:unsigned",
			`{"digest":"sha256:0123456789012345012345678901234501234567890123450123456789012345", "error": ""}`,
			false,
			"",
			"",
			"",
		},
		{ // 7: Unchanged disabled, cached error
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{},
			false,
			"docker.io/securesystemsengineering/testimage:signed",
			`{"digest":"", "error":"evil signatures will be rejected"}`,
			true,
			"cache hit",
			"",
			"evil signatures will be rejected",
		},
		{ // 8: Unchanged disabled, empty cache
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{},
			false,
			"docker.io/securesystemsengineering/testimage:signed",
			`{}`,
			false,
			"",
			"",
			"",
		},
		{ // 9: Unchanged disabled, invalid cache -> don't skip, no error
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{},
			false,
			"docker.io/securesystemsengineering/testimage:signed",
			`{`,
			false,
			"",
			"",
			"",
		},
		{ // 10: Unchanged disabled, skip even though cache isn't digest, no error
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{},
			false,
			"docker.io/securesystemsengineering/testimage:signed",
			`{"digest":"docker.io/securesystemsengineering/testimage@sha256:0123456789012345012345678901234501234567890123450123456789012345", "error": ""}`,
			true,
			"cache hit",
			"docker.io/securesystemsengineering/testimage@sha256:0123456789012345012345678901234501234567890123450123456789012345",
			"",
		},
	}
	for idx, tc := range testCases {
		// Setup
		t.Setenv(constants.AutomaticUnchangedApproval, strconv.FormatBool(tc.unchangdEnabled))
		cache := testhelper.MockCache(
			t,
			[]testhelper.KeyValuePair{{Key: tc.cacheKey, Value: tc.cacheValue}},
		)
		defer cache.Close()
		ctx := context.Background()
		ctx = context.WithValue(ctx, constants.Cache, cache)
		theImage, cachedError := image.New(tc.img)
		if cachedError != nil {
			panic(fmt.Errorf("Image for test must be valid: %s", cachedError))
		}

		skip, reason, digest, cachedError := Skip(
			ctx,
			theImage,
			tc.oldImages,
			func(context.Context) []string { return []string{} },
		)

		// Correct response
		assert.Equal(t, tc.expectedSkip, skip, idx+1)
		assert.Equal(t, tc.expectedReason, reason, idx+1)
		assert.Equal(t, tc.expectedDigest, digest, idx+1)

		if tc.expectedError != "" {
			assert.NotNil(t, cachedError, idx+1)
			assert.ErrorContains(t, cachedError, tc.expectedError, idx+1)
		} else {
			assert.Nil(t, cachedError, idx+1)
		}

		// Check logic dependencies
		assert.Equalf(
			t,
			skip,
			reason != "",
			"%d: if validation should be skipped, there must be a reason, and vice versa",
			idx+1,
		)
		assert.Equalf(
			t,
			cachedError == nil && skip && tc.cacheKey != "",
			digest != "",
			"%d: if there's no caching error and the image should be skipped, there should be a digest, and vice versa",
			idx+1,
		)
		if digest != "" {
			assert.Truef(t, skip, "%d: if there's a digest, validation must be skipped", idx+1)
		}
		if cachedError != nil {
			assert.Truef(t, skip, "%d: if there's a cached error, image must be skipped", idx+1)
		}
	}
}

func TestSkipCacheError(t *testing.T) {
	var testCases = []struct {
		img            string
		expectedSkip   bool
		expectedReason string
		expectedDigest string
	}{
		{ // Cache error -> don't skip, no error
			"docker.io/securesystemsengineering/testimage:signed",
			false,
			"",
			"",
		},
	}
	for idx, tc := range testCases {
		// Setup
		cache := testhelper.NewFailingCache(t, []testhelper.KeyValuePair{}, []string{tc.img}, false)
		defer cache.Close()
		ctx := context.Background()
		ctx = context.WithValue(ctx, constants.Cache, cache)
		theImage, cachedError := image.New(tc.img)
		if cachedError != nil {
			panic(fmt.Errorf("Image for test must be valid: %s", cachedError))
		}

		skip, reason, digest, cachedError := Skip(ctx, theImage, []string{}, func(context.Context) []string { return []string{} })

		// Correct response
		assert.Equal(t, tc.expectedSkip, skip, idx+1)
		assert.Equal(t, tc.expectedReason, reason, idx+1)
		assert.Equal(t, tc.expectedDigest, digest, idx+1)
		assert.Nil(t, cachedError, idx+1)
	}
}

func TestAutomaticUnchangedApproval(t *testing.T) {
	var testCases = []struct {
		img       string
		oldImages []string
		enabled   bool
		expected  bool
	}{
		{ // 1: Returns false if not enabled
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{"docker.io/securesystemsengineering/testimage:signed"},
			false,
			false,
		},
		{ // 2: No old images
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{},
			true,
			false,
		},
		{ // 3: Only old image
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{"docker.io/securesystemsengineering/testimage:signed"},
			true,
			true,
		},
		{ // 4: Not in old images
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{"docker.io/securesystemsengineering/testimage:unsigned"},
			true,
			false,
		},
		{ // 5: One of old images
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{
				"docker.io/securesystemsengineering/testimage:unsigned",
				"docker.io/securesystemsengineering/testimage:signed",
				"abc.de/fgh:ijk",
			},
			true,
			true,
		},
	}

	for idx, tc := range testCases {
		image, err := image.New(tc.img)
		if err != nil {
			panic(fmt.Errorf("Image for test must be valid: %s", err))
		}
		t.Setenv(constants.AutomaticUnchangedApproval, strconv.FormatBool(tc.enabled))
		result := automaticUnchangedApproval(image, tc.oldImages)
		assert.Equal(t, tc.expected, result, idx+1)
	}
}

func TestAutomaticChildApproval(t *testing.T) {
	var testCases = []struct {
		img                    string
		parentImages           []string
		enabled                bool
		resourceValidationMode string
		expected               bool
	}{
		{ // 1: Returns false if not enabled
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{"docker.io/securesystemsengineering/testimage:signed"},
			false,
			"all",
			false,
		},
		{ // 2: Returns true if enabled and image in parent images
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{"docker.io/securesystemsengineering/testimage:signed"},
			true,
			"all",
			true,
		},
		{ // 3: Returns true if enabled and image one of multiple parent images
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{"abc", "docker.io/securesystemsengineering/testimage:signed", "def"},
			true,
			"all",
			true,
		},
		{ // 4: Returns false if enabled but image not in parent images
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{"docker.io/securesystemsengineering/testimage:signed-but-different"},
			true,
			"all",
			false,
		},
		{ // 5: Returns false if enabled but pod-only validation is active
			"docker.io/securesystemsengineering/testimage:signed",
			[]string{"docker.io/securesystemsengineering/testimage:signed"},
			true,
			"podsonly",
			false,
		},
	}

	ctx := context.Background()
	for idx, tc := range testCases {
		t.Setenv(constants.AutomaticChildApproval, strconv.FormatBool(tc.enabled))
		t.Setenv(constants.ResourceValidationMode, tc.resourceValidationMode)

		image, err := image.New(tc.img)
		if err != nil {
			panic(fmt.Errorf("Image for test must be valid: %s", err))
		}
		result := automaticChildApproval(ctx, image, func(context.Context) []string { return tc.parentImages })
		assert.Equal(t, tc.expected, result, "test case %d", idx+1)
	}
}
