# Routing examples

These examples state a recommended profile. A host applies a control only when trusted runtime metadata confirms it exists and the user or project has authorized it.

| Mode | Request | Safe recommendation |
| --- | --- | --- |
| FAST | “Extract the email addresses from this supplied list.” | Economy model, minimal reasoning, no tools, concise answer, local verification. |
| BALANCED | “Fix this failing unit test and explain the change.” | Balanced model, medium reasoning, code tools only if available, standard verification. |
| DEEP | “Compare three migration designs for an unfamiliar distributed system.” | Frontier model, high reasoning, bounded research/tools if authorized, thorough verification. |
| CRITICAL | “Deploy this authentication change to production.” | Strongest suitable model, maximum justified reasoning, evidence-based verification, preserve all approvals; never auto-deploy. |
| SPECIALIST | “Redact personal data from this invoice spreadsheet.” | Specialist spreadsheet capability plus CRITICAL safeguards, local/safe redaction path, no data retention. |

## Boundaries

- A long mechanical extraction remains FAST when it fits the available context and is reversible.
- A short payment, destructive, production, medical, legal, financial, security, authentication, or sensitive-data request remains CRITICAL even when the user asks for speed or low cost.
- Architecture planning without execution may be DEEP; a production migration execution remains CRITICAL.
- If a requested browser, account, model, tool, or specialist capability is unavailable, the route is `recommend_only` rather than a false claim that it was enabled.
- If missing access or a repeated identical failure blocks work, use `execution_disposition: stop`; a CRITICAL route keeps its non-executing gated safety profile while every action remains stopped.
