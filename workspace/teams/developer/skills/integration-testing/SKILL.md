---
name: "integration-testing"
description: "Verify system connections (e.g., Frontend/API/Database) along the modified paths."
---

# integration-testing

1. Verify boundaries and contracts using actual connected components when possible.
2. Test both outputs and critical side effects, such as data persistence, prevention of duplicate transactions, and error propagation.
3. If stubs/mocks are required, explicitly state what they cannot verify.