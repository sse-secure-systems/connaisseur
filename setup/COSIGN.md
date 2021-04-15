# Using Connaisseur with Cosign signatures

[Sigstore](https://sigstore.dev/) is a [Linux Foundation](https://linuxfoundation.org/) project that aims to provide public software signing and transparency to improve open source supply chain security. As part of the Sigstore project, [Cosign](https://github.com/sigstore/cosign) allows seamless container signing, verification and storage. You can read more about it [here](https://blog.sigstore.dev/cosign-signed-container-images-c1016862618).

Connaisseur currently supports the elementary function of verifying Cosign-generated signatures against the locally created corresponding public keys. We plan to expose further features of Cosign and Sigstore in upcoming releases, so stay tuned!

> :warning: Sigstore and Cosign are currently in *pre-release* state and under heavy development and so is our support for them. We therefore consider this an *experimental feature* that might unstable over time. As such, it is not part of our semantic versioning guarantees and we take the liberty to adjust or remove it with any version at any time without incrementing MAJOR or MINOR.

## Demo
![](../img/connaisseur_cosign.gif)

## Signing Container Images with Cosign

> **NOTE**: You can also do a minimal test without installing Cosign locally. In that case, skip this step and use our provided public key and `testimage`s below.

Getting started with Cosign is very well described in the [docs](https://github.com/sigstore/cosign). Please check there for detailed instructions. The currently supported version can be found in our [Makefile](https://github.com/sse-secure-systems/connaisseur/blob/master/Makefile/#L5). In short: After installation, a keypair is generated via:

```bash
cosign generate-key-pair
```

You will be prompted to set a password, after which a private (`cosign.key`) and public (`cosign.pub`) key are created. You can then use Cosign to sign a container image using:

```bash
# Here, $IMAGE is REPOSITORY/IMAGE_NAME:TAG
cosign sign -key cosign.key $IMAGE
```

The created signature can be verfied via:

```bash
cosign verify -key cosign.pub $IMAGE
```



## Configuring Connaisseur for Cosign Signatures

Setting up Connaisseur for Cosign signatures only requires minor changes. In case of questions, please refer to the [default guide](README.md). In essence, you can just clone this repository:

```bash
git clone https://github.com/sse-secure-systems/connaisseur.git
cd connaisseur
```

Next, configure Connaisseur to use Cosign and the previously created public key for validation via the `helm/values.yaml`.  To do so, copy your `cosign.pub` key into `notary.rootPubkey`. Here, at the example of our public key for our `testimage`s (you can also use this key and test with our images):

```yaml
# Replace the actual key part with your own key
  rootPubKey: |
    -----BEGIN PUBLIC KEY-----
    MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEvtc/qpHtx7iUUj+rRHR99a8mnGni
    qiGkmUb9YpWWTS4YwlvwdmMDiGzcsHiDOYz6f88u2hCRF5GUCvyiZAKrsA==
    -----END PUBLIC KEY-----
```

Next, set `notary.isCosign` to `true`:

```yaml
  isCosign: true
```

And finally, install Connaisseur via:

```bash
make install
```



## Test Signature Verification

You can now test signature verification by deploying the signed image from above:

```bash
kubectl run signed --image=$IMAGE
```

Or attempt to deploy any another unsigned image which will fail.

For the lazy ones, you can configure our public key provided in the previous section and test with our signed `testimage`:

```bash
kubectl run signed --image=docker.io/securesystemsengineering/testimage:co-signed
```

and compare to the unsigned `testimage`:

```bash
kubectl run unsigned --image=docker.io/securesystemsengineering/testimage:co-unsigned
```

or a `testimage` signed with a different key:

```bash
kubectl run unsigned --image=docker.io/securesystemsengineering/testimage:co-signed-alt
```

Once finished, you can clean up your cluster via:

```bash
make uninstall
```



## End

Hope you enjoy the new feature and let us [know what you think](https://github.com/sse-secure-systems/connaisseur/discussions/137)!

We are working on improving support for Cosign and Sigstore features. So stay tuned!
