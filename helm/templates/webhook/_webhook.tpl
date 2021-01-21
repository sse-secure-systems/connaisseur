{{- define "connaisseur.namespaceLabels" }}
de.securesystems.connaisseur/enabled: "true"
de.securesystems.connaisseur/release: "{{ .Release.Name }}"
{{ end -}}
