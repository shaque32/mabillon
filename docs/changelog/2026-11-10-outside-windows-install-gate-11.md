## 2026-11-10: Gate 11 met: an outside Windows install of the signed build
- Changed: `docs/PILOT_GATES.md` marks gate 11 (outside install test) met and the count goes from
  14 to 15 of 19. One person outside the project downloaded the signed
  `Mabillon-Setup-0.0.1+9c4e8b3.exe` (main build run 42430786224, 2026-11-08) from a 7-day private
  R2 link made with `tools/pilot_link.py`, checked its SHA-256 and the Shayan Haque signature,
  installed it with the model download unticked and opened the demo in its own window. Arsh
  reported it on 2026-11-10 and accepted it as meeting the gate.
- Where: branch claude/project-thread-s0yxae
- Verified: reported by Arsh in the Windows pilots thread (2026-11-10, "windows test worked",
  "yes all good"). The tester's own written reply is not in the repo, and nobody on the project
  saw the run. This was the first real installer in the R2 bucket (it held only a 48-byte object
  before 2026-11-08).
- Open: narrower than the gate's wording, accepted by Arsh as is: Windows rather than a Mac, a short
  step message from Arsh rather than `docs/PILOT_ONBOARDING.md` alone, and no case opened and no
  model run. No outside Mac install has been done. Windows NVIDIA speed and repeatability (gate 9)
  are still unmeasured.
- Affects: customer-facing claims (pilot readiness count)
- Status doc: pending: in section 11, change "14 of 19 met (" to "15 of 19 met (gate 11, an
  outside Windows install of the signed main build `9c4e8b3` that Arsh accepted on 2026-11-10;"
  and replace "Nobody outside the project has tried the onboarding kit yet (gate 11)." with "One
  person outside the project installed the signed Windows build and opened the demo (gate 11,
  accepted by Arsh 2026-11-10); nobody outside has opened a case or followed the onboarding kit
  alone."
