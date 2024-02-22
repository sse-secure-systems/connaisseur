package utils

// SetSubtract returns set(a)-set(b), i.e. subtracts all elements of b from the set of unique values in a
func SetSubstract[T comparable](a []T, b []T) []T {
	aSet := uniq(a)
	bSet := uniq(b)
	hash := make(map[T]struct{})

	for _, v := range bSet {
		hash[v] = struct{}{}
	}

	var set []T
	for _, v := range aSet {
		if _, ok := hash[v]; !ok {
			set = append(set, v)
		}
	}

	return set
}

// uniq returns only unique elements of a slice
func uniq[T comparable](a []T) []T {
	hash := make(map[T]struct{})
	set := make([]T, 0)

	for _, v := range a {
		hash[v] = struct{}{}
	}

	for k := range hash {
		set = append(set, k)
	}

	return set
}

// Map returns a new slice with the results of applying the function f to each
// element of the original slice
func Map[T, K any](list []T, f func(T) K) []K {
	var out []K

	for _, v := range list {
		out = append(out, f(v))
	}
	return out
}
