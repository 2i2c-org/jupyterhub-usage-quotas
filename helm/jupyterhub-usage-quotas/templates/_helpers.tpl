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
    Values from config.UsageViewer. The URLs follow the defaults of the
    UsageViewer traits.
*/}}
{{- define "jupyterhub-usage-quotas.serviceName" -}}
{{- (.Values.config.UsageViewer | default dict).service_name | default "usage-quota" }}
{{- end }}

{{- define "jupyterhub-usage-quotas.publicHubUrl" -}}
{{- required "config.UsageViewer.public_hub_url is required, e.g. https://hub.example.org/" (.Values.config.UsageViewer | default dict).public_hub_url }}
{{- end }}

{{- define "jupyterhub-usage-quotas.publicOrigin" -}}
{{- $publicHubUrl := include "jupyterhub-usage-quotas.publicHubUrl" . }}
{{- $url := urlParse $publicHubUrl }}
{{- if not (and $url.scheme $url.host) }}
{{- fail (printf "config.UsageViewer.public_hub_url must be an absolute URL, e.g. https://hub.example.org/, got %q" $publicHubUrl) }}
{{- end }}
{{- printf "%s://%s" $url.scheme $url.host }}
{{- end }}

{{- define "jupyterhub-usage-quotas.baseUrl" -}}
{{- $path := (urlParse (include "jupyterhub-usage-quotas.publicHubUrl" .)).path | trimSuffix "/" | trimSuffix "/hub" }}
{{- printf "%s/" $path }}
{{- end }}

{{- define "jupyterhub-usage-quotas.servicePrefix" -}}
{{- (.Values.config.UsageViewer | default dict).service_prefix | default (printf "%sservices/%s/" (include "jupyterhub-usage-quotas.baseUrl" .) (include "jupyterhub-usage-quotas.serviceName" .)) }}
{{- end }}
