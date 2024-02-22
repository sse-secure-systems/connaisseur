package notaryserver

import (
	"connaisseur/internal/utils"
	"context"
	"fmt"

	"github.com/docker/go/canonical/json"
	"github.com/sirupsen/logrus"
	"github.com/theupdateframework/notary/tuf/data"
	"github.com/theupdateframework/notary/tuf/signed"
)

type Repo struct {
	Root                *data.SignedRoot
	Targets             map[string]*data.SignedTargets
	Snapshot            *data.SignedSnapshot
	Timestamp           *data.SignedTimestamp
	notCheckedChecksums map[string][]byte
}

// Downloads all trust data from the notary server asychronously.
func (r *Repo) DownloadBaseTrustData(ctx context.Context, nc *NotaryClient) error {
	var errOut error
	trustDataChannel := make(chan TrustData, len(data.BaseRoles))
	r.Targets = make(map[string]*data.SignedTargets)
	r.notCheckedChecksums = make(map[string][]byte)

	for _, role := range data.BaseRoles {
		rs := role.String()
		go nc.FetchTrustData(
			ctx,
			rs,
			trustDataChannel,
		)
	}

	for range data.BaseRoles {
		select {
		case <-ctx.Done():
			return fmt.Errorf("context cancelled")
		default:
			trustData := <-trustDataChannel

			if trustData.Err != nil {
				return fmt.Errorf(
					"error acquiring trust data %s: %s",
					trustData.Role,
					trustData.Err,
				)
			}

			logrus.Debugf("got trust data for %s", trustData.Role)

			switch trustData.Role {
			case data.CanonicalRootRole.String():
				r.Root, errOut = data.RootFromSigned(trustData.Data)
			case data.CanonicalTargetsRole.String():
				r.Targets[data.CanonicalTargetsRole.String()], errOut = data.TargetsFromSigned(
					trustData.Data,
					data.CanonicalTargetsRole,
				)
			case data.CanonicalSnapshotRole.String():
				r.Snapshot, errOut = data.SnapshotFromSigned(trustData.Data)
			case data.CanonicalTimestampRole.String():
				r.Timestamp, errOut = data.TimestampFromSigned(trustData.Data)
			}

			if errOut != nil {
				logrus.Debugf("error parsing trust data for %s: %s", trustData.Role, errOut)
				return fmt.Errorf("error parsing trust data for %s: %s", trustData.Role, errOut)
			}
			r.notCheckedChecksums[trustData.Role] = trustData.Raw
		}
	}

	return nil
}

// Validates the root trust data against the given keys.
func (r *Repo) validateRoot(keys []data.PublicKey) error {
	// need to transform root to signed object to verify signature
	signedRoot, err := r.Root.ToSigned()
	if err != nil {
		return fmt.Errorf("serialization error for root: %s", err)
	}

	// remarshal the signed part so we can verify the signature, since the signature has
	// to be of a canonically marshalled signed object
	var decoded map[string]interface{}
	if err := json.Unmarshal(*signedRoot.Signed, &decoded); err != nil {
		return fmt.Errorf("error unmarshalling root: %s", err)
	}
	msg, err := json.MarshalCanonical(decoded)
	if err != nil {
		return fmt.Errorf("error marshalling root: %s", err)
	}

	// check if there are any signatures
	if len(r.Root.Signatures) < 1 {
		return fmt.Errorf("no signatures found for root")
	}

	// for each key, verify that at least one signature is valid
	for _, key := range keys {
		verified := false

		for _, sig := range r.Root.Signatures {
			sig := sig
			logrus.Debugf("verifying root signature with key %s", key.ID())

			if err = signed.VerifySignature(msg, &sig, key); err == nil && sig.IsValid {
				logrus.Debugf("root signature verified with key %s", key.ID())
				verified = true
				break
			}
		}

		if !verified {
			return fmt.Errorf("error validating root signature with key %s: %s", key.ID(), err)
		}
	}

	// verify expiry
	if signed.VerifyExpiry(&(r.Root.Signed.SignedCommon), data.CanonicalRootRole) != nil {
		return fmt.Errorf("root trust data expired")
	}

	return nil
}

// Validates the rest of the base trust data against the root trust data.
func (r *Repo) validateRestOfBase() error {

	for _, role := range data.BaseRoles {
		var (
			signedObj    *data.Signed
			signedCommon *data.SignedCommon
			err          error
		)

		switch role {
		case data.CanonicalRootRole:
			continue
		case data.CanonicalTargetsRole:
			signedObj, err = r.Targets[data.CanonicalTargetsRole.String()].ToSigned()
			signedCommon = &r.Targets[data.CanonicalTargetsRole.String()].Signed.SignedCommon
		case data.CanonicalSnapshotRole:
			signedObj, err = r.Snapshot.ToSigned()
			signedCommon = &r.Snapshot.Signed.SignedCommon
		case data.CanonicalTimestampRole:
			signedObj, err = r.Timestamp.ToSigned()
			signedCommon = &r.Timestamp.Signed.SignedCommon
		}

		if err != nil {
			return fmt.Errorf("serialization error for %s: %s", role, err)
		}

		verifyRole, err := r.Root.BuildBaseRole(role)
		if err != nil {
			return fmt.Errorf("error building base role %s: %s", role, err)
		}

		logrus.Debugf("verifying %s signatures", role)
		// validate signatures
		if signed.VerifySignatures(signedObj, verifyRole) != nil {
			return fmt.Errorf("error validating %s signatures", role)
		}

		logrus.Debugf("verifying %s expiry", role)
		//validate expiry
		if signed.VerifyExpiry(signedCommon, role) != nil {
			return fmt.Errorf("%s trust data expired", role)
		}

		logrus.Debugf("successful validation of %s", role)
	}

	return nil
}

