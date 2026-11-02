# Development

Use only the roles needed for the task. Follow RULES.md and project instructions.

## Roles
- tech-lead-architect: Analyze requirements, design the system, define acceptance criteria, and assign work.
- frontend-developer: Build UI, interactions, and API integration.
- backend-developer: Build APIs, databases, business logic, authentication, and access controls.
- code-reviewer: Check correctness, security, data integrity, and maintainability before QA.
- qa-test-engineer: Verify acceptance criteria and relevant regressions after review passes.
- ui-ux-designer: Use for new projects/pages or significant UI/flow changes. Skip minor button, text, or layout changes.
- devops-engineer: Only when the user explicitly requests pipeline/CI/CD work.
- technical-writer: Only when the user explicitly requests documentation.


## Constraints
- Do not start pipeline or documentation work without an explicit request.
- Never assume User Accept; reuse existing approval only when it covers the same scope.
- Start automatic execution from the Dashboard Workflow menu. The controller owns routing, User Accept, review/QA retries, and commit/push; these files define role scope only.
