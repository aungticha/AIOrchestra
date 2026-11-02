---
name: "database-design"
description: "Design or modify schemas, transactions, or migrations when data changes are required."
---

# database-design

1. Review existing schema and data. Identify invariants (e.g., uniqueness, totals).
2. Apply appropriate transactions and constraints to prevent race conditions and duplicate entries based on risk.
3. For migrations, specify the impact on existing data, verification methods, and a viable rollback plan. Do not delete data just to make a migration pass.
4. Create necessary indexes for performance optimization.
5. Define Primary Keys (PK) and Foreign Keys (FK) for relational databases.
6. Avoid nested subqueries in SQL; use appropriate JOINs instead.