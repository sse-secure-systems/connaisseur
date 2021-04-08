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
            {{- if $validator.auth.secret_name -}}
                {{- $_ := set $external_secret $validator.name $validator.auth.secret_name -}}
            {{- end -}}
        {{- end -}}
    {{- else if eq $validator.type "notaryv2" -}}
    {{- else if eq $validator.type "cosign" -}}
    {{- end -}}
{{- end -}}
{{- range $k, $v := $external_secret -}}
    - name: {{ $k }}-vol
  secret:
    secretName: {{ $v }}
{{- end -}}
{{- end -}}


{{- define "external-secrets-mount" -}}
{{- $external_secret := dict -}}
{{- range .Values.validators -}}
    {{- $validator := deepCopy . -}}
    {{- if eq $validator.type "notaryv1" -}}
        {{- if $validator.auth -}}
            {{- if $validator.auth.secret_name -}}
                {{- $_ := set $external_secret $validator.name $validator.auth.secret_name -}}
            {{- end -}}
        {{- end -}}
    {{- else if eq $validator.type "notaryv2" -}}
    {{- else if eq $validator.type "cosign" -}}
    {{- end -}}
{{- end -}}
{{- range $k, $v :=  $external_secret -}}
    - name: {{ $k }}-vol
  mountPath: /app/connaisseur-config/{{ $k }}
  readOnly: True
{{- end -}}
{{- end -}}