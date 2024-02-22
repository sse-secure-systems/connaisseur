package image

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/utils"
	"fmt"
	"strings"

	"github.com/google/go-containerregistry/pkg/name"
)

// wrapper struct around `name.Reference` that return the full reference
// when calling `String()`, including the tag AND digest if present.
type Image struct {
	original string
	ref      name.Reference
	tag      string
	digest   string
	name.Reference
}

func New(image string) (*Image, error) {
	ref, err := name.ParseReference(image)
	if err != nil {
		return nil, err
	}

	i := Image{original: image, ref: ref}
	id := i.Identifier()

	if strings.HasPrefix(
		id,
		"sha256:",
	) {
		i.digest = id

		// for an image like "reg.io/repo/image:tag@sha256:digest", the identifier is
		// "sha256:digest". the tag gets lost and none of the functions of `name.Reference`
		// can retrieve it. we need to extract it manually by cutting from the front and
		// back of the original image string.
		fullyQualifiedImagePath := utils.StringOverlap(i.ref.Context().Name(), i.original)
		tagAndDigest := strings.TrimPrefix(strings.TrimPrefix(i.original, fullyQualifiedImagePath), ":")
		i.tag = strings.TrimSuffix(tagAndDigest, "@"+id)
	} else {
		i.tag = strings.TrimPrefix(id, ":")
	}

	return &i, nil
}

func (i *Image) Context() name.Repository {
	return i.ref.Context()
}

func (i *Image) Identifier() string {
	return i.ref.Identifier()
}

// According to documentation of ref lib, Name is the fully-qualified reference name
func (i *Image) Name() string {
	var tag, digest string

	if i.tag != "" {
		tag = ":" + i.tag
	}

	if i.digest != "" {
		digest = "@" + i.digest
	}

	return fmt.Sprintf("%s%s%s", i.ref.Context(), tag, digest)
}

func (i *Image) Scope(s string) string {
	return i.ref.Scope(s)
}

func (i *Image) OriginalString() string {
	return i.original
}

// "Native" format of the image which we define as the output of Name()
func (i *Image) String() string {
	return i.Name()
}

// notary stores images at `docker.io/...` thus the `index.` prefix
// needs to be removed.
func (i *Image) NotaryReference() string {
	if strings.HasPrefix(i.Context().String(), constants.DefaultDockerRegistry) {
		return strings.TrimPrefix(i.Context().String(), "index.")
	}
	return i.Context().String()
}

func (i *Image) Tag() string {
	return i.tag
}

func (i *Image) Digest() string {
	return i.digest
}

func (i *Image) SetDigest(digest string) *Image {
	if digest != "" && !strings.HasPrefix(digest, "sha256:") {
		digest = "sha256:" + digest
	}
	i.digest = digest
	return i
}
