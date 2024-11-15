package validation

import (
	"connaisseur/internal/config"
	"connaisseur/internal/constants"
	"connaisseur/internal/kubernetes"
	"connaisseur/internal/validator"
	"connaisseur/test/testhelper"
	"context"
	"fmt"
	"io"
	"os"
	"strconv"
	"testing"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	dto "github.com/prometheus/client_model/go"
	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/assert"
	core "k8s.io/api/core/v1"
)

const PRE = "../../../test/testdata/config/"

func TestMain(m *testing.M) {
	logrus.SetOutput(io.Discard)
	os.Exit(m.Run())
}

func TestValidateWorkloadObject(t *testing.T) {
	var testCases = []struct {
		newWLO kubernetes.WorkloadObject
		out    map[string]struct {
			img            string
			validationMode string
			err            error
		}
	}{
		// test case with one image
		{
			kubernetes.WorkloadObject{
				Containers:     []core.Container{{Image: "nginx"}},
				InitContainers: []core.Container{{Image: "nginx"}},
			},
			map[string]struct {
				img            string
				validationMode string
				err            error
			}{
				"nginx": {"index.docker.io/library/nginx:latest", constants.MutateMode, nil},
			},
		},
		// test case with validationMode set to mutate
		{
			kubernetes.WorkloadObject{
				Containers:     []core.Container{{Image: "docker.io/securesystemsengineering/sample"}},
				InitContainers: []core.Container{{Image: "docker.io/securesystemsengineering/sample"}},
			},
			map[string]struct {
				img            string
				validationMode string
				err            error
			}{
				"docker.io/securesystemsengineering/sample": {
					"index.docker.io/securesystemsengineering/sample:latest",
					constants.MutateMode,
					nil,
				},
			},
		},
		// test case with validationMode set to validate
		{
			kubernetes.WorkloadObject{
				Containers:     []core.Container{{Image: "docker.io/securesystemsengineering/sample:v1"}},
				InitContainers: []core.Container{{Image: "docker.io/securesystemsengineering/sample:v1"}},
			},
			map[string]struct {
				img            string
				validationMode string
				err            error
			}{
				"docker.io/securesystemsengineering/sample:v1": {
					"index.docker.io/securesystemsengineering/sample:v1",
					constants.ValidateMode,
					nil,
				},
			},
		},
		// test case with two images
		{
			kubernetes.WorkloadObject{
				Containers:          []core.Container{{Image: "nginx"}, {Image: "debian"}},
				InitContainers:      []core.Container{{Image: "nginx"}},
				EphemeralContainers: []core.EphemeralContainer{{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "debian"}}},
			},
			map[string]struct {
				img            string
				validationMode string
				err            error
			}{
				"nginx":  {"index.docker.io/library/nginx:latest", constants.MutateMode, nil},
				"debian": {"index.docker.io/library/debian:latest", constants.MutateMode, nil},
			},
		},
	}

	cache := testhelper.MockCache(t, []testhelper.KeyValuePair{})
	defer cache.Close()

	cfg, _ := config.Load(PRE + "13_validation_modes.yaml")
	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
	ctx = context.WithValue(ctx, constants.Cache, cache)
	for idx, tc := range testCases {
		voChannel := ValidateWorkloadObject(ctx, &tc.newWLO, &kubernetes.WorkloadObject{})
		validatedImages := map[string]struct {
			img  string
			mode string
			err  error
		}{}
		containers := tc.newWLO.ConsolidatedContainers()
		for range containers {
			vo := <-voChannel
			validatedImages[vo.RawImage] = struct {
				img  string
				mode string
				err  error
			}{vo.NewImage, vo.ValidationMode, vo.Error}
		}
		assert.Equalf(t, len(tc.out), len(validatedImages), "test case %i", idx+1)
		for expectedValidatedImg := range tc.out {
			actualValidatedImg, ok := validatedImages[expectedValidatedImg]
			assert.Truef(t, ok, "test case %i", idx+1)
			assert.Equalf(
				t,
				tc.out[expectedValidatedImg].img,
				actualValidatedImg.img,
				"test case %i",
				idx+1,
			)
			assert.Equalf(
				t,
				tc.out[expectedValidatedImg].validationMode,
				actualValidatedImg.mode,
				"test case %i",
				idx+1,
			)
			assert.Equalf(
				t,
				tc.out[expectedValidatedImg].err,
				actualValidatedImg.err,
				"test case %i",
				idx+1,
			)
		}
	}
}

