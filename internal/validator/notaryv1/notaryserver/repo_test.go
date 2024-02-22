package notaryserver

import (
	"connaisseur/internal/image"
	"connaisseur/internal/validator/auth"
	"connaisseur/test/testhelper"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/pem"
	"fmt"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/theupdateframework/notary/tuf/data"
)

const PRE = "../../../../test/testdata/notaryv1/"

func testGetCustomRepo(
	t *testing.T,
	rootPath, targetsPath, snapshotPath, timestampPath string,
) *Repo {
	root, rootBytes := testhelper.RootData(rootPath + ".json")
	targets, targetsBytes := testhelper.TargetData(targetsPath + ".json")
	snapshot, snapshotBytes := testhelper.SnapshotData(snapshotPath + ".json")
	timestamp, timestampBytes := testhelper.TimestampData(timestampPath + ".json")

	return &Repo{
		Root:      root,
		Targets:   map[string]*data.SignedTargets{data.CanonicalTargetsRole.String(): targets},
		Snapshot:  snapshot,
		Timestamp: timestamp,
		notCheckedChecksums: map[string][]byte{
			data.CanonicalRootRole.String():      rootBytes,
			data.CanonicalTargetsRole.String():   targetsBytes,
			data.CanonicalSnapshotRole.String():  snapshotBytes,
			data.CanonicalTimestampRole.String(): timestampBytes,
		},
	}
}

func testGetRepo(t *testing.T, path string) *Repo {
	return testGetCustomRepo(t, path+"/root", path+"/targets", path+"/snapshot", path+"/timestamp")
}

func testGetRepoWithDelegations(t *testing.T, path string, delegations []string) *Repo {
	repo := testGetRepo(t, path)

	for _, delegation := range delegations {
		delegationSlice := strings.Split(delegation, "/")
		delegationRole := delegationSlice[len(delegationSlice)-1]
		signedDelegation, delegationBytes := testhelper.DelegationData(
			path+"/"+delegation+".json",
			fmt.Sprintf("targets/%s", delegationRole),
		)
		repo.Targets[delegation] = signedDelegation
		repo.notCheckedChecksums[delegation] = delegationBytes
	}

	return repo
}

func TestDownloadBaseTrustData(t *testing.T) {
	srv := testhelper.NotaryMock(BASE, true)
	ctx := context.Background()
	defer srv.Close()

	var testCases = []struct {
		image string
		shas  map[string]string
		err   string
	}{
		{
			"sample-image",
			map[string]string{
				"root":      "76d25d66f45387cce5ac088489a9bf0ac27554da9789098e6c8fdb00856612f7",
				"targets":   "e122a90e80a92c98ff7368d3e90f4c0f23e44df642737e5fede68578b85918c9",
				"snapshot":  "aa5ae7b7646bc4ecd5c80efaf066ff024293039fd2e52793fc8e5ca828c691c9",
				"timestamp": "c9d08b57b39768cde9b30ea7bd73398eac0cafb66080bb301866c3f48565a140",
			},
			"",
		},
		{
			"there-is-no-image",
			map[string]string{},
			"error acquiring trust data",
		},
		{
			"err-image",
			map[string]string{},
			"error parsing trust data",
		},
	}

	for _, tc := range testCases {
		img, _ := image.New(tc.image)
		nc, _ := NewNotaryClient(srv.URL, "", auth.Auth{}, img)

		repo := &Repo{}
		err := repo.DownloadBaseTrustData(ctx, nc)

		if tc.err != "" {
			assert.NotNil(t, err)
			assert.ErrorContains(t, err, tc.err)
		} else {
			assert.Nil(t, err)
			for role, sha := range tc.shas {
				shaaa := sha256.Sum256(repo.notCheckedChecksums[role])
				assert.Equal(t, sha, hex.EncodeToString(shaaa[:]))
			}
		}
	}
}

