---
name: software-spec-dimensions
description: "Reference loaded by software-deep-spec and spec reviews, not for a user request: the ten dimensions a feature specification covers, with what to include in each and the level of detail expected. Consult it when writing or reviewing a feature spec."
user-invocable: false
---

# Spec dimensions

Reference material. It defines the ten dimensions every feature spec addresses and what each one is expected to say. The `software-deep-spec` skill writes a spec against it, one dimension at a time.

Two constraints from that skill apply to every dimension written here: a spec carries no file paths and no code snippets, except a prototype snippet that encodes a decision more precisely than prose; and the testing dimension is written against test seams confirmed with the owner before any dimension is drafted.

## The 10 Dimensions

### 1. Functional Requirements
**Purpose**: Define what the feature does from the user's perspective.

**Must include**:
- User stories in "As a [role], I want [action] so that [benefit]" format
- Acceptance criteria (specific, testable conditions)
- Must-have (MVP) vs nice-to-have (post-MVP) separation
- Input/output examples where applicable

**Decision points to surface**:
- Feature scope boundaries (what's explicitly NOT included)
- User role differences (does this work differently for admin vs user?)
- Priority trade-offs between competing requirements

### 2. UI/UX
**Purpose**: Define how the user interacts with the feature.

**Must include**:
- User flow description (step by step)
- Wireframe descriptions (text-based layout descriptions)
- Loading states, empty states, error states
- Accessibility requirements (keyboard nav, screen reader, color contrast)
- Responsive behavior (mobile vs desktop)

**Mark N/A when**: Pure backend feature, CLI tool, API-only service

**Decision points to surface**:
- Which existing components to reuse vs create new
- Mobile-first vs desktop-first
- Progressive disclosure vs showing everything

### 3. Data Model / Schema
**Purpose**: Define new or modified database tables, columns, and relationships.

**Must include**:
- New tables with all columns, types, constraints, defaults
- Modified existing tables (what changes)
- Indexes needed (and why)
- Relationships (foreign keys, cascading behavior)
- Migration plan (new migration file, data backfill if needed)

**Mark N/A when**: Feature uses no persistent data (pure UI, utility function)

**Decision points to surface**:
- Normalization vs denormalization trade-offs
- Soft delete vs hard delete
- UUID vs serial ID
- JSON columns vs separate tables

### 4. API Design
**Purpose**: Define the HTTP endpoints, request/response formats, and API behavior.

**Must include**:
- Endpoint paths, methods, and descriptions
- Request body/query param schemas
- Response schemas (success and error)
- Authentication requirements per endpoint
- Rate limiting considerations
- Pagination strategy (if listing endpoints)

**Mark N/A when**: No HTTP API involved (background job, DB trigger, pure frontend state)

**Decision points to surface**:
- REST vs RPC-style endpoint naming
- Optimistic vs pessimistic concurrency
- Sync vs async processing for heavy operations

### 5. Security
**Purpose**: Identify security implications and required protections.

**Must include**:
- Authentication changes (new auth flows, token changes)
- Authorization model (who can do what, RLS policies if Supabase)
- Input validation requirements (what to validate, where)
- Data privacy considerations (PII handling, GDPR)
- OWASP-relevant concerns for this specific feature

**Decision points to surface**:
- Permission model granularity (role-based vs attribute-based)
- Data retention and deletion policy
- Audit logging requirements

### 6. Scalability / Performance
**Purpose**: Anticipate load and identify performance-critical paths.

**Must include**:
- Expected load (concurrent users, requests/second, data volume)
- Performance-critical paths (what must be fast)
- Caching strategy (what to cache, invalidation)
- Background jobs (what can be async)
- What breaks at 10x and 100x scale

**Mark N/A when**: Internal tool with <10 users, prototype/MVP with known limited audience

**Decision points to surface**:
- Cache invalidation strategy
- Sync vs async processing boundaries
- Database query optimization priorities

### 7. Deployment / Infrastructure
**Purpose**: Define what's needed to deploy and operate this feature.

**Must include**:
- New environment variables needed
- New services or infrastructure (queues, caches, storage)
- Feature flag plan (gradual rollout strategy)
- Rollback plan (how to undo if things go wrong)
- Monitoring / alerting needs

**Mark N/A when**: Pure code change with no infra requirements

**Decision points to surface**:
- Feature flag vs direct deploy
- Blue-green vs canary deployment
- New service vs extending existing

### 8. Testing Strategy
**Purpose**: Define how the feature will be tested at every level.

**Must include**:
- Unit tests: what to test, key test cases
- Integration tests: which integrations to test
- E2E tests: critical user paths to automate
- Manual testing: what can't be automated and why
- Performance tests: if dimension 6 identified critical paths

**Decision points to surface**:
- Test data strategy (fixtures vs factories vs real data)
- Mock boundaries (what to mock, what to test real)
- Acceptable test coverage target

**Also record, written against the seams confirmed with the owner before drafting began**:
- What makes a good test here: external behaviour only, never implementation detail. Say what counts as external behaviour for this feature
- Which modules get tested, and at which of the confirmed seams
- Prior art: the tests already in this codebase the new ones should resemble, named by module and by the behaviour they assert, not by file path

### 9. Edge Cases / Failure Modes
**Purpose**: Enumerate what can go wrong and how to handle it.

**Must include**:
- Network failures (API down, timeout, partial response)
- Database failures (connection lost, constraint violation, deadlock)
- Concurrency issues (race conditions, double-submit)
- Invalid state (corrupted data, missing references)
- Partial failures (multi-step operations where step N fails)
- User behavior edge cases (rapid clicking, back button, multiple tabs)

**Decision points to surface**:
- Retry vs fail-fast for each failure mode
- Data consistency strategy (eventual vs strong)
- User-facing error messages (generic vs specific)

### 10. Migration / Backwards Compatibility
**Purpose**: Plan the transition from current state to new state.

**Must include**:
- Breaking changes (API, schema, behavior)
- Data migration plan (if schema changes affect existing data)
- Rollout plan (feature flag stages, percentage rollout)
- Rollback plan (how to revert safely)
- Communication plan (if breaking changes affect users/consumers)

**Mark N/A when**: Greenfield feature with no existing users/data to consider

**Decision points to surface**:
- Big bang vs gradual migration
- Backwards-compatible API changes vs new version
- Data migration timing (before deploy, during, after)

## General Guidelines

### When to Mark N/A
- The dimension genuinely doesn't apply to this feature
- Include a one-line justification: "N/A: this is a backend-only feature with no UI"
- Never write a minimal/generic section just to fill space: N/A is better

### Decision Points
- Use `[DECIDE]` markers for unresolved choices
- Include enough context for the user to make the decision
- Note which other dimensions are affected by the decision
- If you have a recommendation, state it with rationale

### Scope Management
- Clearly separate MVP from post-MVP
- Flag scope creep ("this is becoming a separate feature")
- Each dimension should be implementable in a reasonable timeframe
- If the spec is too large, recommend splitting into multiple specs

### Cross-Dimension Consistency
- Data model must support functional requirements
- API design must expose the functional requirements
- Security must cover the API endpoints
- Testing must cover the acceptance criteria
- Edge cases should reference other dimensions' failure modes
