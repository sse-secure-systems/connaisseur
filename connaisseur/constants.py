# Webhooks time out after 30s, so we need to respond before that or the Connaisseur webhook will fail
# with a generic error message, see https://github.com/sse-secure-systems/connaisseur/issues/448
MUTATE_TIMEOUT_SECONDS = 29
SHA256 = "sha256"
DETECTION_MODE = "DETECTION_MODE"
AUTOMATIC_CHILD_APPROVAL = "AUTOMATIC_CHILD_APPROVAL"
AUTOMATIC_UNCHANGED_APPROVAL = "AUTOMATIC_UNCHANGED_APPROVAL"
