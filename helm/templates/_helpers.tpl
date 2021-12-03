{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "helm.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}


{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "helm.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}


{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "helm.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}


{{- define "helm.labels" -}}
app.kubernetes.io/name: {{ include "helm.name" . }}
helm.sh/chart: {{ include "helm.chart" . }}
app.kubernetes.io/instance: {{ .Chart.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}


{{/*
Extract Kubernetes Minor Version.
*/}}
{{- define "k8s-version-minor" -}}
{{- trimSuffix "." (trimPrefix "v1." (regexFind "v\\d\\.\\d{1,2}\\." .Capabilities.KubeVersion.Version)) -}}
{{- end -}}


{{- define "config-secrets" -}}
{{- $secret_dict := dict -}}
{{- range .Values.validators -}}
    {{- $validator := deepCopy . -}}
    {{- if eq $validator.type "notaryv1" -}}
        {{- if $validator.auth -}}
            {{- if not $validator.auth.secret_name -}}
                {{- $_ := set $secret_dict $validator.name (dict "auth" $validator.auth) -}}
            {{- end -}}
        {{- end -}}
    {{- else if eq $validator.type "notaryv2" -}}
    {{- else if eq $validator.type "cosign" -}}
        {{- if $validator.cert -}}
            {{- $_ := set $secret_dict $validator.name (dict "cert" $validator.cert) -}}
        {{- end -}}
    {{- end -}}
{{- end -}}
{{ $secret_dict | toYaml | trim }}
{{- end -}}


{{- define "external-secrets-vol" -}}
{{- $external_secret := dict -}}
{{- range .Values.validators -}}
    {{- $validator := deepCopy . -}}
    {{- if eq $validator.type "notaryv1" -}}
        {{- if $validator.auth -}}
            {{ if $validator.auth.secret_name }}
- name: {{ $validator.name }}-vol
  secret:
    secretName: {{ $validator.auth.secret_name }}
            {{- end -}}
        {{- end -}}
    {{- else if eq $validator.type "notaryv2" -}}
    {{- else if eq $validator.type "cosign" -}}
        {{- if $validator.auth -}}
            {{ if $validator.auth.secret_name }}
- name: {{ $validator.name }}-vol
  secret:
    secretName: {{ $validator.auth.secret_name }}
    items:
      - key: .dockerconfigjson
        path: config.json
            {{- end -}}
        {{- end -}}
    {{- end -}}
{{- end -}}
{{- end -}}


{{- define "external-secrets-mount" -}}
{{- $external_secret := dict -}}
{{ range .Values.validators }}
    {{- $validator := deepCopy . -}}
    {{- if eq $validator.type "notaryv1" -}}
        {{- if $validator.auth -}}
            {{ if $validator.auth.secret_name }}
- name: {{ $validator.name }}-vol
  mountPath: /app/connaisseur-config/{{ $validator.name }}
  readOnly: True
            {{- end -}}
        {{- end -}}
    {{- else if eq $validator.type "notaryv2" -}}
    {{- else if eq $validator.type "cosign" -}}
        {{- if $validator.auth -}}
            {{ if $validator.auth.secret_name }}
- name: {{ $validator.name }}-vol
  mountPath: /app/connaisseur-config/{{ $validator.name }}/.docker/
  readOnly: True
            {{- end -}}
        {{- end -}}
    {{- end -}}
{{- end -}}
{{- end -}}


{{- define "getInstalledTLSCert" -}}
{{- $data := (lookup "v1" "Secret" "connaisseur" (printf "%s-tls" .Chart.Name)).data -}}
{{- if $data -}}
    {{ get $data "tls.crt" }}
{{- end -}}
{{- end -}}


{{- define "getInstalledTLSKey" -}}
{{- $data := (lookup "v1" "Secret" "connaisseur" (printf "%s-tls" .Chart.Name)).data -}}
{{- if $data -}}
    {{ get $data "tls.key" }}
{{- end -}}
{{- end -}}


{{- define "getConfigFiles" -}}
{{ include (print $.Template.BasePath "/config.yaml") . }}
{{ include (print $.Template.BasePath "/config-secrets.yaml") . }}
{{ include (print $.Template.BasePath "/env.yaml") . }}
{{ include (print $.Template.BasePath "/alertconfig.yaml") . }}
{{- end -}}


{{- define "hasCosignCerts" -}}  
{{- range .Values.validators     -}}
    {{- if and (eq .type "cosign") (hasKey . "cert") -}}
        1
    {{- end -}}
{{- end -}}
{{- end -}}


{{- define "getCosignCerts" -}}
{{- range .Values.validators     -}}
    {{- if and (eq .type "cosign") (hasKey . "cert") }}
    {{ .name }}.crt: {{ .cert | b64enc -}}
    {{- end -}}
{{- end -}}
{{- end -}}


{{- define  "cosignCertVol" -}}
{{- if (include "hasCosignCerts" .) -}}
- name: {{ .Chart.Name }}-cosign-certs
  secret:
    secretName: {{ .Chart.Name }}-cosign-certs
{{- end -}}
{{- end -}}


{{- define  "cosignCertVolMount" -}}
{{- if (include "hasCosignCerts" .) -}}
- name: {{ .Chart.Name }}-cosign-certs
  mountPath: /app/certs/cosign
  readOnly: true
{{- end -}}
{{- end -}}
