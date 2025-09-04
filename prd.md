# Product Requirements Document (PRD)

## Project
Meeting Cost Calculator

## Objective
Provide organization-wide visibility into the cost of internal meetings by automatically annotating each Google Calendar event with its estimated cost. Drive behavior change by making the "theater of cost" visible, in order to reduce low-value meetings and free up productive time.

## Scope
- Internal meetings only (attendees with `@hginsights.com`)
- Cost shown in event description and stored in extendedProperties
- Standard hourly rate for all employees (initially)
- Company-wide rollout from Day 1

## Non-Goals
- No per-person salary calculations
- No reporting dashboards in Phase 1 (will be Phase 2)

## Assumptions
- Workspace admins will approve necessary OAuth scopes
- IT will provide Domain-Wide Delegation for the service account

## Success Metrics
- 100% of internal meetings annotated within 15 minutes
- Weekly company-wide meeting cost report available
- Meeting cost visibility leads to reduced average meeting size/duration

## Phases
1. **Phase 1 (This build)**
   - Annotate all meetings with total cost
   - Use a standard hourly rate
2. **Phase 2**
   - Governance nudges (agenda required > $1k)
   - Slack digests (weekly)
   - Rate bands by role
3. **Phase 3**
   - Hard cultural rules (recurring audits, approvals for >$X meetings)

## Risks
- Perception: “Big Brother” if not positioned properly
- Technical: Calendar API quota limits on large domains
- UX: Meeting edits must not send email spam
