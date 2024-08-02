package handler

import (
	alerting "connaisseur/internal/alert"
	"connaisseur/internal/constants"
	"connaisseur/internal/handler/validation"
	"connaisseur/internal/kubernetes"
	"connaisseur/internal/utils"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/sirupsen/logrus"
	admission "k8s.io/api/admission/v1"
	meta "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime/schema"
)

func HandleMutate(w http.ResponseWriter, r *http.Request) {
	IncAdmissionsReceived()
	ctx, cancel := context.WithTimeout(r.Context(), constants.ValidationTimeoutSeconds*time.Second)
	defer cancel()
	handleMutate(ctx, w, r)
}

// Handles the /mutate route.
func handleMutate(ctx context.Context, w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodPost:
		contentType := r.Header.Get("Content-Type")
		if contentType != "application/json" {
			handleError(
				w,
				fmt.Sprintf("wrong content type: expected json, got %s", contentType),
				http.StatusBadRequest,
			)
			return
		}

		// read request
		var body []byte
		if data, err := io.ReadAll(r.Body); err == nil {
			body = data
			logrus.Debugf("request body: %s", string(body))
		} else {
			handleError(w, fmt.Sprintf("error reading request body: %v", err), http.StatusInternalServerError)
			return
		}

		var (
			reviewResponse     *admission.AdmissionResponse
			notificationValues *alerting.NotificationValues
		)
		ar := admission.AdmissionReview{}
		// transform request into AdmissionReview
		if err := json.Unmarshal(body, &ar); err != nil {
			handleError(w, fmt.Sprintf("received invalid json: %v", err), http.StatusBadRequest)
			return
		} else {
			if ar.Request == nil {
				handleError(w, "received empty admission request", http.StatusBadRequest)
				return
			}

			// create response for AdmissionReview
			reviewResponse, notificationValues = mutateReview(ctx, ar)
		}

		alerting := ctx.Value(constants.AlertingConfig).(*alerting.Config)
		err := alerting.EvalAndSendNotifications(ctx, notificationValues)
		if err != nil {
			logrus.Errorf("error sending notifications: %v", err)
			reviewResponse.Allowed = false
			reviewResponse.Result = &meta.Status{
				Message: fmt.Sprintf(
					" error sending notifications: %v",
					err,
				),
			}
		}

		// set response for AdmissionReview. also set the
		// group version kind, so that the response is
		// accepted by the api server
		response := admission.AdmissionReview{
			Response: reviewResponse,
		}
		response.SetGroupVersionKind(schema.FromAPIVersionAndKind(ar.APIVersion, ar.Kind))

		// handle features that change the admission response
		if ar.Request != nil {
			// resource validation mode
			if ar.Request.Kind.Kind != "Pod" && !utils.BlockAllResources() {
				if !response.Response.Allowed {
					response.Response.Warnings = []string{
						"pod-only validation active",
						response.Response.Result.Message,
					}
				}
				response.Response.Allowed = true
				response.Response.Patch = nil
				response.Response.PatchType = nil
			}

			// detection mode
			if utils.FeatureFlagOn(constants.DetectionMode) && !response.Response.Allowed {
				response.Response.Warnings = []string{
					"detection mode active",
					response.Response.Result.Message,
				}
				response.Response.Allowed = true
			}
		}

		// increment admission metrics
		if response.Response.Allowed {
			IncAdmissionsAdmitted()
		} else {
			// differentiate timeout and regular error
			select {
			case <-ctx.Done():
				IncAdmissionsDenied(true)
			default:
				IncAdmissionsDenied(false)
			}
		}

		// write AdmissionReview response
		respBytes, err := json.Marshal(response)
		if err != nil {
			handleError(
				w,
				fmt.Sprintf("error marshalling response: %v", err),
				http.StatusInternalServerError,
			)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		if _, err := w.Write(respBytes); err != nil {
			logrus.Errorf("error writing respons: %v", err)
		}
	default:
		handleError(
			w,
			fmt.Sprintf("%s: %s", constants.MethodNotAllowed, r.Method),
			http.StatusMethodNotAllowed,
		)
	}
}

