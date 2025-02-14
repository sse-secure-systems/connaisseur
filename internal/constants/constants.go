package constants

type ctxkey int

const (
	Logger ctxkey = iota
	ConnaisseurConfig
	AlertingConfig
	Cache
	KubeAPI
	RequestId
)

const (
	AutomaticChildApproval     = "AUTOMATIC_CHILD_APPROVAL"
	AutomaticUnchangedApproval = "AUTOMATIC_UNCHANGED_APPROVAL"
	DetectionMode              = "DETECTION_MODE"
	ResourceValidationMode     = "RESOURCE_VALIDATION_MODE"
	LogLevel                   = "LOG_LEVEL"
	LogFormat                  = "LOG_FORMAT"
	PodName                    = "POD_NAME"
	DefaultAuthFile            = "secret.yaml"
	DockerAuthFile             = ".dockerconfigjson"
	DefaultDockerRegistry      = "index.docker.io"
	DefaultRedisPort           = 6379
	DefaultCacheExpirySeconds  = 30
	CacheExpirySecondsKey      = "CACHE_EXPIRY_SECONDS"
	CacheErrorsKey             = "CACHE_ERRORS"
	EmptyAuthRegistry          = "EMPTYAUTH"
)

const (
	// constant error messages
	MethodNotAllowed   = "Method not allowed."
	ServiceUnavailable = "Service unavailable."
)

const (
	// Validation mode names
	MutateMode   = "mutate"
	ValidateMode = "insecureValidateOnly"
)

const (
	// Timeouts
	HTTPTimeoutSeconds         = 30
	ValidationTimeoutSeconds   = 29 // Keep below 30 such that we can respond before k8s API times out request to Connaisseur
	TLSHandshakeTimeoutSeconds = 10
)

const (
	// Available validator types
	StaticValidator   = "static"
	CosignValidator   = "cosign"
	NotaryV1Validator = "notaryv1"
	NotationValidator = "notation"
)

const (
	DefaultNotaryHost = "notary.docker.io"
)

const (
	// The default URL for the Rekor host during Cosign validation
	DefaultRekorHost = "https://rekor.sigstore.dev"
)

// variable so we can override it in tests
var (
	ConfigDir        = "/app/config"
	CertDir          = "/app/certs"
	AlertDir         = "/app/alerts"
	AlertTemplateDir = "/app/alerts/templates"
	SecretsDir       = "/app/secrets"
	RedisCertDir     = "/app/redis-certs"
)

const (
	// Notification Reasons
	NotificationResultSuccess = "success"
	NotificationResultError   = "error"
	NotificationResultSkip    = "skip"
	NotificationResultTimeout = "timeout"
	NotificationResultInvalid = "invalid"
)

type ConnaisseurLogFormat uint32

const (
	LogFormatJson ConnaisseurLogFormat = iota
	LogFormatJsonPretty
)
