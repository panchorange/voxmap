// blackdiamond テーマの装飾レイヤー。余白 (canvas の外) に漆黒の地で
// ダイヤのファセットが光を弾くような煌めき (4 方向の閃光) をゆっくり瞬かせる。
// position:fixed / pointer-events:none / z-index:-1 でアプリ本体の裏に敷くため、
// 不透明な波形 canvas には一切かからない (= アノテーションを邪魔しない)。
// 瞬きは演出の核なので prefers-reduced-motion 時は CSS 側でレイヤーごと非表示。

// 4 方向に伸びる星形の閃光 (sparkle)。色・大きさ・瞬きは CSS 側で散らす。
function Glint() {
  return (
    <svg className="bd-glint__star" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 0 C8.8 5 11 7.2 16 8 C11 8.8 8.8 11 8 16 C7.2 11 5 8.8 0 8 C5 7.2 7.2 5 8 0 Z" />
    </svg>
  );
}

// ダイヤモンドの剣 (横向き、切先は右)。刃は上下 2 面のファセット + 稜線で
// 結晶らしく、柄は金。切先には常時瞬くきらめきを仕込む。動きは CSS 側。
function DiamondSword() {
  return (
    <svg className="bd-sword-svg" viewBox="0 0 132 26" aria-hidden="true">
      {/* 柄頭・柄・鍔 (金) */}
      <circle className="bd-sword-hilt" cx="6" cy="13" r="4" />
      <rect className="bd-sword-hilt" x="8" y="10" width="12" height="6" rx="1" />
      <rect className="bd-sword-hilt" x="19" y="3" width="4" height="20" rx="1.5" />
      {/* 刃: 下面 (深緑) → 上面ファセット (明ミント) → 稜線ハイライト。切先は右 */}
      <path className="bd-sword-blade" d="M23 13 L102 7 L130 13 L102 19 Z" />
      <path className="bd-sword-facet" d="M23 13 L102 7 L130 13 Z" />
      <line className="bd-sword-ridge" x1="23" y1="13" x2="130" y2="13" />
      {/* 切先のきらめき */}
      <path
        className="bd-sword-spark"
        d="M128 13 C128.5 10 130 8.5 133 8 C130 7.5 128.5 6 128 3 C127.5 6 126 7.5 123 8 C126 8.5 127.5 10 128 13 Z"
      />
    </svg>
  );
}

export function BlackDiamondScene() {
  // 位置・大きさ・速度・タイミング・色味は nth-child で CSS 側に散らす (8 粒)。
  return (
    <div className="blackdiamond-scene" aria-hidden="true">
      {(["g0", "g1", "g2", "g3", "g4", "g5", "g6", "g7"] as const).map((k) => (
        <span key={k} className="bd-glint">
          <Glint />
        </span>
      ))}
      {/* 時々、下部の余白を一閃する剣 */}
      <span className="bd-sword">
        <DiamondSword />
      </span>
    </div>
  );
}
