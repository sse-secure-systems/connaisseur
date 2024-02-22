package image

import (
	"connaisseur/internal/constants"
	"connaisseur/internal/utils"
	"fmt"
	"strings"

	"github.com/google/go-containerregistry/pkg/name"
)

type RegistryRepo struct {
	original string
	registry string
	repo     string
}

func NewRegistryRepo(s string) (*RegistryRepo, error) {
	if s == constants.EmptyAuthRegistry {
		return &RegistryRepo{
			original: s,
			registry: s,
		}, nil
	}

	orig := s
	s = utils.TrimPrefixes(s, "https://", "http://")
	if utils.HasPrefixes(s, "index.docker.io", "docker.io") && strings.HasSuffix(s, "/v1/") {
		s = strings.TrimSuffix(s, "/v1/")
	}

	var registry, repo string
	idx := strings.Index(s, "/")
	if idx == -1 {
		registry = s
	} else {
		registry = s[:idx]
		repo = s[idx+1:]
	}

	_, err := name.NewRegistry(registry)
	if err != nil {
		return nil, fmt.Errorf("unable to parse registry %s: %s", registry, err)
	}

	if repo != "" {
		_, err = name.NewRepository(repo)
		if err != nil {
			return nil, fmt.Errorf("unable to parse repository %s: %s", repo, err)
		}
	}

	return &RegistryRepo{
		original: orig,
		registry: registry,
		repo:     repo,
	}, nil
}

func (r *RegistryRepo) String() string {
	if r.repo == "" {
		return r.registry
	}
	return fmt.Sprintf("%s/%s", r.registry, r.repo)
}
