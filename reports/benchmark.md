# Benchmark

Conversion denominator: generated image count.

| run_id | gate | adapter | generated_images | gate_pass | render_attempts | usable_clips | conversion_rate | retry_policy | attempts | avg_retries | failure_codes |
|---|---|---|---:|---:|---:|---:|---:|---|---:|---:|---|
| demo01 | on | manual | 6 | 3 | 3 | 2 | 33.3% | retry.yaml | 0 | 0.00 |  |
| example | on | manual | 3 | 2 | 2 | 1 | 33.3% | retry.yaml | 0 | 0.00 |  |
| example_nogate | off | manual | 3 | 3 | 3 | 1 | 33.3% | retry.yaml | 1 | 0.33 | F6:1 |
