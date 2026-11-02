---
name: "api-development"
description: "Create or modify APIs per contract, including input validation and error handling."
---

# api-development

1. Agree on method/path/request/response/error with API consumers before parallel work.
2. Validate inputs and permissions. Never leak stack traces or secrets to clients.
3. Test success/rejection paths and backwards compatibility for existing consumers.
4. Extract frequently used logic into `utils`.
5. Strictly separate Controller, Service, and Model layers. For version updates, create new files (e.g., `/v2`) and keep old versions (e.g., `/v1`) intact.
6. Generate a cURL script for the developed API.
7. Use streams or lambda functions for loops nested deeper than 2 levels.