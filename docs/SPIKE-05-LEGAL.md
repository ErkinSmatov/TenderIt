# SPIKE-05: Legal Review — Automated Submission Permissibility & Kazakhstan Hosting

> **Document type:** Attorney brief + consultation tracker
>
> **PART 1** (below) is a prepared brief ready for a Kazakhstan-licensed attorney.
> **PART 2** will be populated after the consultation is complete.

---

## PART 1: ATTORNEY BRIEF

---

## Context for Attorney

TenderIt is a software service that helps Kazakhstani companies submit tender applications to goszakup.gov.kz programmatically. The technical workflow is as follows:

1. The software searches for and displays tender listings relevant to the user's business.
2. When the company director decides to submit an application, the software assembles the application documents (populating templates with the director's previously stored company data).
3. The company director personally clicks "Sign" on their screen and enters their NCALayer PIN — **this is a physical, contemporaneous act by the authorized representative of the company.** The director is not signing blindly; they have reviewed the application on-screen before clicking.
4. NCALayer (a software application required by goszakup.gov.kz and certified by the National Certification Authority of Kazakhstan) signs the document on the director's own device using the director's private key.
5. TenderIt transmits the signed document to goszakup.gov.kz via the official public API.

**Critical technical facts:**
- The private signing key (ЭЦП/EDS private key) **never leaves the director's device.** TenderIt has zero access to the private key at any point.
- The company director is **physically present and actively consents** to each submission via PIN entry. There are no scheduled or automated submissions without the director's real-time participation.
- TenderIt does not store or transmit the director's NCALayer PIN.
- TenderIt accesses goszakup.gov.kz using the official v3 GraphQL API (the same API that goszakup.gov.kz's own web portal uses), not via web scraping.

---

## Legal Questions for Attorney Consultation

### Question 1 — Automated Submission Permissibility

Does using software to programmatically call the goszakup.gov.kz API (with the company director's per-action consent via NCALayer PIN entry) constitute permissible use under:

1. **goszakup.gov.kz Terms of Service:** Specifically — does the ToS prohibit programmatic API access by third-party software? Is there a distinction between "automated submission" (director not present) and "assisted submission" (director signs each application interactively)?

2. **Kazakhstan Law on Public Procurement** (Закон Республики Казахстан от 4 декабря 2015 года No. 434-V «О государственных закупках»): Are there provisions that explicitly require submission to be performed via the goszakup.gov.kz web portal interface, or is any delivery via the official API acceptable?

3. **Regulations from:**
   - Министерство финансов Республики Казахстан (oversees public procurement regulation)
   - Агентство по защите и развитию конкуренции (competition aspects)
   - АО «Центр Электронных Финансов» (ЦЭФ) — operator of goszakup.gov.kz: any published rules on third-party integrations?

**What we need:** A written opinion confirming that "assisted programmatic submission" (director signs each document interactively) is legally equivalent to manual submission via the web portal, or identifying what specific changes to our flow would be required.

---

### Question 2 — EDS Authorization under ЗЭЦД

Under the Law on Electronic Documents and Electronic Digital Signatures (Закон Республики Казахстан от 7 января 2003 года No. 370-II «Об электронном документе и электронной цифровой подписи»):

1. Does per-action user consent — director clicks "Sign" button + enters NCALayer PIN to authorize each individual document — satisfy the authorization requirement for submitted tender documents?

2. Is there a requirement that the authorized person must **initiate** the signing session (i.e., open NCALayer themselves), as opposed to having the software initiate the WebSocket connection to NCALayer while the person subsequently confirms via PIN?

3. Are there specific certificate type requirements for tender document submission? Specifically:
   - **AUTH** certificate (used for authentication): is this sufficient for document signing?
   - **SIGNATURE** (RSA) certificate: is this the required type for document signing?
   - **GOST** (Государственный стандарт, elliptic curve): is GOST required for government procurement submissions?
   - Does goszakup.gov.kz accept all three, or only specific types?

4. What is the legal status of a document signed with a valid ЭЦП but submitted via third-party software? Is the submission legally binding to the same degree as submission via the official portal?

---

### Question 3 — Liability Framework

1. **Submission errors:** What is the liability allocation if TenderIt software submits an erroneous bid (e.g., incorrect price entered by director, wrong document attached) even though the director reviewed the application and clicked "Sign"? Does the director's NCALayer signature constitute full acceptance of liability for the application contents?

2. **Disclosure requirement:** Is there a legal requirement to disclose to goszakup.gov.kz (or the procuring organization) that the tender application was submitted via third-party software rather than the official portal? If so, what is the required disclosure mechanism?

3. **ToS violation consequence:** If goszakup.gov.kz ToS prohibits third-party API access and a bid is submitted this way — is the bid legally void? Could the company face sanctions beyond bid rejection?

4. **TenderIt's liability limitation:** What contract provisions should TenderIt's user agreement include to appropriately allocate risk between TenderIt and the company director using the software?

---

### Question 4 — Data Localization

Under the Law on Personal Data and Its Protection (Закон Республики Казахстан от 21 мая 2013 года No. 94-VI «О персональных данных и их защите», as amended in 2023, with amendments effective 8 January 2025):

1. **Which data categories require Kazakhstan-based storage?** Of the following data collected by TenderIt, which fall under the localization requirement:
   - **БИН** (Business Identification Number — 12-digit legal entity identifier)
   - **ИИН** (Individual Identification Number — 12-digit personal identifier of the company director)
   - Director's full name (ФИО)
   - Company legal address
   - Director's date of birth
   - Company phone number and email
   - Uploaded company documents (ГКП certificate, technical specifications, licenses, certificates)
   - Tender application documents (assembled by TenderIt, contain the above data)
   - Application submission logs (timestamps, IP addresses, document hashes)

2. **Definition of "processing":** Does viewing, displaying, temporarily holding in memory, and transmitting to goszakup.gov.kz constitute "processing" that triggers the localization requirement? Or does localization only apply to persistent storage (database records)?

3. **Infrastructure compliance options:**
   - Is hosting on **AWS Frankfurt** (eu-central-1) with a Kazakhstan domain (tenderit.kz) compliant, or do physical servers need to be in Kazakhstan?
   - Is a **hybrid approach** acceptable: store PII (ИИН, БИН, personal data) on Kazakhstan servers, while storing non-PII (application status, logs, notifications) outside Kazakhstan?
   - Does data physically transiting through non-KZ networks (e.g., TLS connections to a KZ-hosted server via international backbone) violate localization requirements?

4. **Penalties for non-compliance:** What are the specific sanctions under the updated 2025 law for violations of the localization requirement? Are there grace periods for new businesses?

5. **Data Controller registration:** Does TenderIt need to register as a data controller (оператор персональных данных) with any Kazakhstan authority? If so, what is the registration process and timeline?

---

### Question 5 — goszakup Partner Agreement

1. Is there a formal partner program or API usage agreement that TenderIt must sign with **АО «Центр Электронных Финансов»** (operator of goszakup.gov.kz) before providing the service commercially to paying customers?

2. The current path to goszakup.gov.kz API access is via an API token obtained by sending a letter to ecc.kz (Электронный Центр Коммерции). Is this token:
   - Sufficient for commercial use (i.e., as a service offered to multiple companies), or
   - Only valid for a single registered user/company?
   - Does commercial use require a separate commercial license or API agreement?

3. Is there any intellectual property or database right that АО «ЦЭФ» holds over the tender data published on goszakup.gov.kz that would restrict TenderIt from displaying that data to users?

4. **Revenue model clarity:** If TenderIt charges a monthly subscription fee for the service of submitting tender applications via goszakup.gov.kz API — does this create any additional legal obligations (e.g., financial services regulation, intermediary services law)?

---

## Kazakhstan Hosting Providers — Research Summary

Analysis based on publicly available information as of May 2026. Pricing should be confirmed directly with providers as it changes frequently.

---

### KazCloud (kazcloud.kz)

**Overview:** One of Kazakhstan's established cloud infrastructure providers, focused on government and enterprise clients. Claims ISO 27001 certification.

**Services offered:**
- VPS (Virtual Private Server) — Linux-based instances with SSD storage
- Dedicated servers
- Managed database services (PostgreSQL available)
- Object storage (S3-compatible)
- CDN services

**Data center locations:** Almaty, Kazakhstan (confirmed Kazakhstan-based). Claims Tier III data center infrastructure.

**Compliance certifications:**
- ISO/IEC 27001:2013 (Information Security Management) — claimed
- Compliance with Kazakhstan law on personal data localization
- Government-certified for processing state information

**Estimated pricing for TenderIt Phase 1 infrastructure:**
- PostgreSQL 16 (16GB RAM, 100GB SSD): ~35,000–50,000 KZT/month (~$70–100 USD/month) — verify directly
- Object storage (100GB, S3-compatible): ~5,000–8,000 KZT/month (~$10–16 USD/month)
- Redis instance (2GB RAM): ~8,000–12,000 KZT/month (~$16–25 USD/month)
- Estimated total: ~48,000–70,000 KZT/month (~$96–140 USD/month)

**SLA:** 99.9% uptime guarantee (claimed)

**Support:** Business hours (09:00–18:00 Almaty time), Russian/Kazakh language. Email/phone support.

**Contact:** info@kazcloud.kz | +7 (727) 313-07-07

**Notes:** Pricing not publicly listed on website — requires direct inquiry. Suited for projects needing documented Kazakhstan data residency certification for compliance purposes.

---

### Beeline Business KZ (beeline.kz/business/cloud)

**Overview:** Cloud services division of Beeline Kazakhstan (major telecom operator). Part of VEON group. Strong brand recognition among Kazakhstan enterprises.

**Services offered:**
- IaaS (virtual machines, networking, storage)
- PaaS (managed databases, Kubernetes)
- Object storage
- Colocation
- DDoS protection

**Data center locations:** Almaty and Astana, Kazakhstan. Own backbone network infrastructure across Kazakhstan.

**Compliance certifications:**
- ISO/IEC 27001 (claimed)
- Certified for Kazakhstan data localization requirements
- PCI DSS compliance available for payment-related workloads

**Estimated pricing for TenderIt Phase 1 infrastructure:**
- Virtual machine (8 vCPU, 16GB RAM, 100GB SSD): ~40,000–60,000 KZT/month (~$80–120 USD/month)
- Managed PostgreSQL: pricing requires inquiry (enterprise contract typical)
- Object storage (100GB): ~4,000–7,000 KZT/month (~$8–14 USD/month)
- Redis: typically bundled or requires inquiry
- Estimated total: ~55,000–80,000 KZT/month (~$110–160 USD/month)

**SLA:** 99.95% uptime SLA (higher tier than KazCloud — claimed)

**Support:** 24/7 NOC support, dedicated account manager for enterprise clients. Russian/Kazakh language.

**Contact:** Available via beeline.kz/business form. Enterprise sales team for larger deployments.

**Notes:** Better suited for growth stage — enterprise pricing model may be overkill for MVP. Has existing relationships with many Kazakhstan enterprises which could be a channel advantage.

---

### Kcell Cloud (kcell.kz/business)

**Overview:** Cloud/hosting division of Kcell (Kazakhstani telecom, owned by Telia). Offers business cloud services alongside mobile connectivity.

**Services offered:**
- Cloud hosting (VPS, dedicated)
- Business broadband with static IP
- Data center colocation
- IoT connectivity services

**Data center locations:** Almaty, Kazakhstan (primary). Uses own telecom infrastructure.

**Compliance certifications:**
- Kazakhstan data localization compliant (standard for KZ telcos)
- ISO certification status: verify directly with Kcell

**Estimated pricing for TenderIt Phase 1 infrastructure:**
- Cloud server (comparable to 8 vCPU/16GB): ~30,000–45,000 KZT/month (~$60–90 USD/month) — estimated, verify directly
- Object storage: pricing not prominently listed, requires inquiry
- Managed databases: limited self-service offering, likely requires dedicated server approach
- Estimated total: harder to estimate without direct inquiry

**SLA:** 99.9% uptime (claimed for business services)

**Support:** Business hours support, Russian/Kazakh language.

**Contact:** business@kcell.kz | Available via kcell.kz/business

**Notes:** Less developed managed cloud offering compared to KazCloud and Beeline. Better known for connectivity than cloud infrastructure. May be more suitable for MVP/early stage due to potentially lower cost, but managed database offering is weaker.

---

## HOSTING_RECOMMENDATION: KazCloud (kazcloud.kz)

**Preliminary recommendation** (subject to attorney's data localization opinion):

KazCloud is the recommended starting point for TenderIt's Kazakhstan infrastructure because:

1. **Purpose-built cloud provider** (not a telco's side business): More mature managed database and object storage offerings than Kcell.
2. **ISO 27001 certification**: Provides documentary evidence of data security practices, important for the goszakup.gov.kz legal compliance story.
3. **Pricing**: Likely the most competitive among the three for cloud-native workloads.
4. **Track record**: Has Kazakhstan government and enterprise clients, suggesting familiarity with compliance requirements.

**Alternative:** If Beeline's 99.95% SLA is required and budget allows (~30-50% higher cost), Beeline Business KZ is a credible alternative with stronger NOC support.

**Risk note:** This recommendation must be reviewed after the attorney's data localization opinion (Question 4). The attorney may specify certification requirements (e.g., requires specific Tier IV certification, specific government audit) that would narrow the selection.

---

## PART 2: ATTORNEY CONSULTATION STATUS

---

## Attorney Consultation Status

- **Attorney name:** [PENDING]
- **Firm:** [PENDING]
- **Bar/License number:** [PENDING — verify Kazakhstan Bar Association registration]
- **Date of initial contact:** [PENDING]
- **Date of opinion requested by:** [PENDING]
- **Date of opinion delivery:** [PENDING]
- **Format of opinion:** [PENDING — written formal opinion / informal guidance / email summary]

---

## LEGAL_STATUS: PENDING — attorney search in progress

(This line is grep-extractable by the phase gate check)

---

## Summary of Legal Findings

[To be populated after attorney consultation is complete]

Expected sections:
- Submission permissibility verdict (Question 1)
- EDS authorization compliance verdict (Question 2)
- Liability framework recommendations (Question 3)
- Data localization requirements and hosting compliance (Question 4)
- Partner agreement requirements with ЦЭФ (Question 5)

---

## Action Items from Legal Review

[To be populated after attorney consultation]

Expected items:
- Required changes to submission flow (if any)
- Data localization implementation requirements
- Partner agreement or API usage agreement to sign (if required)
- Disclosure language for user-facing Terms of Service
- Required data controller registration steps (if any)

---

## Suggested Attorney Contacts

For identifying a Kazakhstan-licensed attorney with expertise in:
- Kazakhstan IT and e-commerce law
- Public procurement law (госзакупки)
- Personal data protection law

**Recommended search channels:**
1. **Kazakhstan Bar Association** (Республиканская коллегия адвокатов) — kazbar.kz — search for IT/technology law specialists
2. **GRATA International** (gratanet.com) — international law firm with Kazakhstan office, known for IT/tech and public procurement expertise
3. **Dentons Kazakhstan** (dentons.com/en/locations/kazakhstan) — Almaty office, strong in regulatory/compliance
4. **Aequitas** (aequitas.kz) — Kazakhstan firm with technology and corporate practice
5. **McKinsey Legal** — if the question becomes EU GDPR interaction (data routed through EU infrastructure)

**Recommended approach:** Engage a firm with both IT/tech law AND public procurement law expertise, as Question 1 and Question 4 require different specializations.

---

*Document created: 2026-05-28*
*Next review: After attorney engagement confirmed*
