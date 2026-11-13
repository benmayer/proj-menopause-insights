# GTM Sprint Report: Menopause Analysis

> Next steps after the MVP, not things already built. All audience and
> metric figures are **hypotheses to test**, not validated facts.

**MVP (Menohelp):** an agent that turns cycle data, blood test results and symptoms into one
source-grounded report with practical advice. Not diagnostic.

**Problem:** a perimenopause diagnosis in Germany comes on average 6 years after it starts.

---

## Sprint 1: Prove it's useful to a handful of real people

| | |
|---|---|
| **Goal** | Prove the report tells people something they didn't already know and would bring to a doctor |
| **Audience** | 5–8 women aged 35–50+ who already track cycles |
| **Channel** | Personal network and small women's-health communities; free 4-week pilot, one-to-one onboarding |
| **Deliverable** | Working pipeline run on each participant's exported cycle data, blood test PDF and symptom form + one personalised PDF report each + a short feedback form |
| **Metric** | ≥ 5 reports delivered; ≥ 4 of 6 rate it "useful" (4+/5); ≥ 3 say they'd share it with a doctor |

Notes: participants export their own data and consent in writing; nothing is stored beyond the pilot.

---

## Sprint 2: Test a professional channel

| | |
|---|---|
| **Goal** | Test whether practitioners will use the report to prepare consultations |
| **Audience** | 3 menopause coaches, nurses or women's-health practitioners, each with a few clients |
| **Channel** | Direct outreach and warm intros; free pilot in exchange for feedback |
| **Deliverable** | Practitioner-facing report version (adds a clinical-style summary) + upload flow so clients can submit their own export |
| **Metric** | 3 practitioners onboarded; ≥ 10 client reports generated; 2 of 3 say it saves prep time or improves consultations |

---

## Sprint 3: Test willingness to pay

| | |
|---|---|
| **Goal** | Find out whether anyone will pay, and what for |
| **Audience** | Practitioners from Sprint 2 + the most engaged Sprint 1 users |
| **Channel** | Landing page + direct follow-up to pilot participants |
| **Deliverable** | Simple pricing offer (e.g. per-report for individuals, monthly plan for practitioners) + payment link |
| **Metric** | ≥ 3 paying customers or ≥ 10 written commitments; one clear answer on which segment pays |

---

## Cross-sprint requirements
- **Licence:** the coaching material behind the advice is licensed for the demo only. Before any paid use, get a licence or replace it. Hosting and pricing are also still open.
- **Compliance:** health data is sensitive (GDPR special category in the EU). Saved data and consent come before Sprint 1 involves anyone else's data: consent form, data-deletion promise, no logging of raw data.
- **Storage:** the MVP keeps uploads in memory only (`app/api/store.py`). Before Sprint 1 users rely on it: swap in Supabase persistence with accounts, per-user access (RLS), explicit consent, retention limits and delete-on-request.
- **Positioning:** wellness insight, not diagnosis. Disclaimer on every report.
- **Key assumption to test first:** people actually want this, rather than just tracking in their app.
