package testhelper

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http/httptest"
	"os"

	"github.com/theupdateframework/notary/tuf/data"
	admission "k8s.io/api/admission/v1"
)

func RetrieveAdmissionReview(path string) *admission.AdmissionReview {
	ar := admission.AdmissionReview{}
	data, err := os.ReadFile(path)
	if err != nil {
		panic(fmt.Sprintf("Test file not found: %s", path))
	}

	err = json.Unmarshal(data, &ar)
	if err != nil {
		panic("can't unmarshal data in response")
	}
	return &ar
}

func UnmarshalAdmissionReview(resp *httptest.ResponseRecorder) *admission.AdmissionReview {
	ar := admission.AdmissionReview{}
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		panic("couldn't read from body")
	}
	err = json.Unmarshal(data, &ar)
	if err != nil {
		panic("can't unmarshal data in response")
	}

	return &ar
}

func retrieveSigned(path string) (*data.Signed, []byte) {
	var signed data.Signed

	signedBytes, _ := os.ReadFile(path)
	json.Unmarshal(signedBytes, &signed)

	// marshal again to get bytes with correct formatting
	signedBytes, _ = json.Marshal(signed)

	return &signed, signedBytes
}

func TargetData(path string) (*data.SignedTargets, []byte) {
	signed, b := retrieveSigned(path)
	target, _ := data.TargetsFromSigned(signed, data.RoleName("targets"))

	return target, b
}

func RootData(path string) (*data.SignedRoot, []byte) {
	signed, b := retrieveSigned(path)
	root, err := data.RootFromSigned(signed)

	if err != nil {
		log.Printf("error parsing root.json: %s", err)
	}

	return root, b
}

func SnapshotData(path string) (*data.SignedSnapshot, []byte) {
	signed, b := retrieveSigned(path)
	snapshot, _ := data.SnapshotFromSigned(signed)

	return snapshot, b
}

func TimestampData(path string) (*data.SignedTimestamp, []byte) {
	signed, b := retrieveSigned(path)
	timestamp, _ := data.TimestampFromSigned(signed)

	return timestamp, b
}

func DelegationData(path string, role string) (*data.SignedTargets, []byte) {
	signed, b := retrieveSigned(path)
	delegation, _ := data.TargetsFromSigned(signed, data.RoleName(role))

	return delegation, b
}
