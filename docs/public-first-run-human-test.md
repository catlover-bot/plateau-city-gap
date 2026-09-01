# Public first-run human-test package

Goal: `public-first-run-ux-v1`

Package status:

- `READY_FOR_HUMAN_TEST`
- `AWAITING_HUMAN_TEST`
- `AWAITING_MUNICIPAL_WORKFLOW_REVIEW`
- No participant answer has been generated, inferred, or filled by Codex.

## Participant composition

Recruit at least five people who have not used CITY GAP before.

- About two participants: municipal, GIS, urban-planning, or related domain experience.
- About three participants: first-time users without domain experience.
- At least one participant uses a 390px-class mobile viewport.
- Municipal workflow fit is reviewed separately from first-run comprehension.

Record participant codes only. Do not put names, organizations, or contact details in this document.

## Test setup

- Use the feature branch build, not `main` or the GitHub Pages production root.
- Start from the Public root with no prior explanation.
- Keep the browser zoom at 100%.
- Use a production preview.
- Clear local site state before each participant.
- Do not reveal the intended answer until the task is complete or abandoned.
- Do not ask participants to upload photos, GPS, answers, or internal task data.

## 30–60 second first-run task

Read this instruction verbatim:

> 舞鶴市で気になる場所を一つ選び、周辺のデータから確認できることと、まだ確認が必要なことを見つけてください。最後に、現地で確かめる場所と「未確認」の項目を示してください。

The moderator must not name a button, radius, or intended path.

Expected deterministic reference path, for moderator observation only:

1. `地図で場所を調べる`
2. `選んだ駅を起点にする`
3. `800m`
4. `この範囲を調べる`
5. `確認場所を見る`

Do not correct a participant who chooses 500m, 1km, custom radius, or a map point. Record the path actually taken.

## Mobile task

Use a viewport equivalent to 390×844.

Ask the participant to:

1. Choose a place and radius.
2. Find the Area Summary.
3. Find one item that data alone cannot determine.
4. Open its confirmation location.
5. Find the `未確認` state.
6. Return one step and change the selected unknown.

Record horizontal scrolling, map/panel overlap, hidden primary action, missed back action, and accidental activation separately.

## Moderator guide

- Say only: `考えていることを声に出してください。`
- Do not explain PLATEAU, Known/Unknown, Investigation Area, 800m methodology, or verification tasks before the run.
- If the participant asks what 800m means, respond: `画面にある説明を探してみてください。`
- Stop the run only for a technical failure, safety concern, or participant request.
- After the task, ask the comprehension questions in order.
- Preserve negative and partial answers verbatim.
- Do not convert hesitation into a positive result.

## Comprehension questions

1. この画面は何をするものだと思いましたか。
2. データから確認できたことと、まだ分からないことは何でしたか。
3. なぜ確認場所がPLATEAU上の建物・道路・範囲に結び付いていましたか。
4. 800mは実際に徒歩10分で到達できる範囲ですか。
5. `未確認`は何を意味すると理解しましたか。
6. この画面はAIが地域を判断したり、政策を推奨したり、危険を判定したりしていますか。
7. `詳細分析`は最初に押す主な導線だと思いましたか。
8. 次に自治体業務へつなぐなら、どの会議、GIS、帳票、または検討工程で使えそうですか。

Question 8 is recorded for workflow evidence but does not count as first-run comprehension success.

## Empty response sheet

| Field | Response |
|---|---|
| Participant code | |
| Domain experience | |
| Device / viewport | |
| Start timestamp | |
| End timestamp | |
| Completion time | |
| Click count | |
| Path taken | |
| Completed without help | |
| First hesitation | |
| Misclicks | |
| Area → quantified state understood | |
| Known / Unknown distinction understood | |
| PLATEAU target purpose understood | |
| 800m radius vs actual walking time distinguished | |
| `未確認` found | |
| AI / policy / hazard boundary understood | |
| `詳細分析` treated as secondary | |
| Verbatim explanation | |
| Verbatim negative or uncertainty | |
| Moderator intervention | |
| Technical failure | |

Duplicate this table for each participant. Leave every field empty until a real participant provides evidence.

## Accessibility observation sheet

| Observation | Result / note |
|---|---|
| Keyboard-only completion | |
| Focus order understandable | |
| Focus indicator visible | |
| Screen-reader control names understandable | |
| Heading order understandable | |
| 200% zoom usable | |
| Mobile text readable | |
| Touch targets usable | |
| Color alone required | |
| Motion discomfort | |
| Other barrier, verbatim | |

## Separate municipal workflow review

This review must not be substituted by non-domain first-run participants.

| Question | Verbatim municipal response |
|---|---|
| Which radius is used: 500 / 800 / 1000 / other? | |
| What does “town unit” mean operationally? | |
| Which planning restrictions are actually needed? | |
| Which minimum Area Summary items are needed? | |
| How are radius and real walking-time areas distinguished? | |
| Where can Area → Unknown → Verification be used? | |
| Does the task duplicate existing Field Maps / Survey123 / paper practice? | |
| Is a PLATEAU object or honest mesh fallback useful? | |
| Why would the workflow not be used? | |

## Success and failure decision

First-run comprehension passes only if all conditions hold:

- All five participants start from the single primary CTA without moderator direction.
- At least four of five explain Area → quantified evidence → Known/Unknown → confirmation location in their own words.
- At least four of five distinguish the 800m radius from an actual walking-time isochrone.
- At least four of five state that CITY GAP is not an AI policy recommendation or hazard judgment.
- At least four of five find `未確認`.
- The mobile participant completes the flow without horizontal scrolling or map/panel overlap.

Municipal workflow fit remains `AWAITING_MUNICIPAL_WORKFLOW_REVIEW` until a real municipal reviewer identifies an actual work process and records objections.

If the conditions fail, keep `AWAITING_HUMAN_TEST` or record a contradicted hypothesis. Do not rewrite negative evidence as success.
