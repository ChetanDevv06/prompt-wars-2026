# LABLINK
## Software Requirements Specification (SRS)

**Document Version:** 1.0  
**Document Status:** Architecture Baseline — Proposed Freeze  
**Project:** Google Prompt Wars 2026  
**Product:** LabLink — Intelligent Laboratory Resource Management Platform  
**Specification Type:** Product, Functional, Technical and System Requirements

---

# 1. Document Purpose

This document establishes the foundational requirements, architectural decisions, technical direction and implementation standards for LabLink.

It will serve as the central reference throughout the project lifecycle and will guide:

- Product development and feature prioritisation.
- System architecture and backend implementation.
- Database design and data modelling.
- AI integration and optimisation algorithms.
- Frontend development.
- Testing, validation and performance evaluation.
- Deployment and competition submission.

All implementation decisions should be consistent with this document unless an approved change is recorded.

**Important:** This is the initial project baseline developed from the brainstorming and architectural decisions made so far. Official problem-statement requirements and competition evaluation criteria are not yet incorporated. Requirements that depend on those materials remain subject to validation.

# 2. Product Overview

## 2.1 Product Vision

LabLink is an AI-powered, campus-wide laboratory resource-sharing and intelligent allocation platform designed to connect students, faculty, departments, laboratories and institutional equipment through a unified system.

The platform aims to improve resource accessibility, laboratory utilisation, scheduling efficiency and fairness through intelligent resource discovery, project-aware scheduling and explainable allocation.

## 2.2 Core Problem

University laboratories often contain specialised equipment distributed across multiple departments.

Students may require equipment that is unavailable within their own department, while other departments may have unused resources.

Conventional booking systems generally focus on individual reservations and availability. They do not necessarily account for:

- Competing student requirements.
- Project deadlines.
- Equipment compatibility.
- Multiple resource dependencies.
- Historical resource access.
- Fair allocation.
- Cross-department coordination.

LabLink aims to address these challenges through centralised resource management and global scheduling optimisation.

## 2.3 Core Product Objectives

1. Centralise laboratory equipment discovery across departments.
2. Enable students to request resources based on project requirements.
3. Support multiple equipment requirements within a single project.
4. Optimise competing resource requests collectively.
5. Improve allocation fairness through need-aware prioritisation.
6. Reduce unused laboratory capacity.
7. Enable conditional faculty approval workflows.
8. Provide intelligent equipment alternatives.
9. Explain allocation recommendations transparently.
10. Provide administrators with resource utilisation insights.

# 3. Stakeholders and User Roles

## 3.1 Student

Primary platform user.

Responsibilities:
- Discover laboratory equipment.
- Create and manage projects.
- Define project resource requirements.
- Submit booking requests.
- Track allocation and approval status.
- View alternative recommendations.
- Manage confirmed reservations.

## 3.2 Faculty

Responsible for reviewing and managing resource access.

Responsibilities:
- Review pending booking requests.
- Approve or reject restricted-resource requests.
- Review allocation recommendations.
- Modify requests where appropriate.
- Monitor student resource usage.
- Review cross-department access requests where authorised.

## 3.3 Administrator

Responsible for institutional resource management.

Responsibilities:
- Manage users and access permissions.
- Register departments and laboratories.
- Maintain equipment inventory.
- Configure resource availability.
- Define approval policies.
- Configure allocation policies.
- Monitor system-wide utilisation and performance.

# 4. Functional Requirements

Requirements are assigned unique identifiers to make implementation, testing and traceability easier.

Priority definitions:

- **P0:** Essential functionality for the initial product.
- **P1:** Important enhancement.
- **P2:** Future extension.

These are internal engineering priorities, not official competition evaluation categories.

## 4.1 Identity and Access Management

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | The system shall support student, faculty and administrator roles. | P0 |
| FR-002 | The system shall authenticate users before accessing protected functionality. | P0 |
| FR-003 | The system shall enforce role-based access permissions. | P0 |
| FR-004 | The system shall restrict access to department-specific administrative operations. | P0 |
| FR-005 | The system shall maintain user account and profile information. | P0 |

## 4.2 Resource Registry