func TestValidateWorkloadObjectMetrics(t *testing.T) {
	cache := testhelper.MockCache(t, []testhelper.KeyValuePair{
		{
			Key:   "securesystemsengineering/alice-image:alreadyCachedSuccess",
			Value: `{"digest": "sha256:1234567890123456123456789012345612345678901234561234567890123456", "error": ""}`,
		},
		{
			Key:   "securesystemsengineering/alice-image:alreadyCachedFail",
			Value: `{"digest": "", "error": "definitely an error"}`,
		},
	})
	defer cache.Close()

	cfg, _ := config.Load(PRE + "14_validation_metrics.yaml")
	cfg.Validators = append(cfg.Validators, validator.Validator{
		Name:              "notary_validator",
		Type:              "notaryv1",
		SpecificValidator: testhelper.MockAllowValidator{},
	})
	cfg.Validators = append(cfg.Validators, validator.Validator{
		Name:              "cosigner",
		Type:              "cosign",
		SpecificValidator: testhelper.MockValidator{},
	})
	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
	ctx = context.WithValue(ctx, constants.Cache, cache)

	wlo := kubernetes.WorkloadObject{
		Containers: []core.Container{
			{Image: "docker.io/securesystemsengineering/default"},
			{Image: "securesystemsengineering/alice-image:alreadyPresent"},
			{Image: "docker.io/library/allow-me:someTag"},
			{Image: "docker.io/library/allow-me:someOtherTag"},
		},
		InitContainers: []core.Container{
			{Image: "docker.io/securesystemsengineering/notary-signed"},
			{Image: "docker.io/securesystemsengineering/notary-signed"},
			{Image: "docker.io/library/deny-me:tag"},
		},
		EphemeralContainers: []core.EphemeralContainer{
			{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "securesystemsengineering/alice-image:test"}},
			{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "securesystemsengineering/alice-image:willFail"}},
			{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "securesystemsengineering/alice-image:alreadyCachedSuccess"}},
			{EphemeralContainerCommon: core.EphemeralContainerCommon{Image: "securesystemsengineering/alice-image:alreadyCachedFail"}},
		},
	}
	oldWLO := kubernetes.WorkloadObject{
		Containers: []core.Container{
			{Image: "securesystemsengineering/alice-image:alreadyPresent"},
		},
	}

	// enable automatic unchanged approval
	t.Setenv(constants.AutomaticUnchangedApproval, strconv.FormatBool(true))

	// reset previous metrics (executions of other tests in the same pkg play into it)
	resetMetrics()

	voChannel := ValidateWorkloadObject(ctx, &wlo, &oldWLO)

	// wait for validations
	for range wlo.ConsolidatedContainers() {
		<-voChannel
	}

	defaultAllowed, _ := metricValue("connaisseur_validations_total", "static", "default", "success")
	explicitAllowed, _ := metricValue("connaisseur_validations_total", "static", "allow", "success")
	explicitDeny, _ := metricValue("connaisseur_validations_total", "static", "deny", "error")
	notaryAllowed, _ := metricValue("connaisseur_validations_total", "notaryv1", "notary_validator", "success")
	notaryDenied, _ := metricValue("connaisseur_validations_total", "notaryv1", "notary_validator", "error")
	cosignAllowed, _ := metricValue("connaisseur_validations_total", "cosign", "cosigner", "success")
	cosignDenied, _ := metricValue("connaisseur_validations_total", "cosign", "cosigner", "error")

	assert.Equal(t, float64(1), defaultAllowed)  // Only docker.io/securesystemsengineering/default is default static allow
	assert.Equal(t, float64(2), explicitAllowed) // docker.io/library/allow-me occurs with two different taggs
	assert.Equal(t, float64(1), explicitDeny)    // docker.io/library/deny-me occurs once
	assert.Equal(t, float64(1), notaryAllowed)   // Duplicated Notary image is consolidated before validation
	assert.Equal(t, float64(0), notaryDenied)
	assert.Equal(t, float64(3), cosignAllowed) // One image will be allowed and two will be skipped successfully
	assert.Equal(t, float64(2), cosignDenied)  // securesystemsengineering/alice-image:willFail will be denied and there's a cached failure

	cached, _ := metricValue("connaisseur_validations_skipped_total", "cosign", "cosigner", "cache hit")
	unchanged, _ := metricValue("connaisseur_validations_skipped_total", "cosign", "cosigner", "unchanged image reference")
	assert.Equal(t, float64(2), cached)
	assert.Equal(t, float64(1), unchanged)

}

