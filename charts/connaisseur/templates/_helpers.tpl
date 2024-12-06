{{/*
Expand the name of the chart.
*/}}
{{- define "connaisseur.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "connaisseur.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "connaisseur.labels" -}}
helm.sh/chart: {{ include "connaisseur.chart" . }}
{{ include "connaisseur.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .Values.kubernetes.additionalLabels }}
{{ toYaml .Values.kubernetes.additionalLabels }}
{{- end -}}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "connaisseur.selectorLabels" -}}
app.kubernetes.io/name: {{ include "connaisseur.name" . }}
app.kubernetes.io/instance: {{ .Chart.Name }}
{{- if .Values.kubernetes.deployment.podLabels }}
{{ toYaml .Values.kubernetes.deployment.podLabels }}
{{- end -}}
{{- end }}

{{/*
Selector labels for redis
*/}}
{{- define "connaisseur.redisSelectorLabels" -}}
app.kubernetes.io/name: {{ include "connaisseur.name" . }}
app.kubernetes.io/instance: redis
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "connaisseur.serviceName" -}}
{{- include "connaisseur.name" . }}-svc
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "connaisseur.serviceAccountName" -}}
{{- include "connaisseur.name" . }}-serviceaccount
{{- end }}

{{/*
Create the name of the TLS secrets to use
*/}}
{{- define "connaisseur.TLSName" -}}
{{- include "connaisseur.name" . }}-tls
{{- end }}

{{/*
Create the name of the webhook to use
*/}}
{{- define "connaisseur.webhookName" -}}
{{- include "connaisseur.name" . }}-webhook
{{- end }}

{{/*
Create the name of the application configuration to use
*/}}
{{- define "connaisseur.appConfigName" -}}
{{- include "connaisseur.name" . }}-app-config
{{- end }}

{{/*
Create the name of the enviroment variables to use
*/}}
{{- define "connaisseur.envName" -}}
{{- include "connaisseur.name" . }}-env
{{- end }}

{{/*
Create the name of the environment variable secrets to use
*/}}
{{- define "connaisseur.envSecretName" -}}
{{- include "connaisseur.name" . }}-env-secret
{{- end }}

{{/*
Create the name of the role to use
*/}}
{{- define "connaisseur.roleName" -}}
{{- include "connaisseur.name" . }}-role
{{- end }}

{{/*
Create the name of the role binding to use
*/}}
{{- define "connaisseur.roleBindingName" -}}
{{- include "connaisseur.name" . }}-role-binding
{{- end }}

{{/*
Create the name of the cluster role to use
*/}}
{{- define "connaisseur.clusterRoleName" -}}
{{- include "connaisseur.name" . }}-cluster-role
{{- end }}

{{/*
Create the name of the cluster role binding to use
*/}}
{{- define "connaisseur.clusterRoleBindingName" -}}
{{- include "connaisseur.name" . }}-cluster-role-binding
{{- end }}

{{/*
Create the name of the alerting templates
*/}}
{{- define "connaisseur.alertTemplatesName" -}}
{{- include "connaisseur.name" . }}-alert-templates
{{- end -}}

{{/*
Create the name of the alerting configuration
*/}}
{{- define "connaisseur.alertConfigName" -}}
{{- include "connaisseur.name" . -}}-alert-config
{{- end -}}

{{/*
Create the name of the redis depoyment
*/}}
{{- define "connaisseur.redisName" -}}
{{- include "connaisseur.name" . }}-redis
{{- end -}}

{{/*
Create the name of the redis service
*/}}
{{- define "connaisseur.redisService" -}}
{{- include "connaisseur.name" . }}-redis-service
{{- end -}}

{{/*
Create the name of the redis secret (password)
*/}}
{{- define "connaisseur.redisSecret" -}}
{{- include "connaisseur.name" . }}-redis-secret
{{- end -}}

{{/*
Create the name of the redis tls secret
*/}}
{{- define "connaisseur.redisTLS" -}}
{{- include "connaisseur.name" . }}-redis-tls
{{- end -}}

{{/*
Create the name of the pod disruption budget
*/}}
{{- define "connaisseur.podDisruptionBudget" -}}
{{- include "connaisseur.name" . }}-pod-disruption-budget
{{- end -}}

