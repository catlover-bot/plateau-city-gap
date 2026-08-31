# A5 human comprehension test protocol

Status: `AWAITING_HUMAN_TEST`

Goal: determine whether a first-time user understands the A5 core chain within 30–60 seconds. This protocol does not validate municipal workflow fit, operational efficiency, or field results.

## Test build

Use the production build at the feature-branch HEAD:

```bash
cd frontend
npm run build
npm run preview -- --host 127.0.0.1
```

Open:

- copy A: `http://127.0.0.1:4173/plateau-city-gap/?journey=area&copy=A`
- copy B: `http://127.0.0.1:4173/plateau-city-gap/?journey=area&copy=B`
- copy C: `http://127.0.0.1:4173/plateau-city-gap/?journey=area&copy=C`

If the preview selects another port, preserve the path and query. Test at least five first-time participants; at least one session uses a 390×844-equivalent mobile viewport. Rotate A/B/C rather than telling participants which copy is preferred.

## Facilitator script

Say only:

> 舞鶴市の周辺分析を試す画面です。いつもどおり触って、何をするものか考えながら進めてください。

Do not explain Investigation Area, Known/Unknown, PLATEAU targets, verification tasks, the 800m methodology, or the expected answer before the task.

Ask the participant to:

1. choose a place;
2. choose a range;
3. tell you what the data establishes;
4. find what the data does not establish;
5. continue until the concrete verification targets and tasks are visible.

Stop the primary timer when the unverified tasks are visible or at 60 seconds. Do not fabricate or ask for a photo, GPS position, field answer, assignee, or municipal review.

## Observation record

Record facts, not inferred success:

| Field | Value |
|---|---|
| participant ID | anonymized local ID |
| copy | A / B / C |
| viewport | width × height |
| first primary action | exact control selected |
| time to place selection | seconds |
| time to Known/Unknown | seconds |
| time to unverified tasks | seconds or not reached |
| click count | count |
| methodology note opened | yes / no |
| required help | verbatim intervention or none |
| current status found | yes / no |
| participant summary | verbatim |
| confusion | verbatim |
| field evidence expected | yes / no, verbatim reason |

After the timer, ask without leading:

1. 「この画面は何をするものだと思いましたか」
2. 「データから分かったことと、まだ分からないことは何でしたか」
3. 「PLATEAU上の対象と未確認タスクは、なぜ表示されたと思いますか」
4. 「800mは何を意味していると思いますか」
5. 「これは政策推奨、危険判定、市民通報、現地確認のどれに近いですか。そう思う理由は何ですか」

## Pass boundary

A5 remains `AWAITING_HUMAN_TEST` until real observations are recorded. The earlier deterministic walkthrough is preparation evidence only.

The copy comprehension gate passes only if at least four of five participants can explain, in their own words:

```text
selected place/range
  -> quantified public-data facts
  -> explicit source-bounded unknowns
  -> concrete PLATEAU/official targets
  -> still-unverified checks
```

They must not describe the radius as an actual walking-time isochrone, the UI as AI knowing the locality better than staff, or the previews as completed field evidence. Report failed and contradictory observations without rewriting them.
