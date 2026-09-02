# Guided spatial storytelling — human-test package

Status: `READY_FOR_HUMAN_TEST / AWAITING_HUMAN_TEST`

No participant responses are included in this document. Codex prepared the protocol only; real people must perform and record the test.

## Participants

- At least five people who have not previously used CITY GAP.
- Approximately two participants with municipal, GIS, transport, planning, or related domain experience.
- Approximately three non-domain first-time participants.
- At least one participant completes the task at a 390 × 844-equivalent mobile viewport.
- Municipal workflow fit is evaluated separately from first-run comprehension.

## Moderator setup

1. Open the feature-branch production preview at `?experience=guided&story=intro`.
2. Reset the URL and browser state before each participant.
3. Do not explain the three scenes, PLATEAU, the section, or the meaning of `未確認` before the task.
4. Ask the participant to think aloud. Do not point at the candidate list, A–B line, or primary action.
5. Record observed facts and verbatim answers. Do not translate uncertainty into a positive answer.

## First-run task

Prompt:

> 舞鶴市で気になる地域を一つ選び、その地域の街の形と、現地で確かめる場所まで進んでください。分かったと思ったところで止めてください。

Record:

| Field | Response |
|---|---|
| Participant ID | |
| Domain experience | |
| Device / viewport | |
| Start time | |
| End time | |
| Click count | |
| Wrong turns | |
| Needed moderator help | |
| Candidate ↔ map connection noticed | |
| A–B map ↔ section connection noticed | |
| Exact target ↔ checks connection noticed | |
| `未確認` noticed | |
| Keyboard/touch/accessibility observation | |
| Verbatim comments | |

## Comprehension questions

Ask without offering answer choices.

1. この画面は、地域について何をしていましたか。
2. 一覧の候補と地図は、どのようにつながっていましたか。
3. 紫のA–B線と下の図は、何を表していると思いましたか。
4. 最後に強調された道路・建物と、右側の項目はどう関係していましたか。
5. `未確認`は何が未確認だと思いましたか。
6. この結果は、危険判定、政策推奨、歩行可能性の証明、現地調査済みのどれかを意味しますか。そう思う理由は何ですか。

## Mechanical success criteria

- The participant reaches Scene 3 without moderator instruction.
- The participant can identify the same candidate in the list and map.
- The participant describes the map A–B line and section as the same real cut location, without calling it a route.
- The participant says that the highlighted object is where the concise checks apply.
- The participant understands that no field result has yet been collected.
- No participant result is entered by the implementation team in advance.

The product-level comprehension threshold remains a decision for the real test report. Until that report exists, retain `AWAITING_HUMAN_TEST` and do not claim `GUIDED_UX_PASS`, `HUMAN_COMPREHENSION_PASS`, or `VISUAL_QUALITY_PASS`.

## Separate municipal workflow review sheet

| Question | Verbatim response | Evidence / workflow reference |
|---|---|---|
| At what meeting, GIS, document, or review step could an uncertainty-linked target be used? | | |
| Are 3–5 urban-state checks enough to decide the next action? | | |
| Does the source limitation explain why the check is needed? | | |
| Which role would own the follow-up outside this public demo? | | |
| What existing tool already handles assignment or evidence collection? | | |
| Why would the municipality not use this chain? | | |

Municipal acceptance remains `AWAITING_MUNICIPAL_WORKFLOW_REVIEW` regardless of first-run results.
