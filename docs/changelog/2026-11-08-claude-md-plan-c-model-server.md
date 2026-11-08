## 2026-11-08: CLAUDE.md allows the plan C model server for every model job (#PR)
- Changed: CLAUDE.md now lets a case that opts in run its model jobs (stance labeler, AI
  reviewer, claim proposal, assumption filling and agents) on the Mabillon model server, the
  pinned DeepSeek V4.1 Flash 1017 at commit 1bae0e10 with a pinned engine. `core/llm/remote.py`
  becomes the second allowed network client in `core/`. For an ordinary case the server is the
  default choice at setup; CSAM-flagged cases and cases whose protective order does not allow it
  stay on the local model; never "offline". Each job uses one model for the whole case, and only
  filled-in prompts leave the machine. Wording signed by Arsh 2026-11-08 00:33Z ("approved A",
  option A of plans/claude-md-plan-c-diff.md in the project files).
- Where: branch claude/project-thread-fujfti-claude-md
- Verified: rules text only; `make check` passes. No code calls the model server yet.
- Open: the client (`core/llm/remote.py`), the case-setup choice and the first audited boot of
  the server (#244) are separate PRs. The reviewer, claim proposal and assumption filling have
  not been measured on DeepSeek; only stance has (hosted, 2026-11-07). Customer privacy text
  (SECURITY_PRIVACY.md, site) is a separate sign-off.
- Affects: privacy (what a case may send off the machine once the client ships); none today,
  since the code is unchanged. The client PR carries the status-doc edits.
- Status doc: no change
