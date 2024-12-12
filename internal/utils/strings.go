package utils

import (
	"bytes"
	"encoding/json"
	"reflect"
	"slices"
	"strings"
)

// Finds the longest common prefix of a slice of strings.
func LongestCommonPrefix(strs []string) string {
	var longestPrefix string = "" //nolint:staticcheck

	if len(strs) > 0 {
		slices.Sort(strs)
		first := string(strs[0])
		last := string(strs[len(strs)-1])

		for i := 0; i < len(first); i++ {
			if string(last[i]) == string(first[i]) {
				longestPrefix += string(last[i])
			} else {
				break
			}
		}
	}
	return longestPrefix
}

// StringOverlap finds the longest overlapping substring between two input strings.
// The function takes two strings as input and returns the longest substring that appears at the end
// of the first string and the start of the second string.
// If there is no overlap, the function returns an empty string.
func StringOverlap(a, b string) string {
	for i := Max(0, len(a)-len(b)); i < len(a); i++ {
		if strings.HasPrefix(b, a[i:]) {
			return a[i:]
		}
	}

	return ""
}

// HasPrefixes checks if a string has any of the given prefixes (logical OR).
func HasPrefixes(s string, prefixes ...string) bool {
	for _, prefix := range prefixes {
		if strings.HasPrefix(s, prefix) {
			return true
		}
	}
	return false
}

// HasPrefixes checks if a string has any of the given prefixes (logical OR).
func TrimPrefixes(s string, prefixes ...string) string {
	for _, prefix := range prefixes {
		s = strings.TrimPrefix(s, prefix)
	}
	return s
}

// JsonEscapeString takes a string as input and returns a JSON-encoded version of the string.
// It uses the json.NewEncoder function to create a new JSON encoder and writes to a bytes.Buffer.
// The SetEscapeHTML method is used to disable HTML escaping in the output.
// The Encode method is used to encode the input string into JSON format.
// The function then converts the bytes.Buffer to a string and trims the leading and trailing
// quotes.
// It returns the JSON-encoded string.
func JsonEscapeString(i string) string {
	// var output string
	b := &bytes.Buffer{}

	encoder := json.NewEncoder(b)
	encoder.SetEscapeHTML(false)
	// ignoring error because error cannot be reached
	_ = encoder.Encode(i) //nolint: errcheck

	o := b.String()
	return o[1 : len(o)-2]
}

func JsonEscapeStruct(v any) {
	value := reflect.ValueOf(v).Elem()
	fields := reflect.VisibleFields(value.Type())

	for _, field := range fields {
		fieldValue := value.FieldByIndex(field.Index)
		if fieldValue.Kind() == reflect.String {
			fieldValue.SetString(JsonEscapeString(fieldValue.String()))
		}
	}
}

// StringDefault returns the default value if the input string is empty.
func StringDefault(s, default_ string) string {
	if s == "" {
		return default_
	}
	return s
}
