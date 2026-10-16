package main

import (
	"connaisseur/internal/constants"
	"testing"
)

func TestServerPort(t *testing.T) {
	tests := []struct {
		name     string
		value    string
		expected int
	}{
		{name: "default", expected: constants.DefaultServerPort},
		{name: "configured", value: "443", expected: 443},
		{name: "not a number", value: "https", expected: constants.DefaultServerPort},
		{name: "zero", value: "0", expected: constants.DefaultServerPort},
		{name: "too large", value: "65536", expected: constants.DefaultServerPort},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			t.Setenv(constants.ServerPort, test.value)

			actual := serverPort()
			if actual != test.expected {
				t.Errorf("serverPort() = %d, expected %d", actual, test.expected)
			}
		})
	}
}