func TestValidateImage(t *testing.T) {
	t.Setenv(constants.AutomaticUnchangedApproval, "true")

	var testCases = []struct {
		cfgFile  string
		olds     []string
		image    string
		newImage string
		skipped  bool
		skipMsg  string
		err      string
	}{
		{ // static allow
			"00_sample",
			[]string{},
			"allow-me",
			"index.docker.io/library/allow-me:latest",
			false,
			"",
			"",
		},
		{ // static deny
			"00_sample",
			[]string{},
			"deny-me",
			"",
			false,
			"",
			"static deny",
		},
		{ // static validator never skip
			"00_sample",
			[]string{"allow-me"},
			"allow-me",
			"index.docker.io/library/allow-me:latest",
			false,
			"",
			"",
		},
		{ // invalid input image
			"00_sample",
			[]string{},
			"invalid,image",
			"",
			false,
			"",
			"invalid image reference",
		},
		{ // no matching rule
			"09_missing_rule_validator",
			[]string{},
			"cccc",
			"",
			false,
			"",
			"no matching rule",
		},
		{ // missing validator
			"09_missing_rule_validator",
			[]string{},
			"aaaa",
			"",
			false,
			"",
			"validator \"x\" not found",
		},
		{ // regular validation
			"10_mutate_test",
			[]string{},
			"securesystemsengineering/alice-image:test",
			"index.docker.io/securesystemsengineering/alice-image:test@sha256:1234567890123456123456789012345612345678901234561234567890123456",
			false,
			"",
			"",
		},
		{ // error during validation
			"10_mutate_test",
			[]string{},
			"busybox",
			"",
			false,
			"",
			"unabled to find signed digest for image docker.io/library/busybox:latest",
		},
		{ // unchanged approval
			"10_mutate_test",
			[]string{"busybox"},
			"busybox",
			"index.docker.io/library/busybox:latest",
			true,
			"unchanged image reference",
			"",
		},
		{ // unchanged approval doesn't delete digest
			"10_mutate_test",
			[]string{
				"busybox@sha256:1234567890123456123456789012345612345678901234561234567890123456",
			},
			"busybox@sha256:1234567890123456123456789012345612345678901234561234567890123456",
			"index.docker.io/library/busybox@sha256:1234567890123456123456789012345612345678901234561234567890123456",
			true,
			"unchanged image reference",
			"",
		},
		{ // invalid output image
			"10_mutate_test",
			[]string{},
			"invalid-digest",
			"",
			false,
			"",
			"validated image reference index.docker.io/library/invalid-digest:latest@sha256:123 has invalid format",
		},
	}

	for idx, tc := range testCases {
		cfg, _ := config.Load(PRE, tc.cfgFile+".yaml")
		cache := testhelper.MockCache(t, []testhelper.KeyValuePair{})
		defer cache.Close()

		cfg.Validators = append(cfg.Validators, validator.Validator{
			Name:              "mock",
			Type:              "mock",
			SpecificValidator: testhelper.MockValidator{},
		})

		ctx := context.Background()
		ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
		ctx = context.WithValue(ctx, constants.Cache, cache)

		digestChannel := make(chan ValidationOutput, 1)
		go ValidateImage(
			ctx,
			ValidationInput{
				IdxsTypes:        []kubernetes.IdxType{{Index: 0, Type: "containers"}},
				Image:            tc.image,
				PreviousImages:   tc.olds,
				ParentImagesFunc: func(ctx context.Context) []string { return []string{} },
			},
			digestChannel,
		)

		digest := <-digestChannel

		if tc.err != "" {
			assert.NotNil(t, digest.Error, idx+1)
			assert.ErrorContains(t, digest.Error, tc.err, idx+1)
		} else {
			assert.Nil(t, digest.Error, idx+1)
			assert.Equal(t, tc.newImage, digest.NewImage, idx+1)
			assert.Equal(t, tc.skipped, digest.Skipped, idx+1)
			assert.Equal(t, tc.skipMsg, digest.SkipReason, idx+1)
		}
	}
}

