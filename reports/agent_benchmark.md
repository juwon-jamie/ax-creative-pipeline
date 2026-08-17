# Agent Benchmark

No-media seeded benchmark: three briefs crossed with no-gate, gate, and gate+retry policies.

| run_id | brief | policy | generated_images | gate_pass | render_attempts | usable_clips | conversion_rate | attempts | avg_retries | cost_units | failure_codes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| bench_easy_no_gate | easy | no_gate | 3 | 3 | 3 | 2 | 66.7% | 0 | 0.00 | 1.05 | F5:1 |
| bench_easy_gate | easy | gate | 3 | 3 | 3 | 2 | 66.7% | 0 | 0.00 | 1.05 | F5:1 |
| bench_easy_gate_retry | easy | gate_retry | 3 | 3 | 3 | 3 | 100.0% | 1 | 0.33 | 1.10 |  |
| bench_normal_no_gate | normal | no_gate | 3 | 3 | 3 | 1 | 33.3% | 0 | 0.00 | 1.05 | F4:1, F5:1 |
| bench_normal_gate | normal | gate | 3 | 3 | 3 | 1 | 33.3% | 0 | 0.00 | 1.05 | F4:1, F5:1 |
| bench_normal_gate_retry | normal | gate_retry | 3 | 3 | 3 | 2 | 66.7% | 1 | 0.33 | 1.10 | F5:1 |
| bench_hard_no_gate | hard | no_gate | 3 | 3 | 3 | 0 | 0.0% | 0 | 0.00 | 1.05 | F1:1, F4:1, F6:1 |
| bench_hard_gate | hard | gate | 3 | 2 | 2 | 0 | 0.0% | 0 | 0.00 | 0.80 | F1:1, F4:1 |
| bench_hard_gate_retry | hard | gate_retry | 3 | 2 | 2 | 1 | 33.3% | 1 | 0.33 | 0.85 | F1:1 |
