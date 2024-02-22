package handler

import (
	alerting "connaisseur/internal/alert"
	"connaisseur/internal/config"
	"connaisseur/internal/constants"
	"connaisseur/internal/validator"
	"connaisseur/test/testhelper"
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	dto "github.com/prometheus/client_model/go"
	"github.com/stretchr/testify/assert"
	v1 "k8s.io/api/admission/v1"
)

const PRE = "../../test/testdata/"

func TestMain(m *testing.M) {
	// Run tests
	constants.AlertTemplateDir = PRE + "alerts/"
	os.Exit(m.Run())
}

func TestHandleMutate(t *testing.T) {
	handler := http.HandlerFunc(HandleMutate)
	cfg, _ := config.Load(PRE, "config/10_mutate_test.yaml")
	alertCfg, _ := alerting.LoadConfig(PRE, "alerts/alerting/06_empty.yaml")
	cache := testhelper.MockCache(t, []testhelper.KeyValuePair{})
	defer cache.Close()
	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
	ctx = context.WithValue(ctx, constants.AlertingConfig, alertCfg)
	ctx = context.WithValue(ctx, constants.Cache, cache)

	// GET isn't allowed
	resetMetrics()
	req := testhelper.MockRequest("GET", ctx, nil)
	resp := httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusMethodNotAllowed, resp.Code)
	// Received metric is increased even though request is rejected. Others don't budge
	ctrReceived, _ := metricValue("connaisseur_requests_total")
	ctrAdmit, _ := metricValue("connaisseur_admissions_succeeded_total")
	ctrDeny, _ := metricValue("connaisseur_requests_failed_total", "false")
	ctrTimeout, _ := metricValue("connaisseur_admissions_timeouted_total")
	assert.Equal(t, float64(1), ctrReceived)
	assert.Equal(t, float64(0), ctrAdmit)
	assert.Equal(t, float64(0), ctrDeny)
	assert.Equal(t, float64(0), ctrTimeout)

	// Non-standard method isn't allowed
	req = testhelper.MockRequest("YOLO", ctx, nil)
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusMethodNotAllowed, resp.Code)

	// Needs correct content type
	req = testhelper.MockRequest("POST", ctx, nil)
	req.Header.Del("Content-Type")
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusBadRequest, resp.Code)

	// Request body nil, probably not possible in practice
	req = testhelper.MockRequest("POST", ctx, nil)
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusBadRequest, resp.Code)

	// Empty request body leads to 400
	req = testhelper.MockRequest("POST", ctx, strings.NewReader(""))
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusBadRequest, resp.Code)

	// Request body cannot be read
	req = testhelper.MockRequest("POST", ctx, &testhelper.MockReader{Err: fmt.Errorf("error")})
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusInternalServerError, resp.Code)

	// Empty JSON doesn't panic Connaisseur
	req = testhelper.MockRequest("POST", ctx, strings.NewReader("{}"))
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusBadRequest, resp.Code)

	// Invalid request JSON will lead to 400
	req = testhelper.MockRequest("POST", ctx, strings.NewReader("{"))
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusBadRequest, resp.Code)

	// Deny_me is handled and will be rejected
	resetMetrics()
	json, _ := os.Open(PRE + "admission_requests/17_deny_me_pod.json")
	req = testhelper.MockRequest("POST", ctx, json)
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusOK, resp.Code)
	ar := testhelper.UnmarshalAdmissionReview(resp)
	assert.Equal(t, false, ar.Response.Allowed)
	// Metrics increase as expected
	ctrReceived, _ = metricValue("connaisseur_requests_total")
	ctrAdmit, _ = metricValue("connaisseur_admissions_succeeded_total")
	ctrDeny, _ = metricValue("connaisseur_requests_failed_total", "false")
	ctrTimeout, _ = metricValue("connaisseur_admissions_timeouted_total")
	assert.Equal(t, float64(1), ctrReceived)
	assert.Equal(t, float64(0), ctrAdmit)
	assert.Equal(t, float64(1), ctrDeny)
	assert.Equal(t, float64(0), ctrTimeout)

	// Allow_me is handled and will be accepted
	resetMetrics()
	json, _ = os.Open(PRE + "admission_requests/18_allow_me_pod.json")
	req = testhelper.MockRequest("POST", ctx, json)
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusOK, resp.Code)
	ar = testhelper.UnmarshalAdmissionReview(resp)
	assert.Equal(t, true, ar.Response.Allowed)
	// Metrics increase as expected
	ctrReceived, _ = metricValue("connaisseur_requests_total")
	ctrAdmit, _ = metricValue("connaisseur_admissions_succeeded_total")
	ctrDeny, _ = metricValue("connaisseur_requests_failed_total", "false")
	ctrTimeout, _ = metricValue("connaisseur_admissions_timeouted_total")
	assert.Equal(t, float64(1), ctrReceived)
	assert.Equal(t, float64(1), ctrAdmit)
	assert.Equal(t, float64(0), ctrDeny)
	assert.Equal(t, float64(0), ctrTimeout)

	// Deny_me is handled and will be allowed if detection mode is on
	resetMetrics()
	t.Setenv(constants.DetectionMode, "true")
	json, _ = os.Open(PRE + "admission_requests/17_deny_me_pod.json")
	req = testhelper.MockRequest("POST", ctx, json)
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusOK, resp.Code)
	ar = testhelper.UnmarshalAdmissionReview(resp)
	assert.Equal(t, true, ar.Response.Allowed)
	assert.Contains(t, ar.Response.Warnings, "detection mode active")
	t.Setenv(constants.DetectionMode, "")
	// Metrics increase for final decision, not depending on validation output
	ctrReceived, _ = metricValue("connaisseur_requests_total")
	ctrAdmit, _ = metricValue("connaisseur_admissions_succeeded_total")
	ctrDeny, _ = metricValue("connaisseur_requests_failed_total", "false")
	ctrTimeout, _ = metricValue("connaisseur_admissions_timeouted_total")
	assert.Equal(t, float64(1), ctrReceived)
	assert.Equal(t, float64(1), ctrAdmit)
	assert.Equal(t, float64(0), ctrDeny)
	assert.Equal(t, float64(0), ctrTimeout)

	// Enabled automatic unchanged approval doesn't panic Connaisseur
	json, _ = os.Open(PRE + "admission_requests/18_allow_me_pod.json")
	t.Setenv(
		constants.AutomaticUnchangedApproval,
		strconv.FormatBool(true),
	) // ! WARNING ! side effect not cleaned up during this test
	req = testhelper.MockRequest("POST", ctx, json)
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusOK, resp.Code)

	// Edge case of handling a null admission request
	json, _ = os.Open(PRE + "admission_requests/25_null_request.json")
	t.Setenv(
		constants.AutomaticUnchangedApproval,
		strconv.FormatBool(false),
	) // ! WARNING ! side effect not cleaned up during this test
	req = testhelper.MockRequest("POST", ctx, json)
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusBadRequest, resp.Code)
	assert.Equal(t, "received empty admission request\n", resp.Body.String())
}

