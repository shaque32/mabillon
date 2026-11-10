## 2026-11-10: Stay local for any case involving a minor and sexual conduct, signed by Arsh (#256)
- Changed: the stay-local box at setup named only child sexual abuse material. It now reads
  "This case concerns sexual material or conduct involving a minor, or someone presented as a
  minor: for example child sexual abuse material, enticement, sextortion or trafficking. This
  case then runs only on this computer. If unsure, tick it." (`core/casework/cloud.py`
  CSAM_NOTE, `ui/pages.py`). Why: enticement, sextortion and trafficking cases are mostly chat
  text, often with an officer presented as a minor, and a provider that learns of apparent CSAM,
  enticement of a minor or child sex trafficking must report it to NCMEC (18 U.S.C. 2258A), so a
  Fast run on such a case could end in a report about the defense's own evidence. The Fast
  attestation gains a last sentence, "This case does not concern sexual material or conduct
  involving a minor, or someone presented as a minor.", so a case attested under #254's text
  reads as not chosen and must choose again. The stay-local reason, the refusal of Fast on a
  marked case and the "Saved" message use the same phrase. The stored audit-log field keeps its
  name, `csam`, so a case marked under the earlier box still stays local; each new entry records
  the wider words in `csam_note`. `docs/SECURITY_PRIVACY.md` (intro and section 5, items 1 and
  2) and `docs/ARCHITECTURE.md` match. The CLAUDE.md line is proposed in `PROPOSED_CHANGES.md`.
  Also, the Fast explanation at setup (FAST_EXPLAINED) now opens with what each step sends:
  each paragraph of the government's document to propose claims, and, to test a claim, the
  claim and its paragraph, the assumption, one record and the messages around it, the case's
  app names and a group chat's member list. The earlier text left out the document's paragraphs
  and the app names (Greptile on #256), and its "Never your files" becomes "The phone
  extractions themselves and the case database never leave this computer."
  Arsh approved all six texts on 2026-11-10 19:12Z ("i approve the rest",
  plans/minor-sexual-stay-local.md).
- Where: PR #256 (merges after #254)
- Verified: make check (see PR). New tests in `tests/test_cloud.py`: the attestation and box
  texts are pinned; a marked case stays local with the exact reason and keeps the words ticked;
  a case marked under the earlier box still stays local; a case attested before the new
  sentence must choose again; the setup form shows both texts, refuses Fast on a marked case
  and saves a local choice with the new message; the report shows the new sentence; the Fast
  explanation names what each signed prompt carries, and a prompt that gains a field fails the
  test. No API calls.
- Open: the CLAUDE.md line is signed but not applied yet (`PROPOSED_CHANGES.md`). Mabillon
  does not scan for such content; the box and the attestation are the examiner's own
  statements. `docs/ONE_PAGER.md`, `docs/PILOT_ONBOARDING.md`, the `.greptile` privacy rule and
  site/ (Arsh's) still say "possibly containing CSAM" and need a separate refresh. Whether an
  excerpt sent from such a case would in fact trigger a report is a question for a lawyer; this
  is not legal advice.
- Affects: privacy (fewer cases may use Fast), customer-facing claims (setup box, attestation,
  the security and privacy doc)
- Status doc: pending: in section 4, "When Opus is used", replace "the case is not marked as
  possibly containing CSAM" with "the case is not marked as concerning sexual material or
  conduct involving a minor, or someone presented as one (CSAM, enticement, sextortion or
  trafficking)"; in section 5, the "Plan C" bullet, replace "local mode stays for cases marked
  as possibly containing CSAM and strict protective orders" with "local mode stays for cases
  marked as concerning sexual material or conduct involving a minor, and for strict protective
  orders".
