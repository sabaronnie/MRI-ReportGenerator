#!/usr/bin/env bash
# Tear everything down to stop the bill. Deletes k8s LoadBalancers first (so AWS releases the
# ELBs), then the EKS cluster. Optionally also removes ECR repos + the samples bucket.
#   ./deployment/aws/teardown.sh            # cluster + load balancers (keeps ECR images + S3)
#   ./deployment/aws/teardown.sh --all      # also delete ECR repos + samples bucket
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"
init_env

echo "==> Deleting k8s Services (releases the AWS ELBs) + namespace"
kubectl delete -f "$HERE/../k8s/eep.yaml" --ignore-not-found
kubectl delete -f "$HERE/../k8s/frontend.yaml" --ignore-not-found || true
kubectl -n "$NAMESPACE" delete svc --all --ignore-not-found || true
sleep 20  # give the cloud provider time to delete the ELBs before the cluster goes

echo "==> Deleting EKS cluster (this stops the control-plane + node charges)"
eksctl delete cluster --name "$CLUSTER" --region "$AWS_REGION" --wait

if [ "${1:-}" = "--all" ]; then
  echo "==> Deleting ECR repos"
  for repo in mri-eep mri-measurements mri-frontend; do
    aws ecr delete-repository --repository-name "$repo" --region "$AWS_REGION" --force >/dev/null 2>&1 || true
  done
  echo "==> Emptying + deleting samples bucket"
  aws s3 rm "s3://$SAMPLES_BUCKET/" --recursive >/dev/null 2>&1 || true
  aws s3api delete-bucket --bucket "$SAMPLES_BUCKET" --region "$AWS_REGION" >/dev/null 2>&1 || true
fi
rm -f "$HERE/.eep_host"
echo "==> Teardown complete. Re-deploy any time with 01 -> 02 -> 03."