| ID | Requirement | Priority |
|---|---|---|
| FR-006 | Administrators shall be able to register laboratories and departments. | P0 |
| FR-007 | Administrators shall be able to register equipment. | P0 |
| FR-008 | Equipment records shall contain relevant technical specifications. | P0 |
| FR-009 | Equipment shall have availability and operational status information. | P0 |
| FR-010 | The system shall support equipment maintenance and unavailability periods. | P0 |
| FR-011 | The system shall maintain equipment compatibility information. | P1 |

## 4.3 Resource Discovery

| ID | Requirement | Priority |
|---|---|---|
| FR-012 | Students shall be able to search equipment across departments. | P0 |
| FR-013 | Students shall be able to filter equipment by category, specifications and availability. | P0 |
| FR-014 | The system shall identify compatible equipment alternatives. | P1 |
| FR-015 | The system shall support natural-language equipment discovery. | P1 |
| FR-016 | Equipment recommendations shall be grounded in registered equipment specifications. | P0 |

## 4.4 Project Management

| ID | Requirement | Priority |
|---|---|---|
| FR-017 | Students shall be able to create and manage projects. | P0 |
| FR-018 | Projects shall contain descriptions, deadlines and relevant metadata. | P0 |
| FR-019 | Students shall be able to associate multiple resource requirements with a project. | P0 |
| FR-020 | Resource requirements shall specify expected usage duration. | P0 |
| FR-021 | Projects shall support sequential and parallel resource dependencies. | P1 |
| FR-022 | Resource requirements shall support compatible alternatives. | P1 |
| FR-023 | The system shall validate project dependency graphs and reject cycles. | P0 |

## 4.5 Booking Management

| ID | Requirement | Priority |
|---|---|---|
| FR-024 | Students shall be able to submit resource booking requests. | P0 |
| FR-025 | Booking requests shall be associated with relevant projects. | P0 |
| FR-026 | Requests shall support preferred time slots and required duration. | P0 |
| FR-027 | Students shall be able to track request status. | P0 |
| FR-028 | Students shall be able to withdraw eligible pending requests. | P0 |
| FR-029 | The system shall distinguish requests, allocation recommendations, provisional holds and confirmed reservations. | P0 |

## 4.6 LIAE — LabLink Intelligent Allocation Engine

The allocation engine is the central technical component of LabLink.

| ID | Requirement | Priority |
|---|---|---|
| FR-030 | The system shall evaluate competing resource requests collectively. | P0 |
| FR-031 | The system shall enforce equipment availability constraints. | P0 |
| FR-032 | The system shall prevent overlapping reservations for exclusive equipment. | P0 |
| FR-033 | The system shall validate equipment compatibility. | P0 |
| FR-034 | The system shall account for existing confirmed reservations. | P0 |
| FR-035 | The system shall account for project dependencies. | P0 |
| FR-036 | The system shall support immediate allocation evaluation for urgent requests. | P0 |
| FR-037 | The system shall support periodic batch optimisation. | P0 |
| FR-038 | The system shall implement need-aware allocation fairness. | P0 |
| FR-039 | The system shall consider legitimate project deadlines. | P0 |
| FR-040 | The system shall consider historical resource access. | P0 |
| FR-041 | The system shall consider resource scarcity and suitable alternatives. | P1 |
| FR-042 | The system shall produce allocation recommendations and alternative feasible schedules. | P0 |
| FR-043 | The system shall retain allocation results and relevant optimisation metadata. | P0 |
| FR-044 | The system shall distinguish optimal, feasible, infeasible and inconclusive solver outcomes. | P0 |
| FR-045 | The system shall not silently modify confirmed reservations. | P0 |

## 4.7 Approval Management

| ID | Requirement | Priority |
|---|---|---|
| FR-046 | The system shall support configurable approval policies. | P0 |
| FR-047 | The system shall automatically route requests based on applicable approval rules. | P0 |
| FR-048 | Faculty shall be able to approve or reject eligible requests. | P0 |
| FR-049 | Faculty shall be able to review allocation recommendations. | P0 |
| FR-050 | Modified allocations shall undergo constraint validation again. | P0 |
| FR-051 | The system shall maintain approval history. | P0 |

