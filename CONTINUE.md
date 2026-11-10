Continue the repo-reaper project. Sessions share no memory: AGENTS.md (spec, phase plan,
session protocol) and HANDOFF.md (current state) are the memory. Read both, then follow
the Session protocol in AGENTS.md exactly: do the Start steps, work only on the phase it
selects, and finish with all End steps (tests, tick, rewrite HANDOFF.md, commit). Use the
conda env `repo-reaper` (create it from environment.yml if it's missing). Do not start
the next phase.
