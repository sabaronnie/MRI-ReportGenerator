#!/usr/bin/env bash
# Phase 3 — bake the EEP's public URL into the frontend image, deploy it, then patch the EEP's
# CORS to allow the frontend origin. Two-phase because NEXT_PUBLIC_* is inlined at build time.
#   ./deployment/aws/03-deploy-frontend.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"
init_env
ecr_login

EEP_HOST="${EEP_HOST:-$(cat "$HERE/.eep_host" 2>/dev/null || true)}"
[ -n "$EEP_HOST" ] || { echo "ERROR: run 02-deploy-backend.sh first (no EEP host)"; exit 1; }
EEP_URL="http://$EEP_HOST"
echo "==> EEP URL = $EEP_URL"

[ -d "$FRONTEND_DIR" ] || { echo "ERROR: frontend not found at $FRONTEND_DIR (set FRONTEND_DIR)"; exit 1; }

echo "==> Building + pushing frontend image (live mode, EEP URL baked in)"
docker build --platform linux/amd64 \
  --build-arg NEXT_PUBLIC_API_MODE=live \
  --build-arg NEXT_PUBLIC_EEP_URL="$EEP_URL" \
  -t "$ECR_REGISTRY/mri-frontend:$IMAGE_TAG" "$FRONTEND_DIR"
docker push "$ECR_REGISTRY/mri-frontend:$IMAGE_TAG"

echo "==> Applying frontend manifest"
apply_template "$HERE/../k8s/frontend.yaml"
kubectl -n "$NAMESPACE" rollout status deploy/frontend --timeout=180s

echo "==> Waiting for the frontend load balancer hostname"
for i in $(seq 1 40); do
  FE_HOST="$(kubectl -n "$NAMESPACE" get svc frontend -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)"
  [ -n "$FE_HOST" ] && break
  sleep 15
done
[ -n "${FE_HOST:-}" ] || { echo "ERROR: frontend load balancer not ready"; exit 1; }
FE_URL="http://$FE_HOST"

echo "==> Patching EEP CORS to allow the frontend origin ($FE_URL) and restarting it"
kubectl -n "$NAMESPACE" set env deploy/eep "EEP_ALLOWED_ORIGINS=$FE_URL"
kubectl -n "$NAMESPACE" rollout status deploy/eep --timeout=180s

echo ""
echo "================ DEPLOYED ================"
echo "  Frontend (open this):  $FE_URL"
echo "  EEP API:               $EEP_URL        (try $EEP_URL/docs , $EEP_URL/healthz)"
echo "  EEP metrics:           $EEP_URL/metrics"
echo "========================================="
echo "  DNS for new ELBs can take a few minutes to resolve."
