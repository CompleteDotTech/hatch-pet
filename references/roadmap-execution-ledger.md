# Hatch Pet roadmap execution ledger

Snapshot: 2026-10-23, default branch `79958045b794c77ddb726002268bb3bbf9d4f6ad`.
Canonical repository: CompleteTech-Skills/hatch-pet (1425032192); the original CompleteDotTech URL redirects here.

The complete paginated capture contains 180 roadmap issues, 168 native parent edges, 200 native blocked-by edges and 35 comments. All parent bodies, continuations/addenda, child bodies and discussions were inspected. Exact source and issue evidence: Actions run 39985774328, artifact 12515721731 (`hatch-pet-roadmap-capture`). This is a timestamped, nontransactional snapshot; refresh affected issues and branch heads before acting. The complete original issue text remains authoritative. No checklist is reduced by this ledger.

## Execution and acceptance policy

The table records every roadmap issue. Numbers in Parent/Prerequisites refer to native issue relationships. `blocked` means an explicit unmerged prerequisite or unfinished required child prevents that issue's acceptance; it does not mean the engineering task is too difficult. Independent ready work continues. Parent rows aggregate all their native children and their own original acceptance gates. Only #112 was already merged/closed at capture time. No other issue is complete merely because reusable code or an open PR exists.

For each row, remaining acceptance criteria are the complete unchecked tasks and required validation in that issue, plus its cited parent sections/continuations, except where an explicit verified completion entry below supersedes this initial state. Tests/evidence are defined by the evidence profile and the issue-specific checklist. Unknown implementation coverage is not a missing-capability claim.

Evidence profiles:
- **M — implementation work:** no complete implementation of this issue has been verified. Reuse the existing `rig_*` geometry, skeleton, animation, glTF, Blender and browser authorities and existing production acquisition, ownership, provenance, archive and review utilities. Inspect the actual applicable code before extending it. Require strict schema/runtime parity, negative/boundary tests, real CLI/API behavior, relevant 2D regressions, and the exact artifact/backend/persistence/recovery/security demonstrations required by the linked issue. Do not create parallel registries, renderers or job/review stores.
- **R — existing rig implementation:** `scripts/rig_*.py`, `profiles/rig*.schema.json`, `rig-templates/`, `assets/rig-*`, and `tests/test_rig_*.py` provide actual geometry, binding, FK/IK, animation, export, preview and operations. This is partial reusable coverage, not proof of all #51–#58 requirements. Require the issue's specific anatomy/import/correction/deformation/contact/retarget/native/browser/package evidence and preserve all legacy interfaces. #52 has separately claimed correction-validation work (#201); do not duplicate it.
- **A — baseline audit:** review the existing PR's audit, commands, immutable source references and results against actual code/payloads. Complete only the bounded audit issue; downstream implementation and parent acceptance remain open.

Branch/worktree ownership:
- PR #200 / #51: `agent/issue-51-rig-contracts-36752e25`, head `be3bc294d89a94c2094b88becd4fdc671e7a0608`; reviewer worktree `/mnt/data/hatch-pr200`. Independent engineering review and current-head CI are present; ordinary merge and post-merge verification remain.
- PR #192 / #23: `agent/issue-23-director-baseline-20261022`, head `6e3d0dded29f523563502dab1c4db9a4c08ef00b`.
- PR #193 / #166: `agent/issue-166-physics-baseline-36752e25`, head `6951b198f6bab4c89fd9bf0ce848b336d6ae0308`.
- PR #196 / #137: `agent/issue-137-asset-library-baseline-2a0543d`, head `401ac372b967cdb336e315bbc40fc6913ccf6758`.
- #52 / #201: prior session owns `agent/issue-201-correction-validation-36752e25`; no competing implementation is assigned here.
- Unclaimed rows have no implementation branch yet. The next new implementation target is #43 after the reviewed #51 slice completes its lifecycle.

## Per-issue dependency and execution ledger

