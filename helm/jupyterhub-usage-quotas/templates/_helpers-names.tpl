{{- /*
    These helpers encapsulate logic on how we name resources. They also enable
    parent charts to reference these dynamic resource names.

    To avoid duplicating documentation, for more information, please see the
    fullnameOverride entry in the jupyterhub chart's configuration reference:
    https://z2jh.jupyter.org/en/latest/resources/reference.html#fullnameOverride
*/}}



{{- /*
    Utility templates
*/}}

{{- /*
    Renders to a prefix for the chart's resource names. This prefix is assumed to
    make the resource name cluster unique.
*/}}
{{- define "jupyterhub-usage-quotas.fullname" -}}
    {{- /*
        We have implemented a trick to allow a parent chart depending on this
        chart to call these named templates.

        Caveats and notes:

            1. While parent charts can reference these, grandparent charts can't.
            2. Parent charts must not use an alias for this chart.
            3. There is no failsafe workaround to above due to
               https://github.com/helm/helm/issues/9214.
            4. .Chart is of its own type (*chart.Metadata) and needs to be casted
               using "toYaml | fromYaml" in order to be able to use normal helm
               template functions on it.
    */}}
    {{- $fullname_override := .Values.fullnameOverride }}
    {{- $name_override := .Values.nameOverride }}
    {{- if ne .Chart.Name "jupyterhub-usage-quotas" }}
        {{- with index .Values "jupyterhub-usage-quotas" }}
            {{- $fullname_override = .fullnameOverride }}
            {{- $name_override = .nameOverride }}
        {{- end }}
    {{- end }}

    {{- if eq (typeOf $fullname_override) "string" }}
        {{- $fullname_override }}
    {{- else }}
        {{- $name := $name_override | default "jupyterhub-usage-quotas" }}
        {{- if contains $name .Release.Name }}
            {{- .Release.Name }}
        {{- else }}
            {{- .Release.Name }}-{{ $name }}
        {{- end }}
    {{- end }}
{{- end }}

{{- /*
    Renders to a blank string or if the fullname template is truthy renders to it
    with an appended dash.
*/}}
{{- define "jupyterhub-usage-quotas.fullname.dash" -}}
    {{- if (include "jupyterhub-usage-quotas.fullname" .) }}
        {{- include "jupyterhub-usage-quotas.fullname" . }}-
    {{- end }}
{{- end }}



{{- /*
    Namespaced resources
*/}}

{{- /* usage-viewer resources' default name */}}
{{- define "jupyterhub-usage-quotas.usage-viewer.fullname" -}}
    {{- include "jupyterhub-usage-quotas.fullname.dash" . }}usage-viewer
{{- end }}

{{- /* usage-viewer's ServiceAccount name */}}
{{- define "jupyterhub-usage-quotas.usage-viewer.serviceaccount.fullname" -}}
    {{- if .Values.serviceAccount.create }}
        {{- .Values.serviceAccount.name | default (include "jupyterhub-usage-quotas.usage-viewer.fullname" .) }}
    {{- else }}
        {{- .Values.serviceAccount.name }}
    {{- end }}
{{- end }}



{{- /*
    Cluster wide resources

    We currently have no cluster wide resources. If you add one in the future,
    add an entry here that mimics how the jupyterhub helm chart does it.
*/}}