## 4.8 Provisional Holds and Reservations

| ID | Requirement | Priority |
|---|---|---|
| FR-052 | The system shall create provisional holds where approval is pending and policy permits. | P0 |
| FR-053 | Provisional holds shall have configurable expiry periods. | P0 |
| FR-054 | Approved holds shall be converted into confirmed reservations. | P0 |
| FR-055 | Rejected or expired holds shall release their resources. | P0 |
| FR-056 | The system shall revalidate resource availability before reservation confirmation. | P0 |
| FR-057 | The system shall prevent concurrent booking operations from creating conflicting reservations. | P0 |

## 4.9 Reallocation Management

| ID | Requirement | Priority |
|---|---|---|
| FR-058 | The system shall identify opportunities for improving existing allocation plans. | P1 |
| FR-059 | The system shall recommend alternatives when conflicts or equipment failures occur. | P0 |
| FR-060 | The system shall not automatically change confirmed bookings. | P0 |
| FR-061 | Reallocation recommendations shall include their expected impact on affected users. | P1 |
| FR-062 | Reallocation shall require applicable consent or authorised approval before implementation. | P0 |

## 4.10 Analytics and Reporting

| ID | Requirement | Priority |
|---|---|---|
| FR-063 | Administrators shall be able to view equipment utilisation. | P1 |
| FR-064 | The system shall report resource demand and booking trends. | P1 |
| FR-065 | The system shall calculate allocation fairness metrics. | P1 |
| FR-066 | The system shall identify underutilised resources. | P1 |
| FR-067 | The system shall maintain auditable allocation history. | P0 |

## 4.11 GenAI Assistant

| ID | Requirement | Priority |
|---|---|---|
| FR-068 | The system shall interpret natural-language resource requests. | P1 |
| FR-069 | The system shall extract structured project and equipment requirements. | P1 |
| FR-070 | The system shall request clarification when essential information is missing. | P0 |
| FR-071 | The system shall explain allocation recommendations using verified system data. | P1 |
| FR-072 | The system shall not independently create confirmed reservations. | P0 |
| FR-073 | AI-generated information shall undergo validation before being used by deterministic workflows. | P0 |

# 5. Non-Functional Requirements

## 5.1 Reliability

- NFR-001: The system shall prevent conflicting confirmed reservations.
- NFR-002: Allocation and reservation operations shall be transactionally consistent.
- NFR-003: Failed background tasks shall be recoverable.
- NFR-004: Expired provisional holds shall not remain usable.
- NFR-005: Critical allocation decisions shall be auditable.

## 5.2 Performance

- NFR-006: The system shall support bounded optimisation execution.
- NFR-007: Scheduling latency shall be measured under different workload sizes.
- NFR-008: Database queries shall be designed to avoid unnecessary repeated operations.
- NFR-009: Background processing shall prevent expensive optimisation operations from blocking normal API requests.

Performance targets will be established through benchmarking.

## 5.3 Security

- NFR-010: Protected operations shall require authentication.
- NFR-011: Role-based access control shall be enforced on the backend.
- NFR-012: Sensitive configuration and API credentials shall not be committed to source control.
- NFR-013: Database access shall follow least-privilege principles.
- NFR-014: User inputs shall be validated.
- NFR-015: Administrative actions and sensitive allocation decisions shall be logged.

## 5.4 Maintainability

- NFR-016: The backend shall use modular domain boundaries.
- NFR-017: Scheduling algorithms shall be independently testable.
- NFR-018: Allocation policies shall be configurable and versioned.
- NFR-019: API contracts shall be documented.
- NFR-020: Automated tests shall cover critical business rules.

## 5.5 Scalability

- NFR-021: The system shall support increasing numbers of students, equipment records and booking requests.
- NFR-022: The scheduling engine shall support bounded execution and workload benchmarking.
- NFR-023: Background tasks shall be independently scalable where required.

## 5.6 Explainability

- NFR-024: Allocation recommendations shall contain traceable decision information.
- NFR-025: The system shall distinguish hard constraints from optimisation preferences.
- NFR-026: The system shall distinguish proven optimal solutions from feasible solutions.
- NFR-027: AI explanations shall be grounded in actual allocation results.

