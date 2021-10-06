#! /bin/bash

yq e 'del(.deployment.securityContext.seccompProfile)' -i helm/values.yaml
yq e '.deployment.annotations."seccomp.security.alpha.kubernetes.io/pod" = "runtime/default"' -i helm/values.yaml

