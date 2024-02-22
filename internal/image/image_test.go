package image

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestNew(t *testing.T) {
	var testCases = []struct {
		img        string
		context    string
		identifier string
		name       string
		err        bool
	}{
		{ // 1
			"test-image",
			"index.docker.io/library/test-image",
			"latest",
			"index.docker.io/library/test-image:latest",
			false,
		},
		{ // 2
			"test-image:latest",
			"index.docker.io/library/test-image",
			"latest",
			"index.docker.io/library/test-image:latest",
			false,
		},
		{ // 3
			"test-image:1.0.0",
			"index.docker.io/library/test-image",
			"1.0.0",
			"index.docker.io/library/test-image:1.0.0",
			false,
		},
		{ // 4
			"registry.io/path/to/repo/image:tag",
			"registry.io/path/to/repo/image",
			"tag",
			"registry.io/path/to/repo/image:tag",
			false,
		},
		{ // 5
			"test-image@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"index.docker.io/library/test-image",
			"sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"index.docker.io/library/test-image@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			false,
		},
		{ // 6
			"test-image:latest@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"index.docker.io/library/test-image",
			"sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"index.docker.io/library/test-image:latest@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			false,
		},
		{ // 7
			"path/to/repo/image:tag",
			"index.docker.io/path/to/repo/image",
			"tag",
			"index.docker.io/path/to/repo/image:tag",
			false,
		},
		{ // 8
			"registry.io:8080/path/to/repo/image:tag",
			"registry.io:8080/path/to/repo/image",
			"tag",
			"registry.io:8080/path/to/repo/image:tag",
			false,
		},
		{ // 9
			"invalid,image",
			"",
			"",
			"",
			true,
		},
		{ // 10
			"asd\"fgh",
			"",
			"",
			"",
			true,
		},
		{ // 11
			"test-image:tag@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"index.docker.io/library/test-image",
			"sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"index.docker.io/library/test-image:tag@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			false,
		},
		{ // 12
			"my.reg/allow-me@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"my.reg/allow-me",
			"sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"my.reg/allow-me@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			false,
		},
		{ // 13
			"securesystemsengineering/alice-image@sha256:123",
			"",
			"",
			"",
			true,
		},
		{ // 14
			"localhost:5000/test-image:latest",
			"localhost:5000/test-image",
			"latest",
			"localhost:5000/test-image:latest",
			false,
		},
		{ // 15
			"localhost/test-image:latest",
			"index.docker.io/localhost/test-image",
			"latest",
			"index.docker.io/localhost/test-image:latest",
			false,
		},
	}
	for _, tc := range testCases {
		i, err := New(tc.img)

		if tc.err {
			assert.Error(t, err)
		} else {
			assert.Nil(t, err)
			assert.Equal(t, tc.context, i.Context().String())
			assert.Equal(t, tc.identifier, i.Identifier())
			assert.Equal(t, tc.name, i.Name())
			assert.Equal(t, tc.img, i.OriginalString())
		}
	}
}

func TestDigest(t *testing.T) {
	var testCases = []struct {
		img    string
		digest string
	}{
		{
			"test-image",
			"",
		},
		{
			"test-image:tag",
			"",
		},
		{
			"test-image:latest@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
		},
	}
	for _, tc := range testCases {
		img, _ := New(tc.img)
		assert.Equal(t, tc.digest, img.Digest())
	}
}

func TestScope(t *testing.T) {
	testCases := []struct {
		img      string
		scopeTag string
		scope    string
	}{
		{
			"test-image",
			"latest",
			"repository:library/test-image:latest",
		},
		{
			"test-image",
			"",
			"repository:library/test-image:",
		},
		{
			"test-image:latest@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"latest",
			"repository:library/test-image:latest",
		},
	}
	for _, tc := range testCases {
		img, _ := New(tc.img)
		assert.Equal(t, tc.scope, img.Scope(tc.scopeTag))
	}
}

func TestTag(t *testing.T) {
	testCases := []struct {
		img string
		tag string
	}{
		{
			"test-image",
			"latest",
		},
		{
			"test-image@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"",
		},
		{
			"test-image:latest@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"latest",
		},
		{
			"test-image:1.0.0",
			"1.0.0",
		},
	}
	for _, tc := range testCases {
		img, _ := New(tc.img)
		assert.Equal(t, tc.tag, img.Tag())
	}
}

func TestSetDigest(t *testing.T) {
	testCases := []struct {
		img        string
		newDigest  string
		newImgName string
	}{
		{
			"index.docker.io/library/test-image:latest",
			"sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"index.docker.io/library/test-image:latest@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
		},
		{
			"index.docker.io/library/test-image:latest@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"",
			"index.docker.io/library/test-image:latest",
		},
		{
			"index.docker.io/library/test-image:latest",
			"91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"index.docker.io/library/test-image:latest@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
		},
	}
	for _, tc := range testCases {
		img, _ := New(tc.img)
		assert.Equal(t, tc.img, img.Name())
		img.SetDigest(tc.newDigest)
		assert.Equal(t, tc.newImgName, img.Name())
	}
}

func TestNotaryReference(t *testing.T) {
	testCases := []struct {
		img             string
		notaryReference string
	}{
		{
			"test-image",
			"docker.io/library/test-image",
		},
		{
			"test-image:latest@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"docker.io/library/test-image",
		},
		{
			"test-image@sha256:91ac9b26df583762234c1cdb2fc930364754ccc59bc752a2bfe298d2ea68f9ff",
			"docker.io/library/test-image",
		},
		{
			"test-image:latest",
			"docker.io/library/test-image",
		},
		{
			"registry.io:8080/path/to/repo/image:tag",
			"registry.io:8080/path/to/repo/image",
		},
	}
	for _, tc := range testCases {
		img, _ := New(tc.img)
		assert.Equal(t, tc.notaryReference, img.NotaryReference())
	}
}
