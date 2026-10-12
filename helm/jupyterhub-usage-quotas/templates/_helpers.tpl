{{- /*
    Chart name and version, as used by the helm.sh/chart label.
*/}}
{{- define "jupyterhub-usage-quotas.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- /*
    Common labels
*/}}
{{- define "jupyterhub-usage-quotas.labels" -}}
helm.sh/chart: {{ include "jupyterhub-usage-quotas.chart" . }}
{{ include "jupyterhub-usage-quotas.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- /*
    Selector labels
*/}}
{{- define "jupyterhub-usage-quotas.selectorLabels" -}}
app.kubernetes.io/name: {{ .Values.nameOverride | default .Chart.Name | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