# 6. Final System Architecture

## 6.1 Architectural Style

LabLink shall initially follow a modular monolithic architecture.

This approach provides:
- Clear domain separation.
- Simpler development and deployment.
- Transactional database operations.
- Easier debugging and integration testing.
- Future flexibility to extract independently scalable modules.

Microservices are not required for the initial implementation.

## 6.2 Proposed Technology Stack

| Layer | Proposed Technology |
|---|---|
| Frontend | React / Next.js |
| Backend | Python + FastAPI |
| Primary database | PostgreSQL |
| Scheduling optimisation | Google OR-Tools CP-SAT |
| AI integration | Gemini API, subject to briefing and availability |
| Search | PostgreSQL full-text search and structured filtering |
| Semantic search | Embeddings, where justified |
| Caching | Redis, if required |
| Background jobs | Background worker infrastructure |
| Deployment | Google Cloud Run, subject to deployment constraints |
| Version control | Git and public GitHub repository |

These technologies represent the proposed stack, not mandatory competition requirements.

## 6.3 Backend Module Structure

The backend shall be organised into:

1. API and authentication.
2. Identity and access management.
3. Equipment registry.
4. Resource discovery.
5. Project management.
6. Booking management.
7. Scheduling and allocation intelligence.
8. Approval workflows.
9. Reservation management.
10. Analytics and reporting.
11. AI orchestration.
12. Infrastructure and persistence.

The allocation engine shall remain logically independent from GenAI and database persistence.

# 7. LIAE Optimisation Specification

## 7.1 Allocation Strategy

The system shall use a hybrid scheduling strategy:

**Immediate scheduling**
- Used for validated urgent requests.
- Evaluates current availability and competing commitments.
- Performs bounded optimisation over the affected scheduling scope.

**Batch scheduling**
- Collects eligible pending requests.
- Evaluates requests collectively.
- Generates globally optimised allocation recommendations.

Both paths shall use common constraint and fairness rules.

## 7.2 Hard Constraints

The optimiser shall enforce:

1. Equipment availability.
2. No overlapping bookings for exclusive resources.
3. Equipment compatibility.
4. Laboratory operating hours.
5. Access permissions.
6. Existing confirmed commitments.
7. Equipment capacity.
8. Project dependency validity.
9. Applicable resource restrictions.

Hard constraints shall never be traded against soft objectives.

## 7.3 Lexicographic Optimisation

The proposed optimisation hierarchy is:

| Level | Objective |
|---|---|
| L0 | Satisfy all hard constraints |
| L1 | Minimise unmet critical deadline requirements |
| L2 | Maximise need-weighted fulfilment |
| L3 | Minimise historical access imbalance |
| L4 | Maximise productive resource utilisation |
| L5 | Minimise deviation from preferred time slots |

The optimisation engine shall preserve higher-level optimal outcomes when optimising lower-level objectives.

The precise mathematical formulation, normalisation and criticality thresholds shall be established in the technical design phase.

## 7.4 Fairness Model

Fairness shall be need-aware rather than based exclusively on equal booking hours.

The model shall consider:

- Validated project requirements.
- Deadline urgency.
- Historical resource access.
- Waiting time.
- Resource scarcity.
- Availability of suitable alternatives.

Potential evaluation metrics include Jain's fairness index, Gini coefficient and request fulfilment ratios.

# 8. Project Dependency and Resource Model

Projects may contain multiple resource requirements.

Each project shall support:
- Multiple resource requirements.
- Estimated usage duration.
- Sequential dependencies.
- Parallel tasks.
- Compatible resource alternatives.
- Project deadlines.

Dependencies shall be represented using a Directed Acyclic Graph (DAG).

The scheduler shall allocate resources for their actual required usage windows rather than reserving all equipment for the entire project duration.

# 9. Approval and Reservation Lifecycle

The system shall distinguish the following states:

1. PENDING
2. ALLOCATED
3. PROVISIONALLY_HELD
4. CONFIRMED
5. REJECTED
6. EXPIRED
7. RELEASED
8. CANCELLED

A provisional hold shall temporarily protect the resource while awaiting approval.

