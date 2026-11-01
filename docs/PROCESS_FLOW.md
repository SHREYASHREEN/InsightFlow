# Sample Process Flow - Request lifecycle (SAMPLE)

```mermaid
flowchart LR
    A[Employee raises request] --> B[New]
    B -->|owner assigned| C[Assigned]
    C --> D[In Progress]
    D -->|needs requester input| E[Pending Info]
    E --> D
    D --> F[Resolved]
    F --> G[Closed]
    F -.reopen.-> D
```
Plain text: New -> Assigned -> In Progress -> (Pending Info <-> In Progress) -> Resolved -> Closed.
SLA clock: starts at creation (`created_at`), stops at the first Resolved/Closed (`resolved_at`).
Each arrow writes one row to `status_history`; stage durations are computed from those rows.
