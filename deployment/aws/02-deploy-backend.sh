#!/usr/bin/env bash
# Phase 2 — build + push the measurements IEP and the EEP, deploy them, wait for the EEP's
# public load balancer, and print its URL (needed by phase 3 for the frontend build).
#   ./deployment/aws/02-deploy-backend.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"
init_env
ecr_login

echo "==> Building + pushing backend images (linux/amd64 for EKS nodes)"
docker build --platform linux/amd64 \
  -f "$REPO_ROOT/deployment/docker/measurements.Dockerfile" \
  -t "$ECR_REGISTRY/mri-measurements:$IMAGE_TAG" "$REPO_ROOT"
docker push "$ECR_REGISTRY/mri-measurements:$IMAGE_TAG"

docker build --platform linux/amd64 \
  -f "$REPO_ROOT/deployment/docker/eep.Dockerfile" \
  -t "$ECR_REGISTRY/mri-eep:$IMAGE_TAG" "$REPO_ROOT"
docker push "$ECR_REGISTRY/mri-eep:$IMAGE_TAG"

echo "==> Applying measurements + eep manifests"
# CORS origin is unknown until the frontend LB exists; start permissive-but-explicit and let
# phase 3 patch it to the real frontend origin.
export FRONTEND_ORIGIN="http://localhost:3000"
apply_template "$HERE/../k8s/measurements.yaml"
apply_template "$HERE/../k8s/eep.yaml"

echo "==> Waiting for rollouts"
kubectl -n "$NAMESPACE" rollout status deploy/measurements --timeout=180s
kubectl -n "$NAMESPACE" rollout status deploy/eep --timeout=180s

echo "==> Waiting for the EEP load balancer hostname (can take 2-4 min)"
for i in $(seq 1 40); do
  EEP_HOST="$(kubectl -n "$NAMESPACE" get svc eep -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)"
  [ -n "$EEP_HOST" ] && break
  sleep 15
done
[ -n "${EEP_HOST:-}" ] || { echo "ERROR: EEP load balancer not ready"; exit 1; }

echo ""
echo "EEP public URL:  http://$EEP_HOST"
echo "  (DNS may take a few minutes to resolve, then: curl http://$EEP_HOST/healthz )"
echo "$EEP_HOST" > "$HERE/.eep_host"
echo "==> Backend deployed. Next: ./deployment/aws/03-deploy-frontend.sh"
