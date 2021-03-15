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


{{- define "anyIntAuth" -}}
{{- range $i := .Values.notaries }}
{{- if $i.auth }}
{{- if not $i.auth.secret_name}}
true
{{- end }}
{{- end }}
{{- end }}
{{- end -}}


{{- define "getIntAuth" -}}
USER: {{ .user }}
PASS: {{ .password }}
{{- end -}}


{{- define "getAuthSecretVol" -}}
{{- range $i := .Values.notaries -}}
{{- if $i.auth }}
- name: {{ $i.name }}-secret
  secret:
    {{- if $i.auth.secret_name }}
    secretName: {{ $i.auth.secret_name }}
    {{- else }}
    secretName: {{ $i.name }}-host-secret
    {{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}


{{- define "getAuthSecretVolMount" -}}
{{- range $i := .Values.notaries -}}
{{- if $i.auth }}
- name: {{ $i.name }}-secret
  mountPath: /etc/creds/{{ $i.name }}
  readOnly: true
{{ end -}}
{{- end -}}
{{- end -}}


{{- define "selfsigned" -}}
{{- range $i := .Values.notaries -}}
{{- if $i.selfsigned_cert -}}
{{ $i.name }}.crt: {{ $i.selfsigned_cert | b64enc }} 
{{ end -}}
{{- end -}}
{{- end -}}
