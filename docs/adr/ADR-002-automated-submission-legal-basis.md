# ADR-002: Legal Basis for Automated goszakup Submission

**Status:** PENDING (awaiting SPIKE-05 attorney opinion)
**Date:** 2026-05-28
**Deciders:** TenderIt development team

---

## Context

TenderIt's core value proposition is to streamline tender submission for Kazakhstani companies. This requires:

1. **Programmatic goszakup.gov.kz API calls:** TenderIt calls the official goszakup.gov.kz v3 GraphQL API to search tenders and submit applications, rather than navigating the web portal manually.

2. **EDS signing via NCALayer:** The company director signs each application document using NCALayer (Kazakhstan's National Certification Authority Layer) running on their local machine. The director enters their PIN for each submission — it is a per-action, interactive process.

3. **Storage of company data:** TenderIt stores BIN (business identification number), IIN (director's individual identification number), personal data of the director, and company documents to auto-populate tender applications.

Without legal clearance confirming these three activities are lawful under Kazakhstan law, TenderIt cannot be launched to real company users. Legal liability exposure without this clearance could include: bid invalidation, regulatory sanctions, and civil liability for submission errors.

**The key legal question:** Is TenderIt's "assisted programmatic submission" model (director is present, reviews each application, and signs interactively) legally equivalent to manual submission via the goszakup.gov.kz web portal?

The legal questions are fully prepared in: docs/SPIKE-05-LEGAL.md (5 questions across submission permissibility, EDS authorization, liability, data localization, and partner agreements).

---

## Decision

[To be filled after attorney opinion is received — replace "PENDING" in Status with "Accepted" or "Accepted with Conditions"]

**DECISION:** [Launch without restrictions / Launch with specific consent flow / Requires formal API agreement with ЦЭФ before launch / BLOCKED — prohibited by law or ToS]

---

## Evidence

- **Link:** docs/SPIKE-05-LEGAL.md
- **Attorney name:** [PENDING]
- **Firm:** [PENDING]
- **Date of opinion:** [PENDING]
- **Opinion format:** [PENDING — written formal opinion / email summary / informal guidance]

---

## Consequences

[To be filled after attorney opinion is received]

The consequences section will address:

### If DECISION = "Launch without restrictions"
- No changes to current technical design required
- User ToS must include submission liability disclaimer (standard for SaaS)
- Data localization: must confirm Kazakhstan hosting for PII categories (see SPIKE-05-LEGAL.md)

### If DECISION = "Launch with specific consent flow"
Likely requirements:
- Explicit disclosure in onboarding that TenderIt is third-party software submitting via API
- Per-submission confirmation UI (user explicitly acknowledges each submission)
- Specific language in user agreement about liability allocation

Implementation:
- Add disclosure screen in onboarding flow (Phase 2 AUTH-01)
- Add submission confirmation modal with legal text (Phase 5 SUBM-01)
- Update user agreement template (non-code task)

### If DECISION = "Requires formal API agreement with ЦЭФ"
- Must complete partner agreement before accepting paying customers
- Technical changes: API token registration flow may change (from letter-based to formal agreement)
- Timeline risk: agreement negotiation could take weeks to months

### If DECISION = "BLOCKED"
- Fundamental pivot required: manual-assist model (help user fill forms but submit via portal UI)
- Would require Playwright automation of the goszakup.gov.kz portal UI instead of API calls
- This is an architectural rebuild of Phase 5
- Must escalate to project-level GO/NO-GO review before Phase 3 begins

---

## Related Decisions

- **ADR-001** (docs/adr/ADR-001-mpkz-integration-approach.md): MP.kz legal question (ToS compliance for API/scraping) is also covered by SPIKE-05.
- **SPIKE-05** (docs/SPIKE-05-LEGAL.md): Full attorney brief with 5 legal questions.
- **Phase 5, SUBM-01:** The NCALayer signing and submission implementation depends on this ADR's legal constraints.
- **Phase 2, AUTH-01:** If consent flow is required, auth and onboarding UI must include disclosure screens.

---

## Pending Actions

Before this ADR can be finalized (Status: Accepted):

1. **Human action required:** Identify and engage a Kazakhstan-licensed attorney with IT law and public procurement law expertise (see attorney contacts in SPIKE-05-LEGAL.md)
2. **Human action required:** Submit the attorney brief (SPIKE-05-LEGAL.md Part 1) and obtain written opinion
3. **Timeline:** Allow 2–4 weeks for attorney review; plan Phase 3 start date accordingly
4. **Update this ADR:** Fill in DECISION field and Consequences section based on opinion
5. **Phase gate:** This ADR must be in "Accepted" or "Accepted with Conditions" status before Phase 5 (EDS Signing & Submission) is launched to real users

---

## Attorney Engagement Checklist

- [ ] Attorney identified (name, firm, bar registration number)
- [ ] Initial contact made
- [ ] Attorney brief (SPIKE-05-LEGAL.md Part 1) sent to attorney
- [ ] Fee agreement signed
- [ ] Written opinion received
- [ ] Opinion reviewed and DECISION determined
- [ ] This ADR updated to Status: Accepted
- [ ] docs/SPIKE-05-LEGAL.md Part 2 populated with findings
- [ ] LEGAL_STATUS field in SPIKE-05-LEGAL.md updated to CLEARED or CONDITIONAL
