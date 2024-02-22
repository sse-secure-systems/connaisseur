package main

import (
	"crypto/rand"
	"crypto/sha256"
	"crypto/sha512"
	"crypto/x509"
	"encoding/asn1"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"hash"
	"math/big"
	"os"
	"strings"

	jsonCanon "github.com/docker/go/canonical/json"
	"github.com/spf13/cobra"
	"github.com/theupdateframework/notary/tuf/data"
)

type ecdsaSig struct {
	R *big.Int
	S *big.Int
}

var (
	fileArg string
	keyArg  string

	rootCmd = &cobra.Command{
		Use:   "nv1_testdata_creator",
		Short: "A tool to create test data for notaryv1 validators.",
		Long: `A tool to create test data for notaryv1 validators.
This tool is not intended to be used in production, but rather to create
test data for notaryv1 validators.`,
	}

	signCmd = &cobra.Command{
		Use:   "sign --file <file> --key <privkey>",
		Short: "Sign a trust data json with a private key",
		Long: `Sign a trust data json with a private key.
The key must be in PEM format.`,
		Run: func(cmd *cobra.Command, args []string) {
			signFunc()
		},
	}

	hashCmd = &cobra.Command{
		Use:   "hash --file <file>",
		Short: "Hash a trust data json",
		Long: `Hash a trust data json.
This creates the sha256 and sha512 hashes to be used in the timestamp
and snapshot data.`,
		Run: func(cmd *cobra.Command, args []string) {
			hashFunc()
		},
	}

	keyIDCmd = &cobra.Command{
		Use:   "keyid --key <pubkey>",
		Short: "Get the keyid of a public key",
		Run: func(cmd *cobra.Command, args []string) {
			keyIDFunc()
		},
	}
)

func init() {
	signCmd.Flags().StringVar(&fileArg, "file", "", "file to sign")
	signCmd.MarkFlagRequired("file")
	signCmd.Flags().StringVar(&keyArg, "key", "", "key to sign with")
	signCmd.MarkFlagRequired("key")

	hashCmd.Flags().StringVar(&fileArg, "file", "", "file to hash")

	keyIDCmd.Flags().StringVar(&keyArg, "key", "", "key to get keyid of")

	rootCmd.AddCommand(signCmd)
	rootCmd.AddCommand(hashCmd)
	rootCmd.AddCommand(keyIDCmd)
}

func signFunc() {
	file := loadFile(fileArg, true)
	key := loadKey(keyArg)

	sig, err := sign(key, file)
	if err != nil {
		panic(err)
	}
	base64sig := base64.StdEncoding.EncodeToString(sig)

	fmt.Printf("signature: %s\n", base64sig)
}

func hashFunc() {
	file := loadFile(fileArg, false)

	for _, hash := range []struct {
		algo string
		h    hash.Hash
	}{
		{"sha256", sha256.New()},
		{"sha512", sha512.New()},
	} {
		hash.h.Write([]byte(file))
		fmt.Printf("%s: %s\n", hash.algo, base64.StdEncoding.EncodeToString(hash.h.Sum(nil)))
	}
}

func keyIDFunc() {
	var (
		key_bytes []byte
		key_algo  string
	)

	key := []byte(loadKey(keyArg))
	// the keyid for a cert (root) doesn't work for some reason :(
	if strings.HasSuffix(keyArg, ".crt") {
		b64 := base64.StdEncoding.EncodeToString(key)
		key_bytes = []byte(b64)
		key_algo = "ecdsa-x509"
	} else {
		key_decode, _ := pem.Decode(key)
		key_bytes = key_decode.Bytes
		key_algo = "ecdsa"
	}

	tufKey := data.TUFKey{
		Type: key_algo,
		Value: data.KeyPair{
			Public:  key_bytes,
			Private: nil,
		},
	}

	fmt.Printf("keyid: %s\n", tufKey.ID())
	fmt.Printf("key: %s\n", string(key_bytes))
}

func loadFile(file string, signedOnly bool) string {
	var d data.Signed

	file_bytes, err := os.ReadFile(file)
	if err != nil {
		panic(err)
	}

	err = json.Unmarshal(file_bytes, &d)
	if err != nil {
		panic(err)
	}

	var canon []byte
	if signedOnly {
		canon, err = jsonCanon.MarshalCanonical(d.Signed)
	} else {
		canon, err = json.Marshal(d)
	}
	if err != nil {
		panic(err)
	}

	return string(canon)
}

func loadKey(keyPath string) string {
	key_bytes, err := os.ReadFile(keyPath)
	if err != nil {
		panic(err)
	}

	return string(key_bytes)
}

func sign(key string, msg string) ([]byte, error) {
	msg_bytes := []byte(msg)
	hashed := sha256.Sum256(msg_bytes)

	key_decode, _ := pem.Decode([]byte(key))
	privv, err := x509.ParseECPrivateKey(key_decode.Bytes)
	priv := privv
	if err != nil {
		panic(err)
	}

	sigASN1, err := priv.Sign(rand.Reader, hashed[:], nil)
	if err != nil {
		return nil, err
	}

	sig := ecdsaSig{}
	_, err = asn1.Unmarshal(sigASN1, &sig)
	if err != nil {
		return nil, err
	}
	rBytes, sBytes := sig.R.Bytes(), sig.S.Bytes()
	octetLength := (priv.Params().BitSize + 7) >> 3

	// MUST include leading zeros in the output
	rBuf := make([]byte, octetLength-len(rBytes), octetLength)
	sBuf := make([]byte, octetLength-len(sBytes), octetLength)

	rBuf = append(rBuf, rBytes...)
	sBuf = append(sBuf, sBytes...)
	return append(rBuf, sBuf...), nil
}

func main() {
	rootCmd.Execute()
}
