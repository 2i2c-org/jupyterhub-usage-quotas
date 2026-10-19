#!/usr/bin/env bash
# Render the jupyterhub-usage-quotas chart and check the rendered manifests.
#
# It renders two value sets:
# - the default values, with only jupyterhub.publicUrl set
# - tests/helm/lint-and-validate-values.yaml
#
# Requires helm and yq (https://github.com/mikefarah/yq). Run it from the
# repository root:
#
#   tests/helm/test-rendered-manifests.sh
#
set -euo pipefail

CHART=helm/jupyterhub-usage-quotas
LINT_VALUES=tests/helm/lint-and-validate-values.yaml
NAMESPACE=test-namespace

failures=0

# check DESCRIPTION ACTUAL EXPECTED
check() {
    if [[ "$2" == "$3" ]]; then
        echo "ok:   $1"
    else
        echo "FAIL: $1"
        echo "      expected: $3"
        echo "      actual:   $2"
        failures=$((failures + 1))
    fi
}

# get KIND YQ_EXPRESSION, from the manifests in $MANIFESTS
get() {
    yq "select(.kind == \"$1\") | $2" <<<"$MANIFESTS"
}

# The Service and the NetworkPolicy must select the Deployment's pods.
check_selectors() {
    local pod_labels selector key
    pod_labels=$(get Deployment '.spec.template.metadata.labels')
    for selector in \
        "Deployment:.spec.selector.matchLabels" \
        "Service:.spec.selector" \
        "NetworkPolicy:.spec.podSelector.matchLabels"; do
        for key in $(get "${selector%%:*}" "${selector#*:} | keys | .[]"); do
            check "${selector%%:*} selector $key matches the pod labels" \
                "$(get "${selector%%:*}" "${selector#*:}[\"$key\"]")" \
                "$(yq ".[\"$key\"]" <<<"$pod_labels")"
        done
    done
}

container='.spec.template.spec.containers[0]'
env() {
    get Deployment "$container.env[] | select(.name == \"$1\") | .value"
}
env_secret() {
    get Deployment "$container.env[] | select(.name == \"$1\") | .valueFrom.secretKeyRef | .name + \"/\" + .key"
}

echo "### Default values (with jupyterhub.publicUrl)"
MANIFESTS=$(helm template usage-quotas "$CHART" --namespace "$NAMESPACE" \
    --set jupyterhub.publicUrl=https://hub.example.org/)

check "resource names" \
    "$(yq -N '.kind + "/" + .metadata.name' <<<"$MANIFESTS" | sort | tr '\n' ' ')" \
    "Deployment/usage-viewer NetworkPolicy/usage-viewer Secret/usage-viewer Service/usage-viewer ServiceAccount/usage-viewer "
check_selectors
check "API token from the z2jh hub Secret" \
    "$(env_secret JUPYTERHUB_API_TOKEN)" "hub/hub.services.usage-quota.apiToken"
check "no api-token key in the chart Secret" \
    "$(get Secret '.data | has("api-token")')" "false"
check "service prefix" "$(env JUPYTERHUB_SERVICE_PREFIX)" "/services/usage-quota/"
check "public hub URL" "$(env JUPYTERHUB_PUBLIC_HUB_URL)" "https://hub.example.org/hub/"
check "hub namespace is the release namespace" \
    "$(env JUPYTERHUB_USAGE_QUOTAS_HUB_NAMESPACE)" "$NAMESPACE"
check "config is an empty UsageViewer section" \
    "$(get Secret '.data["values.json"] | @base64d')" '{"UsageViewer":{}}'
check "container runs as non-root with a read-only root filesystem" \
    "$(get Deployment "$container.securityContext | (.runAsNonRoot and .readOnlyRootFilesystem)")" "true"
check "pod can access the z2jh hub" \
    "$(get Deployment '.spec.template.metadata.labels["hub.jupyter.org/network-access-hub"]')" "true"

echo
echo "### $LINT_VALUES"
MANIFESTS=$(helm template usage-quotas "$CHART" --namespace "$NAMESPACE" \
    --values "$LINT_VALUES")
fullname=usage-quotas-name-override-usage-viewer

check "resource names" \
    "$(yq -N '.kind + "/" + .metadata.name' <<<"$MANIFESTS" | sort | tr '\n' ' ')" \
    "Deployment/$fullname NetworkPolicy/$fullname Secret/$fullname Service/$fullname ServiceAccount/custom-sa "
check "name label" \
    "$(get Deployment '.spec.template.metadata.labels["app.kubernetes.io/name"]')" "name-override"
check_selectors
check "Deployment uses the ServiceAccount" \
    "$(get Deployment '.spec.template.spec.serviceAccountName')" "custom-sa"
check "API token from the chart Secret" \
    "$(env_secret JUPYTERHUB_API_TOKEN)" "$fullname/api-token"
check "api-token key in the chart Secret" \
    "$(get Secret '.data["api-token"] | @base64d')" "api-token-value"
check "explicit session secret key" \
    "$(get Secret '.data["session-secret-key"] | @base64d')" "session-secret-key"
check "OAuth client ID" "$(env JUPYTERHUB_CLIENT_ID)" "service-quota"
check "base URL" "$(env JUPYTERHUB_BASE_URL)" "/jhub/"
check "service prefix" "$(env JUPYTERHUB_SERVICE_PREFIX)" "/jhub/services/quota/"
check "OAuth callback URL" \
    "$(env JUPYTERHUB_OAUTH_CALLBACK_URL)" "/jhub/services/quota/oauth_callback"
check "public URL" "$(env JUPYTERHUB_PUBLIC_URL)" "https://hub.example.org/jhub/services/quota/"
check "public hub URL" "$(env JUPYTERHUB_PUBLIC_HUB_URL)" "https://hub.example.org/jhub/hub/"
check "readiness probe path" \
    "$(get Deployment "$container.readinessProbe.httpGet.path")" "/jhub/services/quota/health"
check "tpl in extraEnv" "$(env EXAMPLE_RELEASE_NAMESPACE)" "$NAMESPACE"
check "valueFrom in extraEnv" \
    "$(env_secret JUPYTERHUB_USAGE_QUOTAS_PROMETHEUS_USERNAME)" "prometheus-auth/username"
check "config in values.json" \
    "$(get Secret '.data["values.json"] | @base64d | from_json | .UsageViewer | .footer_note + " " + .prometheus_auth.username + " " + .hub_template_paths[0]')" \
    'Contact <a href="mailto:admin@example.org">the hub admin</a>. username /usr/local/share/jupyterhub-usage-quotas/custom-templates'
check "custom templates are mounted at the configured path" \
    "$(get Deployment "$container.volumeMounts[] | select(.name == \"custom-templates\") | .mountPath")" \
    "/usr/local/share/jupyterhub-usage-quotas/custom-templates"
check "container port" "$(get Deployment "$container.ports[0].containerPort")" "8080"
check "--port argument" \
    "$(get Deployment "$container.args[] | select(test(\"^--port=\"))")" "--port=8080"
check "Service port" "$(get Service '.spec.ports[0].port')" "8080"
check "NetworkPolicy has the built-in and the extra ingress rule" \
    "$(get NetworkPolicy '.spec.ingress | length')" "2"

echo
if [[ $failures -gt 0 ]]; then
    echo "$failures check(s) failed"
    exit 1
fi
echo "All checks passed"
