import {AbsoluteFill, Easing, Interactive, interpolate, useCurrentFrame} from "remotion";
import {COLORS} from "../constants";
import {CinematicBackdrop} from "../components/CinematicBackdrop";
import {Headline, Kicker, SupportingCopy} from "../components/Typography";
import {SceneChrome} from "../components/SceneChrome";

const FracturedDocument: React.FC<{delay: number; x: number; y: number; rotate: number; label: string}> = ({
  delay,
  x,
  y,
  rotate,
  label,
}) => {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: 520,
        height: 220,
        padding: 28,
        borderRadius: 22,
        background: "linear-gradient(145deg, rgba(24,45,58,.94), rgba(8,24,34,.94))",
        outline: "1px solid rgba(220,230,232,.13)",
        boxShadow: "0 30px 90px rgba(0,0,0,.34)",
        opacity: interpolate(frame, [delay, delay + 18], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
        translate: interpolate(frame, [delay, delay + 24, 300], ["80px 32px", "0px 0px", "-18px 10px"], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
        rotate: `${rotate}deg`,
      }}
    >
      <div style={{fontFamily: "monospace", fontSize: 14, letterSpacing: 2, color: COLORS.mint}}>{label}</div>
      <div style={{marginTop: 26, height: 12, width: "88%", borderRadius: 8, backgroundColor: "rgba(220,230,232,.16)"}} />
      <div style={{marginTop: 14, height: 12, width: "70%", borderRadius: 8, backgroundColor: "rgba(220,230,232,.11)"}} />
      <div style={{marginTop: 14, height: 12, width: "80%", borderRadius: 8, backgroundColor: "rgba(220,230,232,.13)"}} />
      <div style={{marginTop: 14, height: 12, width: "42%", borderRadius: 8, backgroundColor: "rgba(242,169,59,.30)"}} />
    </div>
  );
};

export const ProblemScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill>
      <CinematicBackdrop accent="amber" />
      <div style={{position: "absolute", left: 110, top: 180, width: 900}}>
        <Kicker color={COLORS.amber}>The operations gap</Kicker>
        <div style={{marginTop: 32}}>
          <Headline size={102} maxWidth={820}>
            The rule is buried.<br />
            <span style={{color: COLORS.silver}}>The source is lost.</span>
          </Headline>
        </div>
        <div style={{marginTop: 34}}>
          <SupportingCopy delay={32} maxWidth={760} color={COLORS.silver}>
            And a plausible answer can become a risky action before anyone sees the proof.
          </SupportingCopy>
        </div>
        <Interactive.Div
          name="Risk statement"
          style={{
            marginTop: 44,
            width: 710,
            padding: "20px 26px",
            borderRadius: 18,
            fontFamily: "Geist Variable",
            fontSize: 27,
            fontWeight: 660,
            color: COLORS.amber,
            backgroundColor: "rgba(242,169,59,.08)",
            outline: "1px solid rgba(242,169,59,.28)",
            opacity: interpolate(frame, [52, 70], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(frame, [52, 76], ["-24px 0px", "0px 0px"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          Unverified answer <span style={{margin: "0 14px", color: COLORS.muted}}>→</span> unsafe work
        </Interactive.Div>
      </div>
      <div style={{position: "absolute", left: 1090, top: 130, width: 720, height: 760}}>
        <FracturedDocument delay={12} x={86} y={44} rotate={-4} label="POLICY · REV 12" />
        <FracturedDocument delay={28} x={30} y={258} rotate={2} label="PROCEDURE · SECTION 8" />
        <FracturedDocument delay={44} x={130} y={472} rotate={-1} label="NOTICE · TIME SENSITIVE" />
        <div
          style={{
            position: "absolute",
            left: 420,
            top: 612,
            width: interpolate(frame, [70, 125], [0, 250], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
            height: 3,
            backgroundColor: COLORS.amber,
            boxShadow: `0 0 22px ${COLORS.amber}`,
          }}
        />
      </div>
      <SceneChrome chapter="Problem" chapterNumber="00" />
    </AbsoluteFill>
  );
};
