---
name: "regression-testing"
description: "Check impacts from diffs or bug fixes. Do not rerun tests without justification."
---

# regression-testing

1. Select existing paths that share code or data with the modified components.
2. After fixing a bug, verify the previously failing scenario and affected adjacent areas.
3. Once tests pass and there are no new changes, forward the results. Do not unnecessarily expand the test suite if there are no pending risks.
4. Write Selenium, Cypress, or Robot scripts for every test, and re-run existing automated tests. Choose appropriate tools for new projects, but strictly use the existing automation tools for established projects.
5. Notify developers of any failing automated test cases if the error is outside the scope of the current change. If the error is within scope, update and fix the affected test case.