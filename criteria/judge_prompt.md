You are scoring one short-form product clip against criteria/usability_v1.md.

Return only JSON with this schema:

{
  "clip_id": "string",
  "verdict": "USABLE or NOT_USABLE",
  "fail_codes": ["F1" ],
  "pass_fail_codes": ["P1" ],
  "p7_reason": "string",
  "reason": "string"
}

Use F1-F7 for immediate rejection defects. Use P1-P7 only when a required pass
condition is missing. If verdict is USABLE, all code arrays must be empty.
