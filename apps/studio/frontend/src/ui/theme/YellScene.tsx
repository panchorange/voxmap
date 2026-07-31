// yell テーマの装飾レイヤー。余白 (canvas の外) に夏のエールらしい炭酸の気配を出す:
// 泡がゆっくり立ちのぼりながら、わずかに左右へ蛇行する。
// position:fixed / pointer-events:none / z-index:-1 でアプリ本体の裏に敷くため、
// 不透明な波形 canvas には一切かからない (= アノテーションを邪魔しない)。
// 動きは演出の核なので prefers-reduced-motion 時は CSS 側でレイヤーごと非表示。

export function YellScene() {
  // 上昇位置・速度・大きさ・蛇行の幅は nth-child で CSS 側に散らす (9個)。
  return (
    <div className="yell-scene" aria-hidden="true">
      {(["b0", "b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8"] as const).map((k) => (
        <span key={k} className="yell-bubble">
          <span className="yell-bead" />
        </span>
      ))}
    </div>
  );
}
