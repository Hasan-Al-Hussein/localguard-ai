import {interpolate, useCurrentFrame} from "remotion";
import {COLORS} from "../constants";

type Props = {
  size?: number;
  label?: boolean;
  animate?: boolean;
};

export const BrandMark: React.FC<Props> = ({size = 72, label = false, animate = true}) => {
  const frame = useCurrentFrame();

  return (
    <div style={{display: "flex", alignItems: "center", gap: 20}}>
      <div
        style={{
          width: size,
          height: size,
          borderRadius: Math.round(size * 0.26),
          display: "grid",
          placeItems: "center",
          color: COLORS.mintSoft,
          background: "linear-gradient(145deg, rgba(82,224,196,.20), rgba(79,140,255,.10))",
          outline: "1px solid rgba(82,224,196,.36)",
          boxShadow: "0 22px 70px rgba(82,224,196,.15), inset 0 1px 0 rgba(255,255,255,.14)",
          scale: animate
            ? interpolate(frame, [0, 20], [0.82, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                output: "perceptual-scale",
              })
            : 1,
        }}
      >
        <svg width={size * 0.58} height={size * 0.58} viewBox="0 0 64 64" fill="none">
          <path d="M32 5 56 18.5v27L32 59 8 45.5v-27L32 5Z" stroke="currentColor" strokeWidth="3" />
          <path d="M32 15 47 23.5v17L32 49l-15-8.5v-17L32 15Z" stroke={COLORS.mint} strokeWidth="3" />
          <path d="M25 32h14M32 25v14" stroke={COLORS.white} strokeWidth="3" strokeLinecap="round" />
          <circle cx="32" cy="32" r="4" fill={COLORS.mint} />
        </svg>
      </div>
      {label ? (
        <div>
          <div style={{fontFamily: "Manrope Variable", fontSize: 30, fontWeight: 780, color: COLORS.white}}>
            LocalGuard AI
          </div>
          <div
            style={{
              marginTop: 4,
              fontFamily: "Geist Variable",
              fontSize: 18,
              letterSpacing: 2.6,
              textTransform: "uppercase",
              color: COLORS.mint,
            }}
          >
            Proof Gate
          </div>
        </div>
      ) : null}
    </div>
  );
};
