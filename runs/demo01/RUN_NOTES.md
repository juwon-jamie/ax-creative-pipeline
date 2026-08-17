# demo01 — first real-media pass (2026-08-17)

- Brief: `briefs/campaign_01.yaml` (3 scenes), k=2 images per scene → 6 images.
- Image model: text-to-image, 9:16, 1k. Video model: image-to-video, 5 s, 9:16, 720p. Vendors abstracted; see adapters.
- Cost: 6 × 2 + 3 × 17.5 = 64.5 credits.

## What the gate caught (real, not staged)
3 of 6 images came back as **3-panel storyboards**: the scene card wording "Start state … End state …" was rendered by the image model as a triptych. Those frames are not video-ready (a video model would animate a collage). Gate rejected them (`judgments/gate_manual.csv`).
→ Learning-loop action: the image prompt template must add "single continuous frame, no panels, no collage" and move start/end-state wording into the *video* prompt only. (Tracked as a retry-policy prompt adjustment.)

## Result
| generated_images | gate_pass | render_attempts | technical_success | usable_clips | conversion (usable / generated) |
|---:|---:|---:|---:|---:|---:|
| 6 | 3 | 3 | 3 | 2 | 33.3% |

- clip_01 texture_drop: USABLE
- clip_02 bottle_turn (clear ampoule): NOT_USABLE — bottle does not turn, only a highlight arc moves (P1/P5)
- clip_03 bottle_turn (frosted): USABLE with a brand-cue note (frosted vs. clear glass)

Denominator is generated images, not render attempts — same definition as `criteria/usability_v1.md`.