func TestHandleMutateSendNotifications(t *testing.T) {
	handler := http.HandlerFunc(HandleMutate)
	srv, c := testhelper.HTTPWebhookMock()
	defer srv.Close()

	cfg, _ := config.Load(PRE, "config/10_mutate_test.yaml")
	alertCfg, _ := alerting.LoadConfig(PRE, "alerts/alerting/03_send_notif_test.yaml")
	cache := testhelper.MockCache(t, []testhelper.KeyValuePair{})
	defer cache.Close()

	for i := range alertCfg.AdmitRequests.Receivers {
		r := alertCfg.AdmitRequests.Receivers[i].(*alerting.Channel)
		r.URL = srv.URL + "/"
	}
	for i := range alertCfg.RejectRequests.Receivers {
		r := alertCfg.RejectRequests.Receivers[i].(*alerting.Channel)
		r.URL = srv.URL + "/"
	}

	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
	ctx = context.WithValue(ctx, constants.AlertingConfig, alertCfg)
	ctx = context.WithValue(ctx, constants.Cache, cache)

	json, _ := os.Open(PRE + "admission_requests/18_allow_me_pod.json")
	req := testhelper.MockRequest("POST", ctx, json)
	resp := httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusOK, resp.Code)
	ar := testhelper.UnmarshalAdmissionReview(resp)
	assert.Equal(t, true, ar.Response.Allowed)
	assert.Equal(t, `{"cluster":"test","message":"CONNAISSEUR admitted a request"}`, c.ReceivedBody)

	alertCfg, _ = alerting.LoadConfig(PRE, "alerts/alerting/07_send_notif_success_and_fail.yaml")
	for i := range alertCfg.AdmitRequests.Receivers {
		r := alertCfg.AdmitRequests.Receivers[i].(*alerting.Channel)
		r.URL = srv.URL + "/"
	}
	for i := range alertCfg.RejectRequests.Receivers {
		r := alertCfg.RejectRequests.Receivers[i].(*alerting.Channel)
		r.URL = srv.URL + "/"
	}

	ctx = context.WithValue(ctx, constants.AlertingConfig, alertCfg)
	json, _ = os.Open(PRE + "admission_requests/18_allow_me_pod.json")
	req = testhelper.MockRequest("POST", ctx, json)
	resp = httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusOK, resp.Code)
	ar = testhelper.UnmarshalAdmissionReview(resp)
	assert.Equal(t, false, ar.Response.Allowed)
	assert.Equal(t, `{"fail":true}`, c.ReceivedBody)
}

