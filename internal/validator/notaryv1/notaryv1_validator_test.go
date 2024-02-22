package notaryv1

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/image"
	"connaisseur/internal/policy"
	"connaisseur/test/testhelper"
	"context"
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
	"gopkg.in/yaml.v3"
)

const PRE = "../../../test/testdata/notaryv1/"
const BASE = "../../../test/testdata/notaryv1/trust_data"

type TestAuth map[string]struct {
	u string
	p string
}

func TestMain(m *testing.M) {
	constants.SecretsDir = "../../../test/testdata/auth/"
	os.Exit(m.Run())
}

// Auth files for testing MUST have a `secretName` or `useKeychain` field, since they
// get transformed during helm installation
func TestUnmarshal(t *testing.T) {
	var testCases = []struct {
		file       string
		name       string
		host       string
		cert       string
		trustRoots []string
		auth       TestAuth
		err        string
	}{
		{ // 1
			"01_notaryv1",
			"default",
			"https://notary.docker.io",
			"",
			[]string{"default", "sse"},
			TestAuth{},
			"",
		},
		{ // 2
			"02_no_trust_root",
			"",
			"",
			"",
			[]string{},
			TestAuth{},
			"no trust roots provided for validator no_trust_root",
		},
		{ // 3
			"03_invalid_host",
			"",
			"",
			"",
			[]string{},
			TestAuth{},
			"invalid url for notary host",
		},
		{ // 4
			"04_default_host",
			"default",
			"https://notary.docker.io",
			"",
			[]string{"default", "sse"},
			TestAuth{},
			"",
		},
		{ // 5
			"05_unmarshal_err",
			"",
			"",
			"",
			[]string{},
			TestAuth{},
			"yaml: unmarshal errors",
		},
		{ // 6
			"12_auth",
			"default",
			"https://ghcr.io",
			"",
			[]string{},
			TestAuth{"notary.docker.io": struct {
				u string
				p string
			}{"user", "pass"}},
			"",
		},
		{ // 7
			"13_invalid_cert",
			"",
			"",
			"",
			[]string{},
			TestAuth{},
			"invalid certificate",
		},
		{ // 8
			"14_auth_no_registry",
			"default",
			"https://ghcr.io",
			"",
			[]string{},
			TestAuth{"ghcr.io": struct {
				u string
				p string
			}{"user", "pass"}},
			"",
		},
	}

	for idx, tc := range testCases {
		var nv1v NotaryV1Validator

		nv1Bytes, _ := os.ReadFile(PRE + tc.file + ".yaml")
		err := yaml.Unmarshal(nv1Bytes, &nv1v)

		if tc.err != "" {
			assert.NotNil(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.Nil(t, err, idx+1)
			assert.Equal(t, tc.name, nv1v.Name, idx+1)
			assert.Equal(t, tc.host, nv1v.Host, idx+1)
			assert.Equal(t, tc.cert, nv1v.Cert, idx+1)
			for i, trustRoot := range tc.trustRoots {
				assert.Equal(t, trustRoot, nv1v.TrustRoots[i].Name, idx+1)
			}
			for k, v := range tc.auth {
				assert.Equal(t, v.u, nv1v.Auth.AuthConfigs[k].Username, idx+1)
				assert.Equal(t, v.p, nv1v.Auth.AuthConfigs[k].Password, idx+1)
			}
		}
	}
}

func TestValidateImage(t *testing.T) {
	srv := testhelper.NotaryMock(BASE, true)
	defer srv.Close()

	ctx := context.Background()

	var testCases = []struct {
		validatorPath string
		image         string
		key           string
		delegations   []string
		digest        string
		err           string
	}{
		{ // 1: working case 1
			"08_never_expire_notary",
			"never-expire-image:sign",
			"default",
			[]string{},
			"sha256:a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
			"",
		},
		{ // 2: working case 2
			"08_never_expire_notary",
			"never-expire-image:v1",
			"default",
			[]string{},
			"sha256:799c0fa8aa4c9fbff5a99aef1b4b5c3abb9c2f34134345005982fad3489893c7",
			"",
		},
		{ // 3: edge case, where targets data is used, instead of delegations
			"08_never_expire_notary",
			"edge-case-image:sign",
			"default",
			[]string{},
			"sha256:a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
			"",
		},
		{ // 4: edge case, but delegations need to be used, since they are defined in the snapshot
			"08_never_expire_notary",
			"edge-case-err-image:sign",
			"default",
			[]string{},
			"",
			"error during download and validation of delegations for targets",
		},
		{ // 5: unknown key type
			"10_unknown_keys",
			"never-expire-image:sign",
			"ed25519",
			[]string{},
			"",
			"signature was invalid", // the fact that the key type is unknown is swallowed by TUF library
		},
		{ // 6: key not found
			"08_never_expire_notary",
			"never-expire-image:sign",
			"not-a-key",
			[]string{},
			"",
			"error getting trust root key",
		},
		{ // 7: download error
			"08_never_expire_notary",
			"non-existant:image",
			"default",
			[]string{},
			"",
			"error downloading trust data",
		},
		{ // 8: missing delegations
			"08_never_expire_notary",
			"never-expire-image:sign",
			"default",
			[]string{"missing"},
			"",
			"no delegations found for validator",
		},
		{ // 9: delegation by tag
			"08_never_expire_notary",
			"never-expire-with-delegations-image:sign",
			"default",
			[]string{"targets/del1"},
			"sha256:a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
			"",
		},
		{ // 10: delegation by digest
			"08_never_expire_notary",
			"never-expire-with-delegations-image@sha256:a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
			"default",
			[]string{"targets/del1"},
			"sha256:a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
			"",
		},
		{ // 11: missing delegation signatures
			"08_never_expire_notary",
			"never-expire-with-delegations-image:sign",
			"default",
			[]string{"targets/del1", "targets/del2"},
			"",
			"validated targets don't contain reference",
		},
		{ // 12: required delegation, but repo has no delegation
			"08_never_expire_notary",
			"never-expire-image:sign",
			"default",
			[]string{"targets/del1"},
			"",
			"no delegations found for validator",
		},
		{ // 13: conflicting delegations
			"08_never_expire_notary",
			"never-expire-with-conflicting-delegations-image:sign",
			"default",
			[]string{"targets/del1", "targets/del2"},
			"",
			"found 2 digests for image",
		},
		{ // 14: delegation by tag and matching digest
			"08_never_expire_notary",
			"never-expire-with-delegations-image:sign@sha256:a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
			"default",
			[]string{"targets/del1"},
			"sha256:a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
			"",
		},
		{ // 15: delegation by tag and non-matching digest
			"08_never_expire_notary",
			"never-expire-with-delegations-image:v1@sha256:a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
			"default",
			[]string{"targets/del2"},
			"",
			"doesn't match given digest",
		},
	}

	for idx, tc := range testCases {
		var nv1v NotaryV1Validator
		nv1Bytes, _ := os.ReadFile(PRE + tc.validatorPath + ".yaml")
		err := yaml.Unmarshal(nv1Bytes, &nv1v)
		assert.Nil(t, err, idx+1)
		nv1v.Host = srv.URL

		args := policy.RuleOptions{
			TrustRoot:   tc.key,
			Delegations: tc.delegations,
		}
		img, _ := image.New(tc.image)

		digest, err := nv1v.ValidateImage(ctx, img, args)

		if tc.err != "" {
			assert.NotNil(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.Nil(t, err, idx+1)
			assert.Equal(t, tc.digest, digest, idx+1)
		}
	}
}

func TestValidateImageInvalidClient(t *testing.T) {
	var nv1v NotaryV1Validator
	nv1Bytes, _ := os.ReadFile(PRE + "08_never_expire_notary.yaml")
	err := yaml.Unmarshal(nv1Bytes, &nv1v)
	assert.Nil(t, err)
	nv1v.Host = "def:// invalid url"

	args := policy.RuleOptions{}
	img, _ := image.New("some:image")

	_, err = nv1v.ValidateImage(context.Background(), img, args)

	assert.NotNil(t, err)
	assert.ErrorContains(t, err, "error creating notary client")
}

func TestTrustRootKeys(t *testing.T) {
	var testCases = []struct {
		file   string
		keyRef string
		keys   []struct {
			alg string
			id  string
		}
		err string
	}{
		{ // 1: ECDSA parsing
			"01_notaryv1",
			"sse",
			[]struct {
				alg string
				id  string
			}{{"ecdsa", "5fd0a12a2fba07ea9fa39564d991be97a43256d1962ee84739efeebab3353a61"}},
			"",
		},
		{ // 2: RSA parsing
			"06_rsa_key",
			"rsa",
			[]struct {
				alg string
				id  string
			}{{"rsa", "932fc6749a68497dea96dd772487b524195f78d7d3cff990d12da7c87c1589df"}},
			"",
		},
		{ // 3: no key found
			"01_notaryv1",
			"no_key",
			[]struct {
				alg string
				id  string
			}{},
			"error getting keys for validator",
		},
		{ // 4: invalid key
			"07_invalid_pub_key",
			"invalid_pub_key",
			[]struct {
				alg string
				id  string
			}{},
			"error parsing public key",
		},
		{ // 5: PEM parsing allows extraneous whitespace
			"09_extra_chars",
			"moreWhitespace",
			[]struct {
				alg string
				id  string
			}{{"ecdsa", "5fd0a12a2fba07ea9fa39564d991be97a43256d1962ee84739efeebab3353a61"}},
			"",
		},
		{ // 6: PEM parsing doesn't allow extraneous non-whitespace
			"09_extra_chars",
			"moreLines",
			[]struct {
				alg string
				id  string
			}{},
			"contains extraneous characters",
		},
		{ // 7: unknown key type (implemented by below parsing lib)
			"10_unknown_keys",
			"ed25519",
			[]struct {
				alg string
				id  string
			}{{"unknown", "6d08660bb5540266b8e1b598f2bc33a8328f06297fcd0883e964ca51bb687838"}},
			"",
		},
		{ // 8: unknown key type (not implemented by below parsing lib)
			"10_unknown_keys",
			"dilithium",
			[]struct {
				alg string
				id  string
			}{},
			"error parsing public key",
		},
		{ // 9: all quantifier
			"01_notaryv1",
			"*",
			[]struct {
				alg string
				id  string
			}{
				{"ecdsa", "c15164663f80d58bf3d8d5a0cd08b8086cba02065feb00421fc2a5436c563210"},
				{"ecdsa", "5fd0a12a2fba07ea9fa39564d991be97a43256d1962ee84739efeebab3353a61"},
			},
			"",
		},
		// { // 10: parsing multiple keys with the same name TODO: choose one (takes the first/doesn't work)
		// 	"11_multiple_entries",
		// 	"sse",
		// 	struct {
		// 		alg string
		// 		id  string
		// 	}{},
		// 	"maybe some error if we decide so",
		// },
	}

	for idx, tc := range testCases {
		var nv1v NotaryV1Validator
		nv1Bytes, _ := os.ReadFile(PRE + tc.file + ".yaml")
		err := yaml.Unmarshal(nv1Bytes, &nv1v)
		assert.Nil(t, err, idx+1)

		keys, err := nv1v.trustRootKeys(tc.keyRef)

		if tc.err != "" {
			assert.NotNil(t, err, idx+1)
			assert.ErrorContains(t, err, tc.err, idx+1)
		} else {
			assert.Nil(t, err, idx+1)
			assert.Equal(t, len(tc.keys), len(keys))
			for i, key := range tc.keys {
				assert.Equal(t, key.alg, keys[i].Algorithm(), idx+1)
				assert.Equal(t, key.id, keys[i].ID(), idx+1)
			}
		}
	}
}

func TestToDelegationString(t *testing.T) {
	var testCases = []struct {
		delegation string
		expected   string
	}{
		{
			"root",
			"targets/root",
		},
		{
			"targets",
			"targets/targets",
		},
		{
			"targets/releases",
			"targets/releases",
		},
	}

	for _, tc := range testCases {
		assert.Equal(t, tc.expected, toDelegationString(tc.delegation))
	}
}

func TestSearchTargetsForTag(t *testing.T) {
	var testCases = []struct {
		file   string
		tag    string
		digest string
		err    string
	}{
		{
			"sample-image/targets",
			"v1",
			"sha256:799c0fa8aa4c9fbff5a99aef1b4b5c3abb9c2f34134345005982fad3489893c7",
			"",
		},
		{
			"sample-image/targets",
			"sign",
			"sha256:a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
			"",
		},
		{
			"sample-image/targets",
			"no_tag",
			"",
			"no tag 'no_tag' found in targets",
		},
	}

	for _, tc := range testCases {
		target, _ := testhelper.TargetData(PRE + "trust_data/" + tc.file + ".json")
		digest, err := searchTargetsForTag(target.Signed, tc.tag)

		if tc.err != "" {
			assert.NotNil(t, err)
			assert.ErrorContains(t, err, tc.err)
		} else {
			assert.Nil(t, err)
			assert.Equal(t, tc.digest, digest)
		}
	}
}

func TestSearchTargetsForDigest(t *testing.T) {
	var testCases = []struct {
		file   string
		digest string
		err    string
	}{
		{
			"sample-image/targets",
			"sha256:799c0fa8aa4c9fbff5a99aef1b4b5c3abb9c2f34134345005982fad3489893c7",
			"",
		},
		{
			"sample-image/targets",
			"sha256:a154797b8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
			"",
		},
		{
			"sample-image/targets",
			"sha256:aaaaaaab8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf",
			"no digest 'sha256:aaaaaaab8300165956ee1f16d98f3a1426301c1168f0462c73ce9bc03361cabf' found in targets",
		},
	}

	for _, tc := range testCases {
		target, _ := testhelper.TargetData(PRE + "trust_data/" + tc.file + ".json")
		digest, err := searchTargetsForDigest(target.Signed, tc.digest)

		if tc.err != "" {
			assert.NotNil(t, err)
			assert.ErrorContains(t, err, tc.err)
		} else {
			assert.Nil(t, err)
			assert.Equal(t, tc.digest, digest)
		}
	}
}
