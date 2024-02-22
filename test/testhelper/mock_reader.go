package testhelper

import "io"

type MockReader struct {
	io.Reader
	Msg string
	Err error
}

func (m *MockReader) Read(p []byte) (n int, err error) {
	if m.Err != nil {
		return 0, m.Err
	}

	if p == nil {
		return 0, nil
	}

	p = []byte(m.Msg)
	return len(m.Msg), nil
}