Holds shall have expiry timestamps and policy-controlled extensions.

Confirmation shall require:
- Valid approval where applicable.
- Current resource availability.
- Valid reservation constraints.
- Successful transactional commit.

# 10. Reallocation Policy

Existing confirmed bookings shall be treated as protected commitments.

The system may identify and recommend improved allocations but shall not silently modify existing confirmed reservations.

Reallocation shall follow:

1. Conflict identification.
2. Alternative generation.
3. Impact analysis.
4. Recommendation.
5. Required consent or authorised approval.
6. Constraint revalidation.
7. Transactional confirmation.

Voluntary cancellation shall release the associated reservation independently of the reallocation process.

# 11. Database Requirements

PostgreSQL shall serve as the primary transactional database.

The initial conceptual data model shall include:

**Identity**
- users
- roles
- user_permissions

**Organisation**
- departments
- laboratories

**Equipment**
- equipment
- equipment_specs
- equipment_compatibilities
- equipment_schedules
- maintenance_windows

**Projects**
- projects
- project_stages
- project_dependencies
- project_resource_requirements
- requirement_alternatives

**Booking**
- booking_requests
- booking_request_items

**Optimisation**
- allocation_runs
- allocation_candidates
- allocation_results

**Approval**
- approval_policies
- approval_requests
- approval_decisions

**Reservations**
- reservations
- reservation_items
- reservation_history

**Intelligence and analytics**
- ai_interactions
- recommendation_explanations
- resource_usage_records
- fairness_metrics
- audit_logs

The final ER diagram shall establish primary keys, foreign keys, junction tables, uniqueness constraints and temporal exclusion constraints.

# 12. Testing and Validation Requirements

The system shall be evaluated through five testing layers.

## 12.1 Unit Testing
- Business rules.
- Compatibility calculations.
- Fairness functions.
- Scheduling constraints.
- Dependency validation.

## 12.2 Integration Testing
- Database operations.
- API workflows.
- Booking transactions.
- Approval workflows.
- Provisional hold lifecycle.

## 12.3 Optimisation Testing
- Competing booking requests.
- Multi-resource projects.
- Lexicographic objective ordering.
- Solver statuses.
- Infeasible scheduling scenarios.

## 12.4 Adversarial Testing
- False or exaggerated deadlines.
- Invalid equipment specifications.
- Dependency cycles.
- Simultaneous booking attempts.
- Expired holds.
- Unauthorised approvals.

## 12.5 Performance Testing

The system shall be benchmarked against:
- First-come-first-served allocation.
- Priority-based greedy scheduling.
- Global constraint-based optimisation.

Metrics shall include:
- Hard constraint violation rate.
- Request fulfilment.
- Deadline satisfaction.
- Fairness.
- Equipment utilisation.
- Scheduling latency.
- Optimisation runtime.

**Mandatory correctness target:** Zero hard-constraint violations and zero conflicting confirmed reservations in the defined test scenarios.

# 13. Known Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Inaccurate equipment records | Validated equipment registry |
| AI hallucinations | Structured schemas and deterministic validation |
| Scheduling scalability | Solver time limits and decomposition |
| Unfair prioritisation | Need-aware fairness metrics |
| Hold starvation | Expiry and extension policies |
| Priority manipulation | Verified deadlines and project validation |
| Concurrent allocations | Versioned snapshots and transactional confirmation |
| Dependency complexity | DAG validation and bounded optimisation |
| Booking disruption | Protected confirmed reservations |
| Poor alternatives | Specification-based compatibility checks |
| Incomplete auditability | Versioned policies and decision records |

# 14. Development Roadmap

The proposed implementation sequence is:

| Phase | Deliverable |
|---|---|
| P1 | Domain modelling and database foundation |
| P2 | Identity and resource registry |
| P3 | Equipment discovery and compatibility |
| P4 | Project and dependency management |
| P5 | Booking request management |
| P6 | Hard constraint validation |
| P7 | LIAE global optimisation |
| P8 | Need-aware fairness |
| P9 | Approval and provisional hold workflows |
| P10 | GenAI integration |
| P11 | Student, faculty and admin interfaces |
| P12 | Testing and benchmarking |
| P13 | Deployment and final submission |

