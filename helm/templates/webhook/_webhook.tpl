{{- define "connaisseur.namespaceLabels" }}
de.securesystems.connaisseur/enabled: "true"
de.securesystems.connaisseur/release: "{{ .Release.Name }}"
de.securesystems.connaisseur/rootPubKeyHash: "{{ trim .Values.notary.rootPubKey | sha1sum }}"
{{ end -}}
