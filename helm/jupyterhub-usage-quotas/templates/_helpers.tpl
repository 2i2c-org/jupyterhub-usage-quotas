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

{{- /*
    URLs derived from jupyterhub.publicUrl
*/}}
{{- define "jupyterhub-usage-quotas.publicOrigin" -}}
{{- $url := required "jupyterhub.publicUrl is required, e.g. https://hub.example.org/" .Values.jupyterhub.publicUrl | urlParse }}
{{- if not (and $url.scheme $url.host) }}
{{- fail (printf "jupyterhub.publicUrl must be an absolute URL, e.g. https://hub.example.org/, got %q" .Values.jupyterhub.publicUrl) }}
{{- end }}
{{- printf "%s://%s" $url.scheme $url.host }}
{{- end }}

{{- define "jupyterhub-usage-quotas.baseUrl" -}}
{{- $path := (urlParse .Values.jupyterhub.publicUrl).path | trimSuffix "/" }}
{{- printf "%s/" $path }}
{{- end }}

{{- define "jupyterhub-usage-quotas.servicePrefix" -}}
{{- printf "%sservices/%s/" (include "jupyterhub-usage-quotas.baseUrl" .) .Values.jupyterhub.serviceName }}
{{- end }}
