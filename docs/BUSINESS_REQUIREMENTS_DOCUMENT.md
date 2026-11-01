# Business Requirements Document (BRD) - SAMPLE
*Fictional company: Northwind Service Desk. Sample document for the InsightFlow portfolio project.*

## 1. Problem statement
The IT service desk handles about 40 requests a month without a consistent way to measure SLA performance or see where tickets wait.
Managers cannot answer: "How many requests are overdue, who owns them, and which stage causes delay?"

## 2. Business objectives
| ID | Objective | Measure |
|---|---|---|
| OBJ-01 | Reduce average ticket resolution time | Average resolution hours |
| OBJ-02 | Improve SLA compliance to 90% | SLA compliance % |
| OBJ-03 | Give managers visibility of service performance | Dashboard in use weekly |
| OBJ-04 | Introduce a self-service knowledge base | (no requirements yet - deliberate gap) |

## 3. Scope
In scope: request logging, SLA deadlines, status history, dashboards, exports, requirement traceability.
Out of scope: email/chat integration, automated notifications, multi-company support, integration with real ticketing tools.

## 4. Stakeholders
| Name | Role | Influence | Interest |
|---|---|---|---|
| Asha Menon | Service Desk Manager | High | High |
| Rahul Verma | Operations Head | High | Medium |
| Neha Kulkarni | HR Business Partner | Medium | High |
| Imran Sheikh | Network Engineer | Low | Medium |

## 5. Assumptions, constraints, risks
- Assumption: SLAs run 24x7 in calendar hours.
- Constraint: prototype uses SQLite (single-site, light concurrency).
- Risk: agents forget to update status -> distorted stage durations. Mitigation: status changes are one click and logged.

## 6. Success criteria
SLA compliance and overdue counts are visible without manual spreadsheets; every approved requirement has acceptance criteria and a UAT test.
