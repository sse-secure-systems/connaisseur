package caching

import "testing"

func TestIsCacher(t *testing.T) {
	var _ Cacher = EmptyCache{}
}
