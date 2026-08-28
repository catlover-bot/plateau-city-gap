# Product permissions

Authorization is additive across active roles and is verified at the endpoint. The UI
uses the same matrix only to present relevant navigation.

| Capability | Viewer | Analyst | Planner | Field Staff | Data Manager | Administrator |
| --- | --- | --- | --- | --- | --- | --- |
| View city/data/analysis/evidence | Yes | Yes | Yes | Yes | Yes | Yes |
| Create/triage Finding | No | Yes | Yes | No | No | Yes |
| Create/update Investigation | No | Yes | Yes | No | No | Yes |
| Draft/run analysis or scenario | No | Yes | Yes | No | No | Yes |
| Request/complete Review | No | No | Yes | No | No | Yes |
| Field observation/offline sync | No | No | Yes | Yes | No | Yes |
| Human Decision Record | No | No | Yes | No | No | Yes |
| Register/validate/promote dataset | No | No | No | No | Yes | Yes |
| View job operations | No | No | No | No | Yes | Yes |
| Retry/cancel job | No | No | No | No | No | Yes |
| Read immutable audit | No | No | No | No | No | Yes |
| Manage organization/city | No | No | No | No | No | Yes |

Field Staff can see the contextual data needed for an assigned visit but cannot review
or decide a case. Data Manager can inspect service jobs but cannot mutate them. A
Decision Record requires Planner or Administrator and reviewed evidence; there is no
optimizer or chatbot role.

The executable source of truth is `ROLE_PERMISSIONS` in
`backend/citygap_platform/security/auth.py`.