// Test edge case of cancelled context
func TestValidateImageCancelledContext(t *testing.T) {
	cfg, _ := config.Load(PRE, "00_sample.yaml")
	cache := testhelper.MockCache(t, []testhelper.KeyValuePair{})
	defer cache.Close()

	ctx := context.Background()
	cctx, cancel := context.WithCancel(ctx)
	cctx = context.WithValue(cctx, constants.ConnaisseurConfig, cfg)
	cctx = context.WithValue(cctx, constants.Cache, cache)

	digestChannel := make(chan ValidationOutput, 1)
	cancel()
	ValidateImage(
		cctx,
		ValidationInput{
			IdxsTypes: []kubernetes.IdxType{{Index: 0, Type: "containers"}},
			Image:     "allow-me",
		},
		digestChannel,
	)
	contextCancelled := false
	select {
	case <-digestChannel:
		println("Error: Channel unexpectedly isn't empty and didn't time out!\n")
	case <-time.After(100 * time.Millisecond):
		println("Channel successfully timed out!\n")
		contextCancelled = true
	}
	assert.True(t, contextCancelled)

	// Timeout metric is increased
	metric, _ := metricValue("connaisseur_validations_timeouted_total", "static", "default", "")
	assert.Equal(t, float64(1), metric)
}

func TestValidateImageCachingBevhaiour(t *testing.T) {
	cfg, _ := config.Load(PRE, "10_mutate_test.yaml")
	cache := testhelper.MockCache(t, []testhelper.KeyValuePair{})
	defer cache.Close()

	cfg.Validators = append(cfg.Validators, validator.Validator{
		Name:              "mock",
		Type:              "mock",
		SpecificValidator: testhelper.MockValidator{},
	})

	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
	ctx = context.WithValue(ctx, constants.Cache, cache)

	// Normally, errors will be cached
	cachedOutputChannel := make(chan ValidationOutput, 1)
	ValidateImage(
		ctx,
		ValidationInput{
			IdxsTypes:        []kubernetes.IdxType{{Index: 0, Type: "containers"}},
			Image:            "will-be-denied-1",
			ParentImagesFunc: func(ctx context.Context) []string { return []string{} },
		},
		cachedOutputChannel,
	)
	<-cachedOutputChannel
	cached, err := cache.Get(ctx, "will-be-denied-1")
	assert.NotEmpty(t, cached)
	assert.Nil(t, err)

	// Set option to not cache errors
	t.Setenv(constants.CacheErrorsKey, strconv.FormatBool(false))
	nonCachedOutputChannel := make(chan ValidationOutput, 1)
	ValidateImage(
		ctx,
		ValidationInput{
			IdxsTypes:        []kubernetes.IdxType{{Index: 0, Type: "containers"}},
			Image:            "will-be-denied-2",
			ParentImagesFunc: func(ctx context.Context) []string { return []string{} },
		},
		nonCachedOutputChannel,
	)
	<-nonCachedOutputChannel
	cached, err = cache.Get(ctx, "will-be-denied-2")
	assert.Empty(t, cached)
	assert.NotNil(t, err)
}

func metricValue(name, label1, label2, label3 string) (float64, error) {
	var m = &dto.Metric{}
	switch name {
	case "connaisseur_validations_total":
		labelled, _ := numImageValidations.GetMetricWith(
			prometheus.Labels{"type": label1, "validator_name": label2, "result": label3},
		)
		_ = labelled.Write(m)
	case "connaisseur_validations_successful_total":
		labelled, _ := numImageValidationsSuccessful.GetMetricWith(
			prometheus.Labels{"type": label1, "validator_name": label2},
		)
		_ = labelled.Write(m)
	case "connaisseur_validations_failed_total":
		labelled, _ := numImageValidationsFailed.GetMetricWith(
			prometheus.Labels{"type": label1, "validator_name": label2},
		)
		_ = labelled.Write(m)
	case "connaisseur_validations_skipped_total":
		labelled, _ := numImageValidationsSkipped.GetMetricWith(
			prometheus.Labels{"type": label1, "validator_name": label2, "reason": label3},
		)
		_ = labelled.Write(m)
	case "connaisseur_validations_timeouted_total":
		labelled, _ := numImageValidationsTimeouted.GetMetricWith(
			prometheus.Labels{"type": label1, "validator_name": label2},
		)
		_ = labelled.Write(m)
	default:
		return 0, fmt.Errorf("metric %s doesn't exist or wasn't exposed", name)
	}

	return *m.Counter.Value, nil
}

func resetMetrics() {
	numImageValidations.Reset()
	numImageValidationsSuccessful.Reset()
	numImageValidationsFailed.Reset()
	numImageValidationsSkipped.Reset()
	numImageValidationsTimeouted.Reset()
}