// Writes an error message to the response and logs it.
func handleError(w http.ResponseWriter, msg string, code int) {
	logrus.Error(msg)
	http.Error(w, msg, code)
}

// Mutates an AdmissionReview, validating all image in the process.
func mutateReview(ctx context.Context, ar admission.AdmissionReview) (*admission.AdmissionResponse, *alerting.NotificationValues) {
	notificationValues := &alerting.NotificationValues{
		RequestId:        string(ar.Request.UID),
		Namespace:        ar.Request.Namespace,
		ConnaisseurPodId: os.Getenv(constants.PodName),
	}

	// extract containers, init containers and ephemeral containers based on workload object
	aro, err := kubernetes.NewAdmissionRequestObjects(ar.Request)
	if err != nil {
		notificationValues.Result = constants.NotificationResultInvalid
		logrus.Errorf("error creating admission request objects: %v", err)
		return &admission.AdmissionResponse{Result: &meta.Status{
			Message: err.Error(),
		}}, notificationValues
	}
	ctx = context.WithValue(ctx, constants.RequestId, ar.Request.UID)
	// do validation
	validationChannel := validation.ValidateWorkloadObject(
		ctx,
		aro.NewObj,
		aro.OldObj,
	)

	// receive validation results and store them in a slice
	validationResults := make([]validation.ValidationOutput, 0)

	for i := 0; i < cap(validationChannel); i++ {
		select {
		case <-ctx.Done():
			notificationValues.Result = constants.NotificationResultTimeout
			return &admission.AdmissionResponse{
				UID: ar.Request.UID,
				Result: &meta.Status{
					Message: fmt.Sprintf(
						"validation of admission request %s timed out after validating %d/%d images",
						ar.Request.UID,
						i,
						cap(validationChannel),
					),
				}}, notificationValues
		case valOut := <-validationChannel:
			// return error, if validation failed or any
			// other error occurred
			if valOut.Error != nil {
				logrus.Errorf(
					"error validating %s %s: %v",
					aro.NewObj.Kind,
					aro.NewObj.Name,
					valOut.Error,
				)

				notificationValues.Result = constants.NotificationResultError
				notificationValues.Error = valOut.Error
				notificationValues.Images = valOut.RawImage
				return &admission.AdmissionResponse{
					UID: ar.Request.UID,
					Result: &meta.Status{
						Message: valOut.Error.Error(),
					}}, notificationValues
			}

			validationResults = append(validationResults, valOut)
		}
	}

	jsonPatches := make([]string, 0)
	images := make([]string, 0)
	skipped := true
	for _, valOut := range validationResults {
		// build json patch from validation results, but only if
		// validation mode is set to mutate and the image reference
		// has changed
		if valOut.ValidationMode == constants.MutateMode && (valOut.NewImage != valOut.OldImage) {
			for _, idxType := range valOut.IdxsTypes {
				path := fmt.Sprintf(
					aro.NewObj.ContainerPathFormatString(),
					idxType.Type,
					idxType.Index,
				) // by virtue of IdxType, this isn't injectable
				patch := fmt.Sprintf(
					`{"op":"replace","path":"%s","value":"%s"}`,
					path,
					valOut.NewImage,
				)
				jsonPatches = append(jsonPatches, patch)
				images = append(images, valOut.RawImage)
			}
		}
		skipped = skipped && valOut.Skipped
	}

	ares := admission.AdmissionResponse{
		UID:     ar.Request.UID,
		Allowed: true,
	}
	if len(jsonPatches) > 0 {
		pt := admission.PatchTypeJSONPatch
		ares.PatchType = &pt
		ares.Patch = []byte("[" + strings.Join(jsonPatches, ",") + "]")
	}

	notificationValues.Images = strings.Join(images, ", ")
	if skipped {
		notificationValues.Result = constants.NotificationResultSkip
	} else {
		notificationValues.Result = constants.NotificationResultSuccess
	}

	return &ares, notificationValues
}
