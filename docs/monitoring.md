# Monitoring & Observability

Satisfies rubric §11 (M3): Prometheus metrics + Grafana dashboards with per-service latency
(p50/p95), error rate, throughput, and an ML-specific signal.

## Stack
Industry-standard **kube-prometheus-stack** (Prometheus Operator + Prometheus + Grafana +
node-exporter + kube-state-metrics) installed via Helm into the `monitoring` namespace.
IaC: [`deployment/monitoring/`](../deployment/monitoring/) — `values.yaml`, `servicemonitors.yaml`,
`dashboard-configmap.yaml`, `install.sh`.

```
each service exposes /metrics  ──ServiceMonitor──▶  Prometheus  ──▶  Grafana dashboard
  eep :8080/metrics                                 (operator)         (public LoadBalancer)
  measurements :8081/metrics
  reporting :8082/metrics
```

## Install / access
```bash
./deployment/monitoring/install.sh      # helm install + ServiceMonitors + dashboard, prints Grafana URL
# Grafana login: admin / mri-demo-admin   (demo only)
```
Grafana is exposed via an AWS load balancer. Prometheus is internal; inspect targets with:
`kubectl -n monitoring port-forward svc/kps-kube-prometheus-prometheus 9090` → http://localhost:9090/targets

## Metrics each service exposes
| Service | Metric | Type | Use |
|---------|--------|------|-----|
| eep | `eep_requests_total{method,path,status}` | counter | throughput, error rate |
| eep | `eep_request_duration_seconds{method,path}` | histogram | latency p50/p95 |
| measurements | `measurement_duration_seconds{measurement}` | histogram | per-component latency |
| measurements | `measurement_results_total{measurement,status}` | counter | ok/error outcomes |
| measurements | `measurement_pathology_flags_total{measurement,flag}` | counter | **ML signal** (output distribution of pathology flags) |
| reporting | `reporting_render_total{status}` | counter | render throughput/errors |
| reporting | `reporting_render_duration_seconds` | histogram | render latency |

## Dashboard "MRI-ReportGenerator — Services" (panels → PromQL)
- **EEP throughput** — `sum(rate(eep_requests_total[1m]))`
- **EEP error rate (5xx)** — `sum(rate(eep_requests_total{status=~"5.."}[5m])) / clamp_min(sum(rate(eep_requests_total[5m])),0.0001)`
- **EEP latency p50/p95** — `histogram_quantile(0.5|0.95, sum(rate(eep_request_duration_seconds_bucket[5m])) by (le))`
- **Measurements component p95** — `histogram_quantile(0.95, sum(rate(measurement_duration_seconds_bucket[5m])) by (le,measurement))`
- **Measurement outcomes** — `sum(rate(measurement_results_total[5m])) by (status)`
- **Reporting render rate & p95**
- **ML signal — pathology flags by type** — `sum(measurement_pathology_flags_total) by (flag)` — the
  distribution of pathology flags the pipeline raises; a shift here is an output-distribution / drift proxy.

## ML-specific signal (rubric requirement)
We don't run a black-box classifier, so the meaningful ML signal is the **distribution of pathology
flags** the measurement pipeline emits (`measurement_pathology_flags_total` by flag) plus the
per-component **error rate** (`measurement_results_total{status="error"}`). A sustained change in the
flag mix or error rate is the drift/anomaly indicator a reviewer would watch.

## Cost / teardown
Grafana adds one LB (~$16/mo if left up). `deployment/aws/teardown.sh` deletes the cluster (and with it
the monitoring stack). To remove just monitoring: `helm uninstall kps -n monitoring`.
