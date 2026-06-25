// yozakura テーマの装飾レイヤー。余白 (canvas の外) に夜桜の気配を出す:
// 桜の花びらが回転しながらゆらゆらと舞い落ちる。
// position:fixed / pointer-events:none / z-index:-1 でアプリ本体の裏に敷くため、
// 不透明な波形 canvas には一切かからない (= アノテーションを邪魔しない)。
// 動きは演出の核なので prefers-reduced-motion 時は CSS 側でレイヤーごと非表示。

// 桜の花びら1枚 (先端に切れ込みのある様式化シルエット)。色は CSS 側で散らす。
function Petal() {
  return (
    <svg className="yozakura-blossom" viewBox="0 0 20 20" aria-hidden="true">
      <path d="M10 2 C 5 4 4 11 8 16 Q9 18.5 10 16 Q11 18.5 12 16 C 16 11 15 4 10 2 Z" />
    </svg>
  );
}

export function YozakuraScene() {
  // 落下位置・速度・大きさ・ゆらぎは nth-child で CSS 側に散らす (8枚)。
  return (
    <div className="yozakura-scene" aria-hidden="true">
      {(["p0", "p1", "p2", "p3", "p4", "p5", "p6", "p7"] as const).map((k) => (
        <span key={k} className="yozakura-petal">
          <Petal />
        </span>
      ))}
    </div>
  );
}