func TestValidateRoot(t *testing.T) {
	var testCases = []struct {
		image string
		keys  []string
		err   string
	}{
		{ // 1
			"sample-image/root",
			[]string{`-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtR5kwrDK22SyCu7WMF8tCjVgeORA
S2PWacRcBN/VQdVK4PVk1w4pMWlz9AHQthDGl+W2k3elHkPbR+gNkK2PCA==
-----END PUBLIC KEY-----`},
			"",
		},
		{ // 2
			"sample-image/root",
			[]string{`-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEvtc/qpHtx7iUUj+rRHR99a8mnGni
qiGkmUb9YpWWTS4YwlvwdmMDiGzcsHiDOYz6f88u2hCRF5GUCvyiZAKrsA==
-----END PUBLIC KEY-----`},
			"error validating root signature",
		},
		{ // 3
			"01_expired_root",
			[]string{`-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEUaqgujac1VCdaGHKQMKoDn6/deWJ
8cCzsnDqGDgjPBayhJCQiI/qN+iBWEUPM7BkrCyDS878h+qd/MdZS22XwA==
-----END PUBLIC KEY-----`},
			"root trust data expired",
		},
		{ // 4
			"07_root_multiple_signatures",
			[]string{
				`-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEUaqgujac1VCdaGHKQMKoDn6/deWJ
8cCzsnDqGDgjPBayhJCQiI/qN+iBWEUPM7BkrCyDS878h+qd/MdZS22XwA==
-----END PUBLIC KEY-----`,
				`-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEnsF6hghdCI5MUEEge8PqtSe1HB3O
88lEztfMO+LaUBCyX1aoeB36MrkqeM4zrWe2UUSxFuL6y/+qiPQQQ/n7Ww==
-----END PUBLIC KEY-----`,
			},
			"",
		},
		{ // 5
			"07_root_multiple_signatures",
			[]string{
				`-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEnsF6hghdCI5MUEEge8PqtSe1HB3O
88lEztfMO+LaUBCyX1aoeB36MrkqeM4zrWe2UUSxFuL6y/+qiPQQQ/n7Ww==
-----END PUBLIC KEY-----`,
				`-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEUaqgujac1VCdaGHKQMKoDn6/deWJ
8cCzsnDqGDgjPBayhJCQiI/qN+iBWEUPM7BkrCyDS878h+qd/MdZS22XwA==
-----END PUBLIC KEY-----`,
			},
			"",
		},
		{ // 6
			"never-expire-image/root",
			[]string{`-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEUaqgujac1VCdaGHKQMKoDn6/deWJ
8cCzsnDqGDgjPBayhJCQiI/qN+iBWEUPM7BkrCyDS878h+qd/MdZS22XwA==
-----END PUBLIC KEY-----`},
			"",
		},
		{ // 7
			"06_no_signature_root",
			[]string{},
			"no signatures found for root",
		},
	}

	for idx, tc := range testCases {
		keys := []data.PublicKey{}
		for _, key := range tc.keys {
			pubDecode, _ := pem.Decode([]byte(key))
			keys = append(keys, data.NewPublicKey("ecdsa", pubDecode.Bytes))
		}

		root, _ := testhelper.RootData(PRE + "trust_data/" + tc.image + ".json")
		repo := &Repo{Root: root}
		err := repo.validateRoot(keys)

		if tc.err != "" {
			assert.NotNil(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.Nil(t, err, idx+1)
		}
	}
}

func TestValidateRestOfBase(t *testing.T) {
	var testCases = []struct {
		repo  string
		paths []string
		err   string
	}{
		{ // 1
			"never-expire-image",
			[]string{},
			"",
		},
		{ // 2
			"",
			[]string{
				"never-expire-image/root",
				"02_invalid_signature_targets",
				"never-expire-image/snapshot",
				"never-expire-image/timestamp",
			},
			"error validating targets signatures",
		},
		{ // 3
			"",
			[]string{
				"never-expire-image/root",
				"never-expire-image/targets",
				"03_expired_snapshot",
				"never-expire-image/timestamp",
			},
			"snapshot trust data expired",
		},
	}

	for idx, tc := range testCases {
		var repo *Repo

		if tc.repo != "" {
			repo = testGetRepo(t, PRE+"trust_data/"+tc.repo)
		} else {
			repo = testGetCustomRepo(t,
				PRE+"trust_data/"+tc.paths[0],
				PRE+"trust_data/"+tc.paths[1],
				PRE+"trust_data/"+tc.paths[2],
				PRE+"trust_data/"+tc.paths[3],
			)
		}
		err := repo.validateRestOfBase()

		if tc.err != "" {
			assert.NotNil(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.Nil(t, err, idx+1)
		}
	}

	// 4
	repo := testGetRepo(t, PRE+"trust_data/never-expire-image")
	repo.Root.Signed.Keys = map[string]data.PublicKey{"x": data.NewPublicKey("ecdsa", []byte("invalid"))}

	err := repo.validateRestOfBase()
	assert.NotNil(t, err, 4)
	assert.ErrorContains(t, err, "error building base role", 4)
}

func TestValidateBaseChecksums(t *testing.T) {
	repo := testGetRepo(t, PRE+"trust_data/never-expire-image")
	err := repo.validateBaseChecksums()

	assert.Nil(t, err)

	delete(repo.notCheckedChecksums, data.CanonicalRootRole.String())
	err = repo.validateBaseChecksums()
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "no checksums found for root")

	repo.notCheckedChecksums[data.CanonicalRootRole.String()] = []byte("invalid")
	err = repo.validateBaseChecksums()
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "error validating root checksums")
}

