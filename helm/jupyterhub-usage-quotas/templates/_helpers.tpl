{{/*
Expand the name of the chart.
*/}}
{{- define "jupyterhub-usage-quotas.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "jupyterhub-usage-quotas.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "jupyterhub-usage-quotas.resourceName" -}}
{{- include "jupyterhub-usage-quotas.name" . -}}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "jupyterhub-usage-quotas.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
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

{{/*
Selector labels
*/}}
{{- define "jupyterhub-usage-quotas.selectorLabels" -}}
app.kubernetes.io/name: {{ include "jupyterhub-usage-quotas.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