// Validates the checksums of the base trust data against the checksums
// given in the snapshot and timestamp trust data.
func (r *Repo) validateBaseChecksums() error {
	for _, role := range data.BaseRoles {
		var (
			payload []byte
			ok      bool
			hashes  data.Hashes
		)

		switch role {
		case data.CanonicalRootRole, data.CanonicalTargetsRole:
			payload, ok = r.notCheckedChecksums[role.String()]
			hashes = r.Snapshot.Signed.Meta[role.String()].Hashes
		case data.CanonicalSnapshotRole:
			payload, ok = r.notCheckedChecksums[role.String()]
			hashes = r.Timestamp.Signed.Meta[role.String()].Hashes
		case data.CanonicalTimestampRole:
			continue
		}

		if !ok {
			return fmt.Errorf("no checksums found for %s", role)
		}

		// verify checksums
		if err := data.CheckHashes(payload, role.String(), hashes); err != nil {
			return fmt.Errorf("error validating %s checksums: %s", role.String(), err)
		}
	}

	return nil
}

// Validates the root trust data first, then validates the rest of the base trust data
// (targets, snapshot, timestamp), and finally validates the checksums for the base trust
// data.
func (r *Repo) ValidateBaseTrustData(keys []data.PublicKey) error {
	if err := r.validateRoot(keys); err != nil {
		return fmt.Errorf("error validating root: %s", err)
	}

	if err := r.validateRestOfBase(); err != nil {
		return fmt.Errorf("error validating base trust data: %s", err)
	}

	if err := r.validateBaseChecksums(); err != nil {
		return fmt.Errorf("error validating base trust data checksums: %s", err)
	}

	return nil
}

// Has the targets trust data any delegations.
func (r *Repo) HasDelegations() bool {
	return len(r.Targets[data.CanonicalTargetsRole.String()].Signed.Delegations.Roles) > 0
}

// Are all given delegations present in the snapshot trust data.
func (r *Repo) HasDelegationHashes(delegations []string) bool {
	for _, delegation := range delegations {
		if _, ok := r.Snapshot.Signed.Meta[delegation]; !ok {
			return false
		}
	}
	return true
}

// Downloads all given delegations and verifies them.
func (r *Repo) DownloadAndValidateDelegations(
	ctx context.Context,
	nc *NotaryClient,
	delegations []string,
) error {
	var errOut error
	trustDataChannel := make(chan TrustData, len(delegations))
	availableDelegationRoles := r.Targets[data.CanonicalTargetsRole.String()].Signed.Delegations.Roles

	logrus.Debugf(
		"available delegation roles: %s",
		utils.Map[*data.Role, string](
			availableDelegationRoles,
			func(role *data.Role) string { return role.Name.String() },
		),
	)

	for _, delegation := range delegations {
		found := false
		delegation := delegation
		for _, role := range availableDelegationRoles {
			if role.Name.String() == delegation {
				found = true
				break
			}
		}

		if !found {
			return fmt.Errorf("delegation %s not found", delegation)
		}

		go nc.FetchTrustData(
			ctx,
			delegation,
			trustDataChannel,
		)
	}

	for range delegations {
		select {
		case <-ctx.Done():
			return fmt.Errorf("context cancelled")
		default:
			trustData := <-trustDataChannel
			if trustData.Err != nil {
				return fmt.Errorf(
					"error downloading delegation %s: %s",
					trustData.Role,
					trustData.Err,
				)
			}

			r.Targets[trustData.Role], errOut = data.TargetsFromSigned(
				trustData.Data,
				data.RoleName(trustData.Role),
			)

			if errOut != nil {
				return fmt.Errorf("error parsing delegation %s", trustData.Role)
			}

			r.notCheckedChecksums[trustData.Role] = trustData.Raw
		}
	}

	// validate the delegations
	logrus.Debugf("validating delegations: %+v", delegations)
	errOut = r.validateDelegations(delegations)

	return errOut
}

// Validates the given delegations with keys from targets role.
func (r *Repo) validateDelegations(delegations []string) error {
	for _, delegation := range delegations {
		// check if the delegation is available
		delegationTarget, ok := r.Targets[delegation]
		if !ok {
			return fmt.Errorf("delegation %s not found", delegation)
		}

		// build the delegation role
		delegationRole, err := r.Targets[data.CanonicalTargetsRole.String()].BuildDelegationRole(
			data.RoleName(delegation),
		)
		if err != nil {
			return fmt.Errorf("error building delegation role %s: %s", delegation, err)
		}

		// get signed object and signed common
		signedCommon := &delegationTarget.Signed.SignedCommon
		signedObj, err := delegationTarget.ToSigned()
		if err != nil {
			return fmt.Errorf(
				"serialization error from signedTarget to signed for delegation %s: %s",
				delegation,
				err,
			)
		}

		// validate signatures
		if signed.VerifySignatures(signedObj, delegationRole.BaseRole) != nil {
			return fmt.Errorf(
				"error validating delegation %s signatures",
				delegation,
			)
		}

		// validate expiry
		if signed.VerifyExpiry(signedCommon, data.RoleName(delegation)) != nil {
			return fmt.Errorf("%s trust data expired", delegation)
		}

		// validate delegation checksums
		payload, ok := r.notCheckedChecksums[delegation]
		hashes := r.Snapshot.Signed.Meta[delegation].Hashes

		if !ok {
			return fmt.Errorf("no checksums found for %s", delegation)
		}

		if err := data.CheckHashes(payload, delegation, hashes); err != nil {
			return fmt.Errorf("error validating %s checksums: %s", delegation, err)
		}
	}

	return nil
}
