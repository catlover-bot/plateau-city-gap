# CITY GAP frontend

React, TypeScript, Vite and CesiumJSで構成した静的Webアプリです。分析結果をコピーした`public/data`をSingle Source of Truthとして表示し、ブラウザ側に分析値は埋め込みません。

```bash
npm install
npm run dev
```

検証は`npm run lint`、`npm run typecheck`、`npm run test`、`npm run build`で実行します。Viteのbase pathはGitHub Pages向けに`/plateau-city-gap/`です。