| Issue | Parent | Native prerequisites | State | Existing work / owner | Evidence | Acceptance blocker |
|---|---|---|---|---|---|---|
| #10 | — | — | blocked | unclaimed | M | required children |
| #11 | — | — | blocked | existing rig engine | R | required children |
| #12 | — | — | blocked | unclaimed | M | required children |
| #13 | — | — | blocked | unclaimed | M | required children |
| #14 | — | — | blocked | unclaimed | M | required children |
| #15 | — | — | blocked | unclaimed | M | required children |
| #16 | — | — | blocked | unclaimed | M | required children |
| #17 | — | — | blocked | unclaimed | M | required children |
| #18 | — | — | blocked | unclaimed | M | required children |
| #19 | 18 | — | blocked | unclaimed | M | required children |
| #20 | 18 | 19 | blocked | unclaimed | M | required children and #19 |
| #21 | 18 | 20 | blocked | unclaimed | M | required children and #20 |
| #22 | 18 | 21 | blocked | unclaimed | M | required children and #21 |
| #23 | 19 | — | reviewing | PR #192 | A | none |
| #24 | 19 | 23 | blocked | unclaimed | M | #23 |
| #25 | 19 | 24 | blocked | unclaimed | M | #24 |
| #26 | 19 | 24,25 | blocked | unclaimed | M | #24, #25 |
| #27 | 20 | 26 | blocked | unclaimed | M | #26 |
| #28 | 20 | 27 | blocked | unclaimed | M | #27 |
| #29 | 20 | 28 | blocked | unclaimed | M | #28 |
| #30 | 20 | 29 | blocked | unclaimed | M | #29 |
| #31 | 20 | 30 | blocked | unclaimed | M | #30 |
| #32 | 21 | 24,25,31 | blocked | unclaimed | M | #24, #25, #31 |
| #33 | 21 | 24,25 | blocked | unclaimed | M | #24, #25 |
| #34 | 21 | 25,33 | blocked | unclaimed | M | #25, #33 |
| #35 | 21 | 26,34,31 | blocked | unclaimed | M | #26, #34, #31 |
| #36 | 21 | 32,35 | blocked | unclaimed | M | #32, #35 |
| #37 | 21 | 32,33,35,36 | blocked | unclaimed | M | #32, #33, #35, #36 |
| #38 | 22 | 31,36 | blocked | unclaimed | M | #31, #36 |
| #39 | 22 | 38,35 | blocked | unclaimed | M | #38, #35 |
| #40 | 22 | 39 | blocked | unclaimed | M | #39 |
| #41 | 22 | 37,40 | blocked | unclaimed | M | #37, #40 |
| #42 | 22 | 39,40,41 | blocked | unclaimed | M | #39, #40, #41 |
| #43 | 10 | — | ready | unclaimed | M | none |
| #44 | 10 | 43 | blocked | unclaimed | M | #43 |
| #45 | 10 | 44 | blocked | unclaimed | M | #44 |
| #46 | 10 | 44 | blocked | unclaimed | M | #44 |
| #47 | 10 | 45,46 | blocked | unclaimed | M | #45, #46 |
| #48 | 10 | 47 | blocked | unclaimed | M | #47 |
| #49 | 10 | 48 | blocked | unclaimed | M | #48 |
| #50 | 10 | 49 | blocked | unclaimed | M | #49 |
| #51 | 11 | — | reviewing | PR #200 | R | merge and post-merge verification |
| #52 | 11 | 51 | blocked | prior #201 work | R | #51 |
| #53 | 11 | 52 | blocked | unclaimed | R | #52 |
| #54 | 11 | 53 | blocked | unclaimed | R | #53 |
| #55 | 11 | 54 | blocked | unclaimed | R | #54 |
| #56 | 11 | 55 | blocked | unclaimed | R | #55 |
| #57 | 11 | 56 | blocked | unclaimed | R | #56 |
| #58 | 11 | 57 | blocked | unclaimed | R | #57 |
| #59 | 12 | — | ready | unclaimed | M | none |
| #60 | 12 | 59 | blocked | unclaimed | M | #59 |
| #61 | 12 | 60 | blocked | unclaimed | M | #60 |
| #62 | 12 | 61 | blocked | unclaimed | M | #61 |
| #63 | 12 | 62 | blocked | unclaimed | M | #62 |
| #64 | 12 | 63 | blocked | unclaimed | M | #63 |
| #65 | 12 | 64 | blocked | unclaimed | M | #64 |
| #66 | 12 | 65 | blocked | unclaimed | M | #65 |
| #67 | 13 | — | ready | unclaimed | M | none |
| #68 | 13 | 67 | blocked | unclaimed | M | #67 |
| #69 | 13 | 68 | blocked | unclaimed | M | #68 |
| #70 | 13 | 69 | blocked | unclaimed | M | #69 |
| #71 | 13 | 70 | blocked | unclaimed | M | #70 |
| #72 | 13 | 71 | blocked | unclaimed | M | #71 |
| #73 | 13 | 72 | blocked | unclaimed | M | #72 |
| #74 | 13 | 73 | blocked | unclaimed | M | #73 |
| #75 | 14 | — | ready | unclaimed | M | none |
| #76 | 14 | 75 | blocked | unclaimed | M | #75 |
| #77 | 14 | 76 | blocked | unclaimed | M | #76 |
| #78 | 14 | 77 | blocked | unclaimed | M | #77 |
| #79 | 14 | 78 | blocked | unclaimed | M | #78 |
| #80 | 14 | 79 | blocked | unclaimed | M | #79 |
| #81 | 14 | 80 | blocked | unclaimed | M | #80 |
| #82 | 14 | 81 | blocked | unclaimed | M | #81 |
| #83 | 15 | — | ready | unclaimed | M | none |
| #84 | 15 | 83 | blocked | unclaimed | M | #83 |
| #85 | 15 | 84 | blocked | unclaimed | M | #84 |
| #86 | 15 | 85 | blocked | unclaimed | M | #85 |
| #87 | 15 | 86 | blocked | unclaimed | M | #86 |
| #88 | 15 | 87 | blocked | unclaimed | M | #87 |
| #89 | 15 | 88 | blocked | unclaimed | M | #88 |
| #90 | 15 | 89 | blocked | unclaimed | M | #89 |
| #91 | 16 | — | ready | unclaimed | M | none |
| #92 | 16 | 91 | blocked | unclaimed | M | #91 |
| #93 | 16 | 92 | blocked | unclaimed | M | #92 |
| #94 | 16 | 93 | blocked | unclaimed | M | #93 |
| #95 | 16 | 94 | blocked | unclaimed | M | #94 |
| #96 | 16 | 95 | blocked | unclaimed | M | #95 |
| #97 | 16 | 96 | blocked | unclaimed | M | #96 |
| #98 | 16 | 97 | blocked | unclaimed | M | #97 |
| #99 | 17 | — | ready | unclaimed | M | none |
| #100 | 17 | 99 | blocked | unclaimed | M | #99 |
| #101 | 17 | 100 | blocked | unclaimed | M | #100 |
| #102 | 17 | 101 | blocked | unclaimed | M | #101 |
| #103 | 17 | 102 | blocked | unclaimed | M | #102 |
| #104 | 17 | 103 | blocked | unclaimed | M | #103 |
| #105 | 17 | 104 | blocked | unclaimed | M | #104 |
| #106 | 17 | 105 | blocked | unclaimed | M | #105 |
| #107 | — | — | blocked | unclaimed | M | required children |
| #108 | 107 | — | blocked | unclaimed | M | required children |
| #109 | 107 | 108 | blocked | unclaimed | M | required children and #108 |
| #110 | 107 | 109 | blocked | unclaimed | M | required children and #109 |
| #111 | 107 | 110 | blocked | unclaimed | M | required children and #110 |
| #112 | 108 | — | merged | PR #190 | A | none |
| #113 | 108 | 112 | ready | unclaimed | M | none |
| #114 | 108 | 113 | blocked | unclaimed | M | #113 |
| #115 | 108 | 112,113 | blocked | unclaimed | M | #113; #112 satisfied |
| #116 | 109 | 113,115 | blocked | unclaimed | M | #113, #115 |
| #117 | 109 | 116 | blocked | unclaimed | M | #116 |
| #118 | 109 | 116,117 | blocked | unclaimed | M | #116, #117 |
| #119 | 109 | 116,117,118 | blocked | unclaimed | M | #116, #117, #118 |
| #120 | 110 | 119,114 | blocked | unclaimed | M | #119, #114 |
| #121 | 110 | 120 | blocked | unclaimed | M | #120 |
| #122 | 110 | 114,121,115 | blocked | unclaimed | M | #114, #121, #115 |
| #123 | 110 | 122,119 | blocked | unclaimed | M | #122, #119 |
| #124 | 111 | 123,118 | blocked | unclaimed | M | #123, #118 |
| #125 | 111 | 124 | blocked | unclaimed | M | #124 |
| #126 | 111 | 125,120,121 | blocked | unclaimed | M | #125, #120, #121 |
| #127 | 111 | 126 | blocked | unclaimed | M | #126 |
| #128 | — | — | blocked | unclaimed | M | required children |
| #129 | 128 | — | blocked | unclaimed | M | required children |
| #130 | 128 | 129 | blocked | unclaimed | M | required children and #129 |
| #131 | 128 | 130 | blocked | unclaimed | M | required children and #130 |
| #132 | 128 | 131 | blocked | unclaimed | M | required children and #131 |
| #133 | 128 | 132 | blocked | unclaimed | M | required children and #132 |
| #134 | 128 | 133 | blocked | unclaimed | M | required children and #133 |
| #135 | 128 | 134 | blocked | unclaimed | M | required children and #134 |
| #136 | 128 | 135 | blocked | unclaimed | M | required children and #135 |
| #137 | 129 | — | reviewing | PR #196 | A | none |
| #138 | 129 | 137 | blocked | unclaimed | M | #137 |
| #139 | 130 | 138 | blocked | unclaimed | M | #138 |
| #140 | 130 | 139 | blocked | unclaimed | M | #139 |
| #141 | 131 | 140 | blocked | unclaimed | M | #140 |
| #142 | 131 | 141 | blocked | unclaimed | M | #141 |
| #143 | 132 | 142 | blocked | unclaimed | M | #142 |
| #144 | 132 | 143 | blocked | unclaimed | M | #143 |
| #145 | 133 | 144 | blocked | unclaimed | M | #144 |
| #146 | 133 | 145 | blocked | unclaimed | M | #145 |
| #147 | 134 | 140,142 | blocked | unclaimed | M | #140, #142 |
| #148 | 134 | 147,143 | blocked | unclaimed | M | #147, #143 |
| #149 | 135 | 148,146 | blocked | unclaimed | M | #148, #146 |
| #150 | 135 | 149 | blocked | unclaimed | M | #149 |
| #151 | 136 | 150 | blocked | unclaimed | M | #150 |
| #152 | 136 | 151 | blocked | unclaimed | M | #151 |
| #153 | — | — | blocked | unclaimed | M | required children |
| #154 | 153 | — | blocked | unclaimed | M | required children |
| #155 | 153 | 154 | blocked | unclaimed | M | required children and #154 |
| #156 | 153 | 155 | blocked | unclaimed | M | required children and #155 |
| #157 | 153 | 156 | blocked | unclaimed | M | required children and #156 |
| #158 | 153 | 157 | blocked | unclaimed | M | required children and #157 |
| #159 | 153 | 158 | blocked | unclaimed | M | required children and #158 |
| #160 | 153 | 158 | blocked | unclaimed | M | required children and #158 |
| #161 | 153 | 156 | blocked | unclaimed | M | required children and #156 |
| #162 | 153 | 156 | blocked | unclaimed | M | required children and #156 |
| #163 | 153 | 159,160,161,162 | blocked | unclaimed | M | required children and native prerequisites |
| #164 | 153 | 163 | blocked | unclaimed | M | required children and #163 |
| #165 | 153 | 164 | blocked | unclaimed | M | required children and #164 |
| #166 | 154 | — | reviewing | PR #193 | A | none |
| #167 | 155 | 166 | blocked | unclaimed | M | #166 |
| #168 | 155 | 167 | blocked | unclaimed | M | #167 |
| #169 | 155 | 168 | blocked | unclaimed | M | #168 |
| #170 | 156 | 169 | blocked | unclaimed | M | #169 |
| #171 | 156 | 170 | blocked | unclaimed | M | #170 |
| #172 | 157 | 171 | blocked | unclaimed | M | #171 |
| #173 | 158 | 172 | blocked | unclaimed | M | #172 |
| #174 | 158 | 173 | blocked | unclaimed | M | #173 |
| #175 | 159 | 174 | blocked | unclaimed | M | #174 |
| #176 | 159 | 171,169 | blocked | unclaimed | M | #171, #169 |
| #177 | 160 | 173,169 | blocked | unclaimed | M | #173, #169 |
| #178 | 160 | 171,169 | blocked | unclaimed | M | #171, #169 |
| #179 | 161 | 169,168 | blocked | unclaimed | M | #169, #168 |
| #180 | 161 | 171,169 | blocked | unclaimed | M | #171, #169 |
| #181 | 161 | 170,175,178,179,180 | blocked | unclaimed | M | #170, #175, #178, #179, #180 |
| #182 | 162 | 172,171 | blocked | unclaimed | M | #172, #171 |
| #183 | 163 | 181,176,177,182 | blocked | unclaimed | M | #181, #176, #177, #182 |
| #184 | 163 | 183 | blocked | unclaimed | M | #183 |
| #185 | 163 | 184 | blocked | unclaimed | M | #184 |
| #186 | 164 | 185 | blocked | unclaimed | M | #185 |
| #187 | 164 | 186 | blocked | unclaimed | M | #186 |
| #188 | 165 | 187 | blocked | unclaimed | M | #187 |
| #189 | 165 | 188 | blocked | unclaimed | M | #188 |

