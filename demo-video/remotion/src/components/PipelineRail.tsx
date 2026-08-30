import {Easing, interpolate, useCurrentFrame} from "remotion";
import {COLORS} from "../constants";

type Stage = {
  number: string;
  label: string;
  detail: string;
  accent: string;
};

const STAGES: Stage[] = [
  {number: "01", label: "Document", detail: "Immutable revision", accent: COLORS.blue},
  {number: "02", label: "Exact anchor", detail: "Page + offsets", accent: COLORS.mint},
  {number: "03", label: "Cited answer", detail: "Sufficient evidence", accent: COLORS.mint},
  {number: "04", label: "Human gate", detail: "Approve once", accent: COLORS.amber},
];

export const PipelineRail: React.FC<{compact?: boolean}> = ({compact = false}) => {
  const frame = useCurrentFrame();

  return (
    <div style={{position: "relative", display: "flex", gap: compact ? 18 : 26, alignItems: "stretch"}}>
      <div
        style={{
          position: "absolute",
          left: compact ? 36 : 48,
          right: compact ? 36 : 48,
          top: compact ? 34 : 42,
          height: 2,
          backgroundColor: "rgba(220,230,232,.16)",
        }}
      >
        <div
          style={{
            width: `${interpolate(frame, [18, 100], [0, 100], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            })}%`,
            height: "100%",
            background: `linear-gradient(90deg, ${COLORS.blue}, ${COLORS.mint}, ${COLORS.amber})`,
            boxShadow: `0 0 18px ${COLORS.mint}`,
          }}
        />
      </div>
      {STAGES.map((stage, index) => (
        <div
          key={stage.number}
          style={{
            position: "relative",
            width: compact ? 248 : 328,
            minHeight: compact ? 136 : 168,
            padding: compact ? "20px 22px" : "26px 28px",
            borderRadius: compact ? 20 : 26,
            background: "linear-gradient(145deg, rgba(12,37,52,.92), rgba(5,20,30,.92))",
            outline: `1px solid ${stage.accent}48`,
            boxShadow: "0 24px 80px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.07)",
            opacity: interpolate(frame, [16 + index * 16, 30 + index * 16], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
            translate: interpolate(frame, [16 + index * 16, 34 + index * 16], ["0px 30px", "0px 0px"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          <div
            style={{
              position: "relative",
              zIndex: 1,
              width: compact ? 30 : 36,
              height: compact ? 30 : 36,
              display: "grid",
              placeItems: "center",
              borderRadius: 999,
              fontFamily: "monospace",
              fontSize: compact ? 12 : 14,
              fontWeight: 700,
              color: COLORS.obsidian,
              backgroundColor: stage.accent,
              boxShadow: `0 0 24px ${stage.accent}66`,
            }}
          >
            {stage.number}
          </div>
          <div style={{marginTop: compact ? 20 : 26, fontFamily: "Manrope Variable", fontSize: compact ? 24 : 30, fontWeight: 720, color: COLORS.white}}>
            {stage.label}
          </div>
          <div style={{marginTop: 7, fontFamily: "Geist Variable", fontSize: compact ? 17 : 20, color: COLORS.muted}}>
            {stage.detail}
          </div>
        </div>
      ))}
    </div>
  );
};
