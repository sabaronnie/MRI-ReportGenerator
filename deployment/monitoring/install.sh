#!/usr/bin/env bash
# Install Prometheus + Grafana (kube-prometheus-stack) on the EKS cluster, wire it to scrape our
# services, load the custom dashboard, and expose Grafana publicly.
#   ./deployment/monitoring/install.sh
# Prereqs: cluster up (deployment/aws/01-provision.sh) + kubeconfig pointing at it.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> [1/5] Helm repo"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update prometheus-community >/dev/null

echo "==> [2/5] Install kube-prometheus-stack (namespace: monitoring)"
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install kps prometheus-community/kube-prometheus-stack \
  --namespace monitoring -f "$HERE/values.yaml" --wait --timeout 12m

echo "==> [3/5] Name the app metrics ports (idempotent) so ServiceMonitors can target them"
kubectl -n mri patch svc measurements -p '{"spec":{"ports":[{"name":"http","port":8081,"targetPort":8081}]}}' >/dev/null 2>&1 || true
kubectl -n mri patch svc reporting    -p '{"spec":{"ports":[{"name":"http","port":8082,"targetPort":8082}]}}' >/dev/null 2>&1 || true

echo "==> [4/5] Apply ServiceMonitors + custom dashboard"
kubectl apply -f "$HERE/servicemonitors.yaml"
kubectl apply -f "$HERE/dashboard-configmap.yaml"

echo "==> [5/5] Wait for the Grafana load balancer"
for i in $(seq 1 40); do
  GF_HOST="$(kubectl -n monitoring get svc kps-grafana -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)"
  [ -n "$GF_HOST" ] && break
  sleep 15
done

echo ""
echo "================ MONITORING UP ================"
echo "  Grafana:  http://${GF_HOST:-<pending>}"
echo "  login:    admin / mri-demo-admin"
echo "  dashboard: 'MRI-ReportGenerator — Services'  (also has the built-in k8s/cluster dashboards)"
echo "  Prometheus targets: kubectl -n monitoring port-forward svc/kps-prometheus 9090 -> http://localhost:9090/targets"
echo "==============================================="
echo "  ELB DNS can take a few minutes to resolve."