func TestValidateBaseTrustData(t *testing.T) {
	pem, _ := pem.Decode([]byte(`-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEUaqgujac1VCdaGHKQMKoDn6/deWJ
8cCzsnDqGDgjPBayhJCQiI/qN+iBWEUPM7BkrCyDS878h+qd/MdZS22XwA==
-----END PUBLIC KEY-----`))
	key := []data.PublicKey{data.NewPublicKey("ecdsa", pem.Bytes)}

	repo := testGetRepo(t, PRE+"trust_data/never-expire-image")
	err := repo.ValidateBaseTrustData(key)
	assert.Nil(t, err)

	tmpTime := repo.Root.Signed.Expires
	repo.Root.Signed.Expires = time.Now().Add(-1 * time.Hour)
	err = repo.ValidateBaseTrustData(key)
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "error validating root")

	repo.Root.Signed.Expires = tmpTime
	tmpTime = repo.Snapshot.Signed.Expires
	repo.Snapshot.Signed.Expires = time.Now().Add(-1 * time.Hour)
	err = repo.ValidateBaseTrustData(key)
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "error validating base trust data")

	repo.Snapshot.Signed.Expires = tmpTime
	delete(repo.notCheckedChecksums, data.CanonicalRootRole.String())
	err = repo.ValidateBaseTrustData(key)
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "error validating base trust data checksums")
}

func TestHasDelegations(t *testing.T) {
	repo := testGetRepo(t, PRE+"trust_data/never-expire-image")
	assert.False(t, repo.HasDelegations())

	repo = testGetRepo(t, PRE+"trust_data/never-expire-with-delegations-image")
	assert.True(t, repo.HasDelegations())
}

func TestDownloadAndValidateDelegations(t *testing.T) {
	srv := testhelper.NotaryMock(BASE, true)
	ctx := context.Background()
	defer srv.Close()

	var testCases = []struct {
		img         string
		delegations []string
		err         string
	}{
		{
			"never-expire-with-delegations-image",
			[]string{"targets/del1", "targets/del2"},
			"",
		},
		{
			"never-expire-with-delegations-image",
			[]string{"targets/delll"},
			"delegation targets/delll not found",
		},
	}

	for _, tc := range testCases {
		img, _ := image.New(tc.img)
		nc, _ := NewNotaryClient(srv.URL, "", auth.Auth{}, img)
		repo := testGetRepo(t, PRE+"trust_data/"+tc.img)

		err := repo.DownloadAndValidateDelegations(ctx, nc, tc.delegations)

		if tc.err != "" {
			assert.NotNil(t, err)
			assert.ErrorContains(t, err, tc.err)
		} else {
			assert.Nil(t, err)
		}
	}
}

func TestValidateDelegation(t *testing.T) {
	img := "never-expire-with-delegations-image"
	delegations := []string{"targets/del1", "targets/del2", "targets/releases"}

	repo := testGetRepoWithDelegations(t, PRE+"trust_data/"+img, delegations)
	err := repo.validateDelegations(delegations)
	assert.Nil(t, err)

	tmpDelegation := repo.Targets["targets/del1"]
	tmpDelegationBytes := repo.notCheckedChecksums["targets/del1"]

	isd, isdBytes := testhelper.DelegationData(
		PRE+"trust_data/04_invalid_signature_delegation.json",
		"targets/del1",
	)
	repo.Targets["targets/del1"] = isd
	repo.notCheckedChecksums["targets/del1"] = isdBytes
	err = repo.validateDelegations(delegations)
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "error validating delegation targets/del1 signatures")

	exd, exdBytes := testhelper.DelegationData(
		PRE+"trust_data/05_expired_delegation.json",
		"targets/del1",
	)
	repo.Targets["targets/del1"] = exd
	repo.notCheckedChecksums["targets/del1"] = exdBytes
	err = repo.validateDelegations(delegations)
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "targets/del1 trust data expired")

	repo.Targets["targets/del1"] = tmpDelegation
	repo.notCheckedChecksums["targets/del1"] = tmpDelegationBytes
	repo.Snapshot.Signed.Meta["targets/del1"].Hashes["sha256"], _ = base64.StdEncoding.DecodeString(
		"BRvrK68g71NZV1jUZi8wJoqadC6NQA0s2rvDX5gVOVc=",
	)
	err = repo.validateDelegations(delegations)
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "error validating targets/del1 checksums")

	delete(repo.Targets, "targets/del1")
	err = repo.validateDelegations(delegations)
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "delegation targets/del1 not found")

	repo.Targets["targets/del3"] = tmpDelegation
	delegations = []string{"targets/del2", "targets/del3"}
	err = repo.validateDelegations(delegations)
	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "error building delegation role targets/del3")
}

func TestHasDelegationHashes(t *testing.T) {
	repo := testGetRepo(t, PRE+"trust_data/edge-case-image")
	assert.False(t, repo.HasDelegationHashes([]string{"targets/del1"}))

	repo = testGetRepo(t, PRE+"trust_data/edge-case-err-image")
	assert.True(t, repo.HasDelegationHashes([]string{"targets/del1", "targets/del2", "targets/releases"}))
}
