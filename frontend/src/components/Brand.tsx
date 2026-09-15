type BrandMarkProps = {
  size?: number;
  /** color: 墨 + 鉴青; mono: 单色(继承 currentColor); reverse: 深色底反白 */
  variant?: "color" | "mono" | "reverse";
};

const INK = "#23282B";
const RAGGED = "#A8A59C";
const JADE = "#0F6E56";

/**
 * 师鉴通主标识「明镜」。
 * 正圆镜面（顶部 24° 缺口）+ 论文文本行（上参差、下对齐）+ 圆心镜钮。
 * 任何尺寸下圆与镜钮不得省略。
 */
export function BrandMark({ size = 40, variant = "color" }: BrandMarkProps) {
  const ink = variant === "reverse" ? "#F4F2EC" : variant === "mono" ? "currentColor" : INK;
  const ragged =
    variant === "reverse" ? "#F4F2EC" : variant === "mono" ? "currentColor" : RAGGED;
  const raggedOpacity = variant === "color" ? 1 : 0.42;
  const knob = variant === "reverse" ? "#5DCAA5" : variant === "mono" ? "currentColor" : JADE;

  return (
    <svg width={size} height={size} viewBox="0 0 96 96" role="img" aria-label="师鉴通">
      <g fill="none" strokeLinecap="round">
        <path d="M31.1 11.75 A 40 40 0 1 0 64.9 11.75" stroke={ink} strokeWidth="2.6" />
        <line x1="42" y1="23" x2="68" y2="23" stroke={ragged} strokeWidth="1.7" opacity={raggedOpacity} />
        <line x1="32" y1="35.5" x2="82" y2="35.5" stroke={ragged} strokeWidth="1.7" opacity={raggedOpacity} />
        <line x1="15" y1="48" x2="42" y2="48" stroke={ink} strokeWidth="2.6" />
        <line x1="54" y1="48" x2="81" y2="48" stroke={ink} strokeWidth="2.6" />
        <line x1="15" y1="60.5" x2="81" y2="60.5" stroke={ink} strokeWidth="2.2" />
        <line x1="21" y1="73" x2="58" y2="73" stroke={ink} strokeWidth="2.2" />
      </g>
      <circle cx="48" cy="48" r="4.8" fill={knob} />
    </svg>
  );
}

/**
 * 动态标识「鉴」：检测进行中，镜面线自上而下扫过，
 * 文本行由浅灰（未校）转为墨黑（已正）。用作加载状态。
 */
export function ScanningMark({ size = 64 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 96 96" role="img" aria-label="正在检测">
      <defs>
        <clipPath id="sjt-mirror-clip">
          <circle cx="48" cy="48" r="38" />
        </clipPath>
        <clipPath id="sjt-clip-ink">
          <rect className="sjt-clip-ink" x="0" y="0" width="96" height="96" />
        </clipPath>
        <clipPath id="sjt-clip-gray">
          <rect className="sjt-clip-gray" x="0" y="0" width="96" height="96" />
        </clipPath>
      </defs>
      <g fill="none" strokeLinecap="round" clipPath="url(#sjt-clip-gray)">
        <line x1="42" y1="23" x2="68" y2="23" stroke={RAGGED} strokeWidth="1.7" />
        <line x1="32" y1="35.5" x2="82" y2="35.5" stroke={RAGGED} strokeWidth="1.7" />
        <line x1="15" y1="48" x2="42" y2="48" stroke={RAGGED} strokeWidth="1.7" />
        <line x1="54" y1="48" x2="81" y2="48" stroke={RAGGED} strokeWidth="1.7" />
        <line x1="15" y1="60.5" x2="81" y2="60.5" stroke={RAGGED} strokeWidth="1.7" />
        <line x1="21" y1="73" x2="58" y2="73" stroke={RAGGED} strokeWidth="1.7" />
      </g>
      <g fill="none" strokeLinecap="round" clipPath="url(#sjt-clip-ink)">
        <line x1="42" y1="23" x2="68" y2="23" stroke={INK} strokeWidth="1.7" />
        <line x1="32" y1="35.5" x2="82" y2="35.5" stroke={INK} strokeWidth="1.7" />
        <line x1="15" y1="48" x2="42" y2="48" stroke={INK} strokeWidth="2.6" />
        <line x1="54" y1="48" x2="81" y2="48" stroke={INK} strokeWidth="2.6" />
        <line x1="15" y1="60.5" x2="81" y2="60.5" stroke={INK} strokeWidth="2.2" />
        <line x1="21" y1="73" x2="58" y2="73" stroke={INK} strokeWidth="2.2" />
      </g>
      <g clipPath="url(#sjt-mirror-clip)">
        <line className="sjt-scan-bar" x1="4" y1="0" x2="92" y2="0" stroke={JADE} strokeWidth="2.2" strokeLinecap="round" />
      </g>
      <circle cx="48" cy="48" r="4.8" fill={JADE} />
      <path d="M31.1 11.75 A 40 40 0 1 0 64.9 11.75" fill="none" stroke={INK} strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}