## Cross-cutting work outside the native roadmap

- #191 / PR #194: stable-actor prop ownership in existing 2D continuity. Reuse this fix rather than changing owner identity independently.
- #195 / PR #198: exclusive rig/portable restoration. Merge hold remains: unresolved symlink-to-outside-root ownership race reported by independent review. Do not merge before repair and renewed review/checks.
- #197 / PR #199: bundle publication and leaf-preserving controller ownership. Review this shared fix before adapting #198; avoid competing lock helpers.

## Baseline and current evidence

- Source capture came from a clean checkout; no local user modifications were overwritten. Repository-local agent/contribution instruction files were not present in the inspected complete tree. README, SKILL.md and relevant authorities were inspected.
- Canonical implemented 3D convention is Y-up, right-handed, meters, XYZW. Related issue proposals of Z-up are not new independent authorities. Explicit basis conversion is required. Existing 2D pixel semantics are unchanged.
- Initial host test run at `7995804`: 853 discovered tests, one failure, nine skips. The host startup hook preloaded NumPy and pygltflib was absent; this is not a passing baseline. A clean venv rerun with the pinned interchange reader is in progress.
- At PR #200 head `be3bc294`: clean schema/math gate 20 passed; all rig tests 86 run, zero failures/errors, five explicit optional external-integration skips. Schema/template parity, actual source-delivery verification and clean-tree/diff checks pass. Local Blender/browser/Khronos runs are not claimed.
- PR #200 remote current-head CI: all three public-delivery OS jobs in run 39839668188 and all nine rig jobs in run 39839668224 passed, including actual Blender, browser, Khronos and archive gates. Independent follow-through review: 5631489108, in addition to the original corrected-head independent reviews. Normal merge policy remains in force.
- Current retained original v3 media transport verifies; older unavailable historical/private payloads remain explicit limitations. Synthetic geometry demonstrations never replace original media or human visual approval.

## Final roadmap gates still open

All twelve parent missions remain open. Reusable canonical multi-scene assets, complete scene/editor/director systems, continuity repair with actual selective rerendering, full asset-library restore/rerender, real solver categories and the Physics Laboratory, complete required silent-video demonstrations and corresponding visual acceptance have not been delivered by this execution ledger.