func TestHandleMutatePodsOnly(t *testing.T) {
	t.Setenv(constants.ResourceValidationMode, "podsOnly")

	handler := http.HandlerFunc(HandleMutate)
	cfg, _ := config.Load(PRE, "config/10_mutate_test.yaml")
	alertCfg, _ := alerting.LoadConfig(PRE, "alerts/alerting/06_empty.yaml")
	cache := testhelper.MockCache(t, []testhelper.KeyValuePair{})
	defer cache.Close()
	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
	ctx = context.WithValue(ctx, constants.AlertingConfig, alertCfg)
	ctx = context.WithValue(ctx, constants.Cache, cache)

	// Deny_me non-pod is handled and will be accepted
	resp, ar := request(ctx, PRE+"admission_requests/14_deny_me_job.json", handler)
	assert.Equal(t, http.StatusOK, resp.Code)
	assert.True(t, ar.Response.Allowed)

	// non pod resources are not mutated
	cfg.Validators = append(cfg.Validators, validator.Validator{
		Name:              "mock",
		Type:              "mock",
		SpecificValidator: testhelper.MockAllowValidator{},
	})
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
	resp, ar = request(ctx, PRE+"admission_requests/01_deployment.json", handler)
	assert.Equal(t, http.StatusOK, resp.Code)
	assert.True(t, ar.Response.Allowed)
	assert.Equal(t, []uint8([]byte(nil)), ar.Response.Patch)

	// resource validation mode wins over detection mode for non-pod resources
	t.Setenv(constants.DetectionMode, "true")
	resp, ar = request(ctx, PRE+"admission_requests/14_deny_me_job.json", handler)
	assert.Equal(t, http.StatusOK, resp.Code)
	assert.True(t, ar.Response.Allowed)
	assert.Contains(t, ar.Response.Warnings, "pod-only validation active")
	assert.NotContains(t, ar.Response.Warnings, "detection mode active")

	// detection mode still triggers for pods
	resp, ar = request(ctx, PRE+"admission_requests/17_deny_me_pod.json", handler)
	assert.Equal(t, http.StatusOK, resp.Code)
	assert.True(t, ar.Response.Allowed)
	assert.Contains(t, ar.Response.Warnings, "detection mode active")
	assert.NotContains(t, ar.Response.Warnings, "pod-only validation active")
}

// This tests that the default is to block all resources
func TestHandleMutateDefaultAllResources(t *testing.T) {
	handler := http.HandlerFunc(HandleMutate)
	cfg, _ := config.Load(PRE, "config/10_mutate_test.yaml")
	alertCfg, _ := alerting.LoadConfig(PRE, "alerts/alerting/06_empty.yaml")
	cache := testhelper.MockCache(t, []testhelper.KeyValuePair{})
	defer cache.Close()
	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
	ctx = context.WithValue(ctx, constants.AlertingConfig, alertCfg)
	ctx = context.WithValue(ctx, constants.Cache, cache)

	// Deny_me non-pod is handled and will be denied by default
	json, _ := os.Open(PRE + "admission_requests/14_deny_me_job.json")
	req := testhelper.MockRequest("POST", ctx, json)
	resp := httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusOK, resp.Code)
	ar := testhelper.UnmarshalAdmissionReview(resp)
	assert.False(t, ar.Response.Allowed)
}

