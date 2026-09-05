export type GuidedCheck = readonly [id: string, label: string, reason: string];

export const GUIDED_CONTENT = {
  intro: {
    titleFirstLine: "舞鶴の地域を、",
    titleSecondLine: "地図からたどる。",
    description: "地域を選び、街の形と、データだけでは判断できない場所を地図でたどります。",
    action: "地域を選ぶ",
  },
  find: {
    title: "地域を選ぶ",
    lead: "地図または一覧から、調べる地域を選べます。",
    action: "街の形を見る",
  },
  understand: {
    back: "範囲選択へ戻る",
    unknownTitle: "形が見えても、実際の歩きやすさまでは判断できません。",
    unknownReason: "PLATEAU道路面は、歩道・横断・入口や、実際に人が通れることを確認した経路データではないためです。",
    action: "確認場所を見る",
  },
  verify: {
    back: "街の形へ戻る",
    title: "現地で確認すること",
    emptyEvidence: "回答や確認結果はまだありません。",
    advancedAction: "詳細分析を開く",
  },
  loading: {
    map: "舞鶴市の500m範囲を読み込んでいます",
    context: "選択した範囲のPLATEAU建物・道路を読み込んでいます",
  },
} as const;

export const GUIDED_CHECKS = {
  road: [
    ["walking-passability", "道路を実際に歩いて通行できるか", "PLATEAU道路面は歩行可能性を表さないため。"],
    ["walking-sidewalk", "歩道の有無と有効幅員", "公式歩行ネットワークと歩道属性を収録していないため。"],
    ["walking-crossing", "横断箇所と横断時の見通し", "道路形状だけでは安全な横断可否を判断できないため。"],
    ["walking-building-link", "建物から道路までの接続", "建物と道路の形だけでは入口・私道・階段を特定できないため。"],
  ],
  building: [
    ["building-entrance", "建物の入口と道路のつながり", "建物形状からは実際の入口を特定できないため。"],
    ["building-current-use", "建物が現在使われているか", "PLATEAUの用途・形状は現在の利用状況を保証しないため。"],
    ["building-access-barrier", "入口までに段差や通行制限があるか", "公開データだけでは現地の障害を判断できないため。"],
  ],
  facility: [
    ["facility-open", "施設が現在利用できるか", "登録時点以後の休止・閉鎖を公開データだけでは判断できないため。"],
    ["facility-entrance", "利用者用の入口がどこにあるか", "登録地点は入口位置を示すものではないため。"],
    ["facility-access", "道路から入口まで支障なく移動できるか", "段差・階段・通行制限を収録していないため。"],
  ],
} as const satisfies Record<"road" | "building" | "facility", readonly GuidedCheck[]>;
