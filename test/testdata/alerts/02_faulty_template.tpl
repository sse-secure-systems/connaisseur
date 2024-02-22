{{- if .Skipped -}}
reason: {{ .SkipReason }}
{{- else if .Error -}}
error: {{ .Error }}
{{- else -}}
new: {{ .NewImage }}, old: {{ .OldImage }}