{{/*
Extract Kubernetes Minor Version.
*/}}
{{- define "connaisseur.k8s-version-minor" -}}
{{- trimSuffix "." (trimPrefix "v1." (regexFind "v\\d\\.\\d{1,2}\\." .Capabilities.KubeVersion.Version)) -}} {* TODO: not future safe *}
{{- end -}}


{{/*
Name of the connaisseur image
*/}}
{{- define "connaisseur.image" -}}
    {{ .Values.kubernetes.deployment.image.repository }}:{{ default (print "v" .Chart.AppVersion) .Values.kubernetes.deployment.image.tag }}
{{- end -}}

{{/*
Name of the namespace selector key
*/}}
{{- define "conaisseur.namespaceSelectorKey" -}}
securesystemsengineering.connaisseur/webhook
{{- end -}}


{{/*
Collect the names of all authentication secrets
*/}}
{{- define "connaisseur.validatorSecrets" -}}
{{- $secrets := list -}}
{{- range .Values.application.validators -}}
    {{- if hasKey . "auth" -}}
        {{- if hasKey .auth "secretName" -}}
            {{- $secrets = append $secrets .auth.secretName -}}
        {{- else if and (hasKey .auth "username") (hasKey .auth "password") (or (eq .type "notaryv1") (hasKey .auth "registry")) -}}
            {{- $secrets = append $secrets (print .name "-auth") -}}
        {{- end -}}
    {{- end -}}
{{- end -}}
{{- $dict := dict "list" $secrets -}}
{{ $dict | toYaml }}
{{- end -}}

{{/*
Volume definitions for all authentication secrets
*/}}
{{- define "connaisseur.validatorSecretVolumes" -}}
{{- $secrets := ((include "connaisseur.validatorSecrets" .) | fromYaml ) -}}
{{- range (get $secrets "list") }}
- name: {{ . }}-volume
  secret:
    secretName: {{ . }}
{{- end -}}
{{- end -}}

{{/*
Volume mounts for all authentication secrets
*/}}
{{- define "connaisseur.validatorSecretMounts" -}}
{{- $secrets := ((include "connaisseur.validatorSecrets" .) | fromYaml ) -}}
{{- range (get $secrets "list" ) }}
- name: {{ . }}-volume
  mountPath: /app/secrets/{{ . }}
  readOnly: True
{{- end -}}
{{- end -}}

{{/*
Render all configuration files
*/}}
{{- define "connaisseur.getConfigFiles" -}}
{{ include (print $.Template.BasePath "/configmaps.yaml") . }}
{{ include (print $.Template.BasePath "/env.yaml") . }}
{{ include (print $.Template.BasePath "/secrets.yaml") . }}
{{- end -}}

{{/*
Get checksum of all configuration files. To be used for the deployment as annotation.
Should any configuration change, that the deployment must reload, the checksum
will change, cause the deployment to be redeployed.
*/}}
{{- define "connaisseur.getConfigChecksum" -}}
{{- $configs := list (include "connaisseur.getConfigFiles" . | sha256sum) -}}

{{- if hasKey .Values.kubernetes.deployment "tls" | and (not (empty .Values.kubernetes.deployment.tls )) -}}
    {{- $configs = append $configs (print .Values.kubernetes.deployment.tls | sha256sum) -}}
{{- end -}}
{{- if hasKey .Values.kubernetes.redis "tls" | and (not (empty .Values.kubernetes.redis.tls )) -}}
    {{- $configs = append $configs (print .Values.kubernetes.redis.tls | sha256sum) -}}
{{- end -}}

{{ join "\n" $configs | sha256sum }}
{{- end -}}

{{/*
Volume definitions for all alerts
*/}}
{{- define "connaisseur.alertVolumes" -}}
- name: {{ include "connaisseur.alertConfigName" . }}
  configMap:
    name: {{ include "connaisseur.alertConfigName" . }}
{{- if .Values.alerting }}
- name: {{ include "connaisseur.alertTemplatesName" . }}
  configMap:
    name: {{ include "connaisseur.alertTemplatesName" . }}
{{- end -}}
{{- end -}}

{{/*
Volume mounts for all alerts
*/}}
{{- define "connaisseur.alertMounts" -}}
- name: {{ include "connaisseur.alertConfigName" . }}
  mountPath: /app/alerts/config.yaml
  readOnly: true
  subPath: config.yaml
{{- if .Values.alerting }}
- name: {{ include "connaisseur.alertTemplatesName" . }}
  mountPath: /app/alerts/templates
  readOnly: true
{{- end -}}
{{- end -}}

