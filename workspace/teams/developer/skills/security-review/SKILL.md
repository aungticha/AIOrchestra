---
name: "security-review"
description: "Review security risks in changed code and trust boundaries; do not automatically audit the entire system."
---

# Security Review

1. Identify trust boundaries and sensitive data in the diff: inputs, paths, permissions, and secrets.
2. Check relevant execution paths for unauthorized access, injection, path traversal, and data leaks.
3. Report findings with triggers, impact, and suggested fixes. Separate confirmed issues from assumptions.
4. Reject mock behavior or hardcoded `|| true` / `&& false` used to bypass validation, authorization, or real execution.
5. Prevent secrets from leaking into source code, logs, responses, reports, or commits.