import yaml

if __name__ == "__main__":
    with open("helm/values.yaml", "r") as f:
        config = yaml.safe_load(f)

    ### Create backup copy
    with open("helm/values.yaml.old", "w") as f:
        yaml.dump(config, f)

    ### Remove image tag or digest
    image = config["deployment"]["image"]
    # lossy heuristic for where to split image and tag/digest
    if "@sha256:" in image:
        repo = image[0 : image.index("@sha256:")]
    else:
        repo = ":".join(image.split(":")[:-1])
    config["deployment"]["image"] = {"repository": repo}

    ### Set kubernetes config
    deployment = config.pop("deployment")
    service = config.pop("service")
    failure_policy = deployment.pop("failurePolicy", None)
    reinvocation_policy = deployment.pop("reinvocationPolicy", None)
    webhook = {}
    if failure_policy is not None:
        webhook["failurePolicy"] = failure_policy
    if reinvocation_policy is not None:
        webhook["reinvocationPolicy"] = reinvocation_policy
    config["kubernetes"] = {"deployment": deployment, "service": service}
    if webhook:
        config["kubernetes"].update({"webhook": webhook})

    ### Drop debug key
    debug = config.pop("debug", False)
    if debug:
        config["logLevel"] = "DEBUG"

    ### Set application config
    log_level = config.pop("logLevel", "INFO")
    validators = config.pop("validators")
    policy = config.pop("policy")

    detection_mode = bool(config.pop("detectionMode", False))
    namespaced_validation = config.pop("namespacedValidation", {"enabled": False})
    # check explicitly disabled config won't be taken as enabled
    if not namespaced_validation.pop("enabled"):
        namespaced_validation = False
    child_approval = bool(
        config.pop("automaticChildApproval", {"enabled": True}).get("enabled")
    )
    unchanged_approval = bool(config.pop("automaticUnchangedApproval", False))
    features = {
        "detectionMode": detection_mode,
        "namespacedValidation": namespaced_validation,
        "automaticChildApproval": child_approval,
        "automaticUnchangedApproval": unchanged_approval,
    }

    config["application"] = {
        "logLevel": log_level,
        "validators": validators,
        "policy": policy,
        "features": features,
    }

    ### Move Rekor host key
    for validator in config["application"]["validators"]:
        if validator["type"] == "cosign":
            rekor_host = validator.pop("host", None)
            if rekor_host is not None:
                validator["host"] = {"rekor": rekor_host}

    ### Rename alerting receivers
    alerting = config.get("alerting", {})
    admit_receivers = alerting.get("admit_request", {}).pop("templates", None)
    if admit_receivers is not None:
        alerting["admit_request"]["receivers"] = admit_receivers
    reject_receivers = alerting.get("reject_request", {}).pop("templates", None)
    if reject_receivers is not None:
        alerting["reject_request"]["receivers"] = reject_receivers

    ### Rename snake_case variables
    for validator in config["application"]["validators"]:
        # trust_roots may have been explicitly None due to our default config and must then be set
        if "trust_roots" in validator:
            trust_roots = validator.pop("trust_roots")
            validator["trustRoots"] = trust_roots
        secret_name = validator.get("auth", {}).pop("secret_name", None)
        if secret_name is not None:
            validator["auth"]["secretName"] = secret_name
        k8s_keychain = validator.get("auth", {}).pop("k8s_keychain", None)
        if k8s_keychain is not None:
            validator["auth"]["useKeychain"] = k8s_keychain
        if validator.pop("is_acr", False):
            validator["isAcr"] = True

    for rule in config["application"]["policy"]:
        trust_root = rule.get("with", {}).pop("trust_root", None)
        if trust_root is not None:
            rule["with"]["trustRoot"] = trust_root

    if config.get("alerting", {}):
        cluster_identifier = config["alerting"].pop("cluster_identifier", None)
        if cluster_identifier is not None:
            config["alerting"]["clusterIdentifier"] = cluster_identifier

        admit = config["alerting"].pop("admit_request", None)
        if admit is not None:
            for receiver in admit["receivers"]:
                receiver["receiverUrl"] = receiver.pop("receiver_url")
                custom_headers = receiver.pop("custom_headers", None)
                if custom_headers is not None:
                    receiver["customHeaders"] = custom_headers
                payload_fields = receiver.pop("payload_fields", None)
                if payload_fields is not None:
                    receiver["payloadFields"] = payload_fields
                fail_if_alert_sending_fails = receiver.pop(
                    "fail_if_alert_sending_fails", None
                )
                if fail_if_alert_sending_fails is not None:
                    receiver["failIfAlertSendingFails"] = fail_if_alert_sending_fails
            config["alerting"]["admitRequest"] = admit

        reject = config["alerting"].pop("reject_request", None)
        if reject is not None:
            for receiver in reject["receivers"]:
                receiver["receiverUrl"] = receiver.pop("receiver_url")
                custom_headers = receiver.pop("custom_headers", None)
                if custom_headers is not None:
                    receiver["customHeaders"] = custom_headers
                payload_fields = receiver.pop("payload_fields", None)
                if payload_fields is not None:
                    receiver["payloadFields"] = payload_fields
                fail_if_alert_sending_fails = receiver.pop(
                    "fail_if_alert_sending_fails", None
                )
                if fail_if_alert_sending_fails is not None:
                    receiver["failIfAlertSendingFails"] = fail_if_alert_sending_fails
            config["alerting"]["rejectRequest"] = reject

    ### Write new config
    with open("helm/values.yaml", "w") as f:
        yaml.dump(config, f)