{{/*
Will make a call to the Kubernetes API to get the value of a secret.
Expects a dictionary as input with the following keys:
- name: name of the secret
- key: key of the value to get
- namespace: namespace of the secret
*/}}
{{- define "connaisseur.LookUpSecret" -}}
{{- $data := (lookup "v1" "Secret" .namespace .name).data -}}
{{- if $data -}}
    {{ get $data .key }}
{{- end -}}
{{- end -}}

{{/*
Will look for an already installed redis password secret and return it.
If there is no such secret, it will generate a new password and return it.
*/}}
{{- define "connaisseur.redisPassword" -}}
{{- $args := dict "name" (include "connaisseur.redisSecret" .) "key" "REDIS_PASSWORD" "namespace" .Release.Namespace -}}
{{- $pw := (include "connaisseur.LookUpSecret" $args) | default (uuidv4 | b64enc) -}}
{{ $pw }}
{{- end -}}

{{/*
Set up certificate and private key to use for TLS communication:
If there's a configured one in the values.yaml, use that to allow rotation
Otherwise, if there's an existing installation re-use the previous certificate
Otherwise, generate a new self-signed certificate

Expects a dictionary as input with the following keys:
- deployment: the dict of the deployment, which should include a tls section (e.g. .Values.kubernetes.deployment or .Values.kubernetes.redis)
- tlsName: the name of the secret to potentially reuse
- svc: the name of the service
- namespace: the namespace of the service

Returns a dictionary in yaml format with the following keys:
- cert: the certificate
- key: the private key
*/}}
{{- define "connaisseur.tlsCertificate" -}}
{{- include "connaisseur.validateTLSConfig" .deployment -}}

{{- $altNames := list -}}
{{- $altNames = append $altNames (printf "%s" .svc) -}}
{{- $altNames = append $altNames (printf "%s.%s" .svc .namespace) -}}
{{- $altNames = append $altNames (printf "%s.%s.svc" .svc .namespace) -}}
{{- $altNames = append $altNames (printf "%s.%s.svc.cluster.local" .svc .namespace) -}}
{{- $newCertificate := genSelfSignedCert (printf "%s.%s.svc" .svc .namespace) nil $altNames 36500 -}}

{{- $certArgs := dict "name" .tlsName "namespace" .namespace "key" "tls.crt" -}}
{{- $keyArgs := dict "name" .tlsName "namespace" .namespace "key" "tls.key" -}}
{{- $installedCert := include "connaisseur.LookUpSecret" $certArgs -}}
{{- $installedKey := include "connaisseur.LookUpSecret" $keyArgs -}}
{{ $encodedTLSCert := default ($newCertificate.Cert | b64enc) ($installedCert) }}
{{ $encodedTLSKey := default ($newCertificate.Key | b64enc) ($installedKey) }}

{{- if hasKey .deployment "tls" -}}
  {{- if hasKey .deployment.tls "key" -}}
    {{- $certByHelmConfig := buildCustomCert (.deployment.tls.cert | b64enc) (.deployment.tls.key | b64enc) -}}
    {{- $encodedTLSCert = $certByHelmConfig.Cert | b64enc -}}
    {{- $encodedTLSKey = $certByHelmConfig.Key | b64enc -}}
  {{- end -}}
{{- end -}}

{{- $return := dict "cert" $encodedTLSCert "key" $encodedTLSKey -}}
{{ $return | toYaml}}
{{- end -}}

{{/*
Validates the TLS configuration of a deployment.
If configured, the deployment must have both a cert and a key.

Expects a dictionary as input with the following keys:
- deployment: the dict of the deployment, which should include a tls section (e.g. .Values.kubernetes.deployment or .Values.kubernetes.redis)
*/}}
{{- define "connaisseur.validateTLSConfig" -}}
# input: deployment, e.g. .Values.kubernetes.deployment or .Values.kubernetes.redis
{{- if hasKey . "tls" -}}
    {{- if and (not (hasKey .tls "cert")) (hasKey .tls "key")}}
        {{ fail "Helm configuration has a 'tls' section with a 'key' attribute, but is missing the 'cert' attribute." -}}
    {{- end -}}
    {{- if and (not (hasKey .tls "key")) (hasKey .tls "cert")}}
        {{ fail "Helm configuration has a 'tls' section with a 'cert' attribute, but is missing the 'key' attribute." -}}
    {{- end -}}
{{- end -}}
{{- end -}}