The implementation order may be adjusted after reviewing the official problem statement and evaluation criteria.

# 15. Competition Submission Constraints

The following constraints have been communicated in the competition resources provided so far:

1. Maximum of two submission attempts.
2. GitHub repository must be public.
3. Repository size must be below 10 MB.
4. Repository must contain only one branch.
5. Code shall be developed through Google Antigravity.
6. Git shall be configured for version control.
7. Submission requires the public GitHub repository link.

These are recorded as competition-provided constraints and shall be revalidated against the final official briefing.

# 16. Development Environment and Engineering Standards

Before implementation:

- Configure ECC/Kilo Code agent workflows.
- Configure project-specific agent instructions.
- Initialise Graphify for repository understanding.
- Establish coding conventions and development guidelines.
- Establish automated testing and linting.
- Configure Git and the required single-branch workflow.
- Maintain a clean repository structure.
- Keep secrets and local environment files out of version control.

All AI coding agents shall follow this specification and shall not independently redefine core architectural decisions.

# 17. Open Decisions and Pending Validation

The following matters are deliberately not considered frozen:

| ID | Pending item | Required input |
|---|---|---|
| O-01 | Official problem-statement requirements | Complete PS |
| O-02 | Competition evaluation weights | Official briefing |
| O-03 | Required application features | Official PS |
| O-04 | Exact allocation objective formulation | Technical modelling |
| O-05 | Fairness thresholds and criticality rules | Benchmarking |
| O-06 | Dataset and equipment assumptions | PS and implementation research |
| O-07 | Deployment requirements | Competition instructions |
| O-08 | Final technology stack | Technical feasibility review |
| O-09 | Performance targets | Benchmarking |
| O-10 | Final MVP scope | Evaluation criteria |

No unverified assumption shall be represented as an official competition requirement.

# 18. Change Management and Version Control

This document shall be treated as the primary requirements reference.

Changes shall follow these principles:

1. Every requirement shall have a unique identifier.
2. Changes shall be documented.
3. Architectural changes shall include a justification.
4. New features shall be assessed against project scope.
5. Official problem-statement requirements shall take precedence over conflicting assumptions in this initial specification.
6. Existing decisions shall not be silently overwritten.
7. Updated specifications shall receive a new version number.

Suggested versioning:

- **v1.0:** Initial architecture and requirements baseline.
- **v1.1:** Official PS and evaluation criteria incorporated.
- **v1.2:** Technical requirements and mathematical model refined.
- **v2.0:** Major approved scope or architecture changes.

# 19. Initial Acceptance Criteria

The initial product baseline shall be considered technically validated when:

- Users can authenticate and access authorised functionality.
- Administrators can manage equipment and laboratories.
- Students can discover compatible equipment.
- Projects can contain multiple resource requirements.
- Project dependencies are validated.
- Students can submit booking requests.
- The scheduling engine can evaluate competing requests.
- Hard constraints are enforced.
- Need-aware fairness is evaluated.
- Lexicographic optimisation produces traceable results.
- Approval policies are enforced.
- Provisional holds expire correctly.
- Confirmed reservations cannot be double-booked.
- Reallocation recommendations do not silently change existing bookings.
- GenAI outputs undergo deterministic validation.
- The core system passes its defined automated test scenarios.

Final acceptance criteria shall be reconciled with the official competition requirements.

---

# 20. Final Document Status

**LabLink SRS v1.0 — Initial Architecture Baseline**

This document establishes the product vision, proposed system boundaries, functional requirements, non-functional requirements, scheduling principles, AI integration strategy, database direction, security expectations, testing strategy and development roadmap.

It is the primary reference for subsequent project planning and implementation.

**Freeze policy:**

The architectural decisions established through brainstorming are accepted as the initial baseline. The document is not yet the final competition-compliant specification. The official problem statement and evaluation briefing must be incorporated before the requirements baseline is fully frozen for implementation.

**Guiding engineering principle:**

LabLink must produce resource-allocation decisions that are feasible, fair, explainable, auditable and transactionally reliable. AI should improve the quality of interaction and interpretation without replacing deterministic validation and optimisation.

---

**END OF DOCUMENT**