func TestHandleMutateTimeoutMetrics(t *testing.T) {
	handler := http.HandlerFunc(HandleMutate)
	cfg, _ := config.Load(PRE, "config/10_mutate_test.yaml")
	alertCfg, _ := alerting.LoadConfig(PRE, "alerts/alerting/06_empty.yaml")
	cache := testhelper.MockCache(t, []testhelper.KeyValuePair{})
	defer cache.Close()
	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
	ctx = context.WithValue(ctx, constants.AlertingConfig, alertCfg)
	ctx = context.WithValue(ctx, constants.Cache, cache)
	ctx, cancel := context.WithCancel(ctx)
	cancel()

	// Reset previous metrics (executions of other tests in the same pkg play into it)
	resetMetrics()

	json, _ := os.Open(PRE + "admission_requests/18_allow_me_pod.json")
	req := testhelper.MockRequest("POST", ctx, json)
	resp := httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	assert.Equal(t, http.StatusOK, resp.Code)
	ar := testhelper.UnmarshalAdmissionReview(resp)
	assert.Equal(t, false, ar.Response.Allowed)
	// Timeout metric increases, normal failure doesn't
	ctrReceived, _ := metricValue("connaisseur_requests_total")
	normalFailed, _ := metricValue("connaisseur_requests_failed_total", "false")
	timeouted, _ := metricValue("connaisseur_requests_failed_total", "true")
	assert.Equal(t, float64(1), ctrReceived)
	assert.Equal(t, float64(0), normalFailed)
	assert.Equal(t, float64(1), timeouted)
}

func TestMutateReview(t *testing.T) {
	var testCases = []struct {
		admissionFile      string
		allowed            bool
		patch              string
		cacheKey           string
		cacheValue         string
		err                string
		notificationResult string
	}{
		{ // 1: Admits and stores correct hash, when validation is successful. Produces a patch
			"01_deployment",
			true,
			`[{"op":"replace","path":"/spec/template/spec/containers/0/image","value":"index.docker.io/securesystemsengineering/alice-image:test@sha256:1234567890123456123456789012345612345678901234561234567890123456"}]`,
			"securesystemsengineering/alice-image:test",
			"{\"digest\":\"sha256:1234567890123456123456789012345612345678901234561234567890123456\",\"error\":\"\"}",
			"",
			constants.NotificationResultSuccess,
		},
		{ // 2: Denies with static_deny and caches error
			"14_deny_me_job",
			false, // While we allow Pods globally, that decision is taken one level above this function
			"",
			"my.reg/deny-me@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"",
			"static deny",
			constants.NotificationResultError,
		},
		{ // 3: Admits with static_allow and doesn't cache, producing no patch
			"18_allow_me_pod",
			true,
			"[]",
			"my.reg/allow-me@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"",
			"",
			constants.NotificationResultSuccess,
		},
		{ // 4: Denies image, where validation fails and caches error
			"04_cronjob",
			false,
			"",
			"busybox",
			"{\"digest\":\"\",\"error\":\"error during mock validation of image busybox: unabled to find signed digest for image docker.io/library/busybox:latest\"}",
			"unabled to find signed digest for image docker.io/library/busybox:latest",
			constants.NotificationResultError,
		},
		{ // 5: Admits with static_allow and caches success, producing no patch, even though index.docker.io/library would be appended
			"22_allow_me_with_index_docker_io",
			true,
			"[]",
			"test-image",
			"",
			"",
			constants.NotificationResultSuccess,
		},
		{ // 6: Admits and stores correct hash, when validation is successful. Produces no patch, since image reference doesn't change (sha only)
			"23_alice_digest_dpl",
			true,
			`[]`,
			"securesystemsengineering/alice-image@sha256:1234567890123456123456789012345612345678901234561234567890123456",
			"{\"digest\":\"sha256:1234567890123456123456789012345612345678901234561234567890123456\",\"error\":\"\"}",
			"",
			constants.NotificationResultSuccess,
		},
		{ // 7: Admits and stores correct hash, when validation is successful. Produces no patch, since image reference doesn't change (tag+sha)
			"24_alice_tag_digest_dpl",
			true,
			`[]`,
			"securesystemsengineering/alice-image:test@sha256:1234567890123456123456789012345612345678901234561234567890123456",
			"{\"digest\":\"sha256:1234567890123456123456789012345612345678901234561234567890123456\",\"error\":\"\"}",
			"",
			constants.NotificationResultSuccess,
		},
	}

	cache := testhelper.MockCache(t, []testhelper.KeyValuePair{})
	defer cache.Close()
	cfg, _ := config.Load(PRE, "config/10_mutate_test.yaml")
	cfg.Validators = append(
		cfg.Validators,
		validator.Validator{
			Name:              "mock",
			Type:              "mock",
			SpecificValidator: testhelper.MockValidator{},
		},
	)

	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
	ctx = context.WithValue(ctx, constants.Cache, cache)

	for i, tc := range testCases {

		ar := testhelper.RetrieveAdmissionReview(PRE + "admission_requests/" + tc.admissionFile + ".json")

		res, nv := mutateReview(ctx, *ar)
		// Allow/deny as expected
		assert.Equal(t, tc.allowed, res.Allowed, tc.admissionFile, "test case %d", i+1)
		assert.Equal(t, tc.notificationResult, nv.Result)

		// Patch as expected or not present if not expected
		if tc.patch != "" {
			assert.Equalf(t, []byte(tc.patch), res.Patch, "test case %d", i+1)
		} else {
			assert.Nil(t, res.Patch, "test case %d", i+1)
		}

		// Cache value is as expected
		if tc.cacheKey != "" {
			if tc.cacheValue != "" {
				value, err := cache.Get(ctx, tc.cacheKey)
				assert.Equalf(t, tc.cacheValue, value, "test case %d", i+1)
				// Clean up key for subsequent tests
				_ = cache.Del(ctx, tc.cacheKey)
				assert.Nil(t, err)
			} else {
				_, err := cache.Get(ctx, tc.cacheKey)
				assert.NotNilf(t, err, "test case %d", i+1)
			}
		}

		// Error as expected or not present if not expected
		if tc.err != "" {
			assert.Contains(t, res.Result.Message, tc.err, tc.admissionFile, "test case %d", i+1)
		} else {
			assert.Nil(t, res.Result, "test case %d", i+1)
		}
	}

	// Check that no more cache keys were set than expected
	remainingKeys, err := cache.Keys(ctx, "*")
	assert.Nil(t, err, "unable to get remaining keys")
	assert.Equal(
		t,
		0,
		len(remainingKeys),
		"There are still cache keys set, indicating that a key was set unexpectedly",
	)
}

