// yusha テーマの装飾レイヤー。余白 (canvas の外) に勇者の冒険の気配を出す:
// 高空をシルエットの鳥が羽ばたきながら横切り、地平を馬が駆ける。
// position:fixed / pointer-events:none / z-index:-1 でアプリ本体の裏に敷くため、
// 不透明な波形 canvas には一切かからない (= アノテーションを邪魔しない)。
// 動きは演出の核なので prefers-reduced-motion 時は CSS 側でレイヤーごと非表示。

// 羽ばたく鳥のシルエット (左右の翼が肩を支点に回転)。
function Bird() {
  return (
    <svg className="yusha-bird" viewBox="0 0 32 12" aria-hidden="true">
      <path className="yusha-wing yusha-wing--l" d="M16 6 C 10 0 4 1 0 6 C 6 5 11 5 16 7 Z" />
      <path className="yusha-wing yusha-wing--r" d="M16 6 C 22 0 28 1 32 6 C 26 5 21 5 16 7 Z" />
    </svg>
  );
}

// 馬に乗った勇者のシルエット (地平を駆ける)。脚は省略した様式化シルエット。
function Rider() {
  return (
    <svg className="yusha-rider" viewBox="0 0 64 40" aria-hidden="true">
      {/* 馬体 + たてがみ + 脚 + 騎手をまとめた一筆書きシルエット */}
      <path d="M4 26 L10 22 Q14 18 22 19 L40 19 Q44 14 50 15 L54 13 L52 17 Q58 18 60 24 L57 25 Q56 22 52 22 L50 28 L47 28 L48 22 L26 22 L27 30 L24 30 L23 22 L16 22 L15 30 L12 30 L13 22 Q9 23 8 27 Z" />
      {/* 騎手 */}
      <path d="M34 19 Q33 12 37 11 Q41 12 40 19 Z" />
      <circle cx="38" cy="9" r="2.4" />
    </svg>
  );
}

export function YushaScene() {
  return (
    <div className="yusha-scene" aria-hidden="true">
      {/* 鳥は高度・速度・タイミングを散らす (位置/遅延は nth-child で CSS 側) */}
      <span className="yusha-flyer">
        <Bird />
      </span>
      <span className="yusha-flyer">
        <Bird />
      </span>
      <span className="yusha-flyer">
        <Bird />
      </span>
      <span className="yusha-flyer">
        <Bird />
      </span>
      <span className="yusha-gallop">
        <Rider />
      </span>
    </div>
  );
}
