package utils

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

type TestStruct struct {
	TestField string   `validate:"required"`
	TestArray []string `validate:"min=1"`
}

type TestStruct2 struct {
	TestField string `validate:"eq=test"`
}

func TestValidate(t *testing.T) {
	var testCases = []struct {
		input interface{}
		err   string
	}{
		{ // 1: valid TestStruct
			TestStruct{
				TestField: "test",
				TestArray: []string{"test"},
			},
			"",
		},
		{ // 2: invalid TestStruct2
			TestStruct2{
				TestField: "test",
			},
			"",
		},
		{ // 3: invalid TestStruct
			TestStruct{
				TestArray: []string{"test"},
			},
			"TestStruct has 1 errors:\nTestStruct error 0: TestField is a required field\n",
		},
		{ // 4: invalid TestStruct2
			TestStruct2{
				TestField: "invalid",
			},
			"TestStruct2 has 1 errors:\nTestStruct2 error 0: TestField is not equal to test\n",
		},
	}

	for idx, tc := range testCases {
		err := Validate(tc.input)

		if tc.err == "" {
			assert.NoError(t, err, idx+1)
		} else {
			assert.ErrorContains(t, err, tc.err, idx+1)
		}
	}
}