func TestMutateReviewInvalidKind(t *testing.T) {
	var testCases = []struct {
		admissionFile string
		err           string
	}{
		{ // Fails for an unexpected object in admission request
			"11_role",
			"unknown workload kind",
		},
	}

	for _, tc := range testCases {
		ar := testhelper.RetrieveAdmissionReview(PRE + "admission_requests/" + tc.admissionFile + ".json")

		res, nv := mutateReview(context.Background(), *ar)
		// Denied as expected
		assert.Equal(t, false, res.Allowed, tc.admissionFile)
		assert.Equal(t, constants.NotificationResultInvalid, nv.Result)

		// Patch not present
		assert.Nil(t, res.Patch)

		// Error as expected
		assert.Contains(t, res.Result.Message, tc.err, tc.admissionFile)
	}
}

func TestMutateReviewCached(t *testing.T) {
	var testCases = []struct {
		admissionFile      string
		allowed            bool
		patch              string
		cacheKey           string
		cacheValue         string
		err                string
		notificationResult string
	}{
		{ // Admits with patch
			"01_deployment",
			true,
			`[{"op":"replace","path":"/spec/template/spec/containers/0/image","value":"index.docker.io/securesystemsengineering/alice-image:test@sha256:1234567890123456123456789012345612345678901234561234567890123456"}]`,
			"securesystemsengineering/alice-image:test",
			"{\"digest\":\"sha256:1234567890123456123456789012345612345678901234561234567890123456\",\"error\":\"\"}",
			"",
			constants.NotificationResultSkip,
		},
		{ // Admits without patch
			"18_allow_me_pod",
			true,
			"[]",
			"my.reg/allow-me@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"{\"digest\":\"sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff\",\"error\":\"\"}",
			"",
			constants.NotificationResultSkip,
		},
		{ // Denies
			"14_deny_me_job",
			false, // While we allow Pods globally, that decision is taken one level above this function
			"",
			"my.reg/deny-me@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"{\"digest\":\"\",\"error\":\"error during static validation of image my.reg/deny-me@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff: static deny\"}",
			"static deny",
			constants.NotificationResultError,
		},
	}

	cache := testhelper.MockCache(t, []testhelper.KeyValuePair{})
	defer cache.Close()
	// Config references a validator that is set to be not implemented below and would thus panic if
	// called.
	// Thus we know any results in the below validation must come from the cache
	cfg, _ := config.Load(PRE, "config/12_mutate_test_cached.yaml")
	cfg.Validators = append(
		cfg.Validators,
		validator.Validator{
			Name:              "notImplemented",
			Type:              "notImplemented",
			SpecificValidator: nil,
		},
	)
	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
	ctx = context.WithValue(ctx, constants.Cache, cache)

	for idx, tc := range testCases {
		// Prepare Redis
		err := cache.Set(ctx, tc.cacheKey, tc.cacheValue, 30*time.Second)
		assert.Nil(t, err, "test case %d", idx+1)

		ar := testhelper.RetrieveAdmissionReview(PRE + "admission_requests/" + tc.admissionFile + ".json")

		res, nv := mutateReview(ctx, *ar)
		// Allow/deny as expected
		assert.Equal(t, tc.allowed, res.Allowed, tc.admissionFile, "test case %d", idx+1)
		assert.Equal(t, tc.notificationResult, nv.Result, tc.admissionFile, "test case %d", idx+1)

		// Patch as expected or not present if not expected
		if tc.patch != "" {
			assert.Equal(t, []byte(tc.patch), res.Patch, "test case %d", idx+1)
		} else {
			assert.Nil(t, res.Patch, "test case %d", idx+1)
		}

		// Error as expected or not present if not expected
		if tc.err != "" {
			assert.Contains(t, res.Result.Message, tc.err, tc.admissionFile, "test case %d", idx+1)
		} else {
			assert.Nil(t, res.Result, "test case %d", idx+1)
		}

		// Clean up key for subsequent tests
		err = cache.Del(ctx, tc.cacheKey)
		assert.Nil(t, err, "test case %d", idx+1)
	}
}

func TestMutateReviewCancelledContext(t *testing.T) {
	cache := testhelper.MockCache(t, []testhelper.KeyValuePair{})
	defer cache.Close()
	cfg, _ := config.Load(PRE, "config/10_mutate_test.yaml")

	ctx := context.Background()
	ctx = context.WithValue(ctx, constants.ConnaisseurConfig, cfg)
	ctx = context.WithValue(ctx, constants.Cache, cache)
	ctx, cancel := context.WithCancel(ctx)
	cancel()

	ar := testhelper.RetrieveAdmissionReview(PRE + "admission_requests/01_deployment.json")

	res, nv := mutateReview(ctx, *ar)
	assert.False(t, res.Allowed)
	assert.Equal(t, constants.NotificationResultTimeout, nv.Result)
	assert.Contains(t, res.Result.Message, "timed out")
}

func metricValue(name string, label ...string) (float64, error) {
	var m = &dto.Metric{}
	switch name {
	case "connaisseur_requests_total":
		_ = numAdmissionsReceived.Write(m)
	case "connaisseur_admissions_succeeded_total":
		_ = numAdmissionsAdmitted.Write(m)
	case "connaisseur_requests_failed_total":
		labelled, _ := numAdmissionsDenied.GetMetricWith(
			prometheus.Labels{"timeout": label[0]},
		)
		_ = labelled.Write(m)
	default:
		return 0, fmt.Errorf("metric %s doesn't exist or wasn't exposed", name)
	}

	return *m.Counter.Value, nil
}

func resetMetrics() {
	// // Counters cannot be reset directly :(  https://github.com/prometheus-net/prometheus-net/issues/63
	prometheus.DefaultRegisterer.Unregister(numAdmissionsReceived)
	prometheus.DefaultRegisterer.Unregister(numAdmissionsAdmitted)
	numAdmissionsReceived = promauto.NewCounter(prometheus.CounterOpts{
		Name: "connaisseur_requests_total",
		Help: "The total number of admission requests posed to Connaisseur",
	})
	numAdmissionsAdmitted = promauto.NewCounter(prometheus.CounterOpts{
		Name: "connaisseur_requests_admitted_total",
		Help: "The total number of admission requests that were admitted",
	})

	// CounterVecs can :)
	numAdmissionsDenied.Reset()
}

func request(ctx context.Context, path string, handler http.HandlerFunc) (*httptest.ResponseRecorder, *v1.AdmissionReview) {
	json, _ := os.Open(path)
	req := testhelper.MockRequest("POST", ctx, json)
	resp := httptest.NewRecorder()
	handler.ServeHTTP(resp, req)
	return resp, testhelper.UnmarshalAdmissionReview(resp)
}
