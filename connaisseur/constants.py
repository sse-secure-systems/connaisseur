# We use aiohttp to connect to external sources. Webhooks time out after 30s,
# so we need to respond before that or the Connaisseur webhook will fail with a
# generic error message, see https://github.com/sse-secure-systems/connaisseur/issues/448
# Since the timeouts in aiohttp are ceiled to full seconds
# (https://docs.aiohttp.org/en/stable/client_quickstart.html#timeouts),
# we can't get closer to 30 than 29 without failing to respond within 30 a lot more often
AIO_TIMEOUT_SECONDS = 29
SHA256 = "sha256"
DETECTION_MODE = "DETECTION_MODE"
AUTOMATIC_CHILD_APPROVAL = "AUTOMATIC_CHILD_APPROVAL"
AUTOMATIC_UNCHANGED_APPROVAL = "AUTOMATIC_UNCHANGED_APPROVAL"
