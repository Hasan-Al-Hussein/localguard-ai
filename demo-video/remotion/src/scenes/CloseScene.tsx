import {AbsoluteFill, Easing, Img, Interactive, interpolate, staticFile, useCurrentFrame} from "remotion";
import {COLORS} from "../constants";
import {BrandMark} from "../components/BrandMark";
import {CinematicBackdrop} from "../components/CinematicBackdrop";

export const CloseScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill>
      <CinematicBackdrop accent="mint" grid={false} />
      <Img
        name="LocalGuard evidence vault art"
        src={staticFile("brand/evidence-vault-hero.png")}
        style={{
          position: "absolute",
          right: -40,
          top: -10,
          width: 1050,
          height: 1100,
          objectFit: "cover",
          objectPosition: "center",
          opacity: interpolate(frame, [0, 36], [0, 0.48], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
          scale: interpolate(frame, [0, 179], [1.08, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
          maskImage: "linear-gradient(90deg, transparent 0%, black 28%, black 100%)",
        }}
      />
      <div style={{position: "absolute", left: 140, top: 170, width: 1050}}>
        <BrandMark size={96} label />
        <Interactive.Div
          name="Final value statement"
          style={{
            marginTop: 56,
            fontFamily: "Manrope Variable",
            fontSize: 112,
            lineHeight: 0.96,
            letterSpacing: -5.8,
            fontWeight: 780,
            color: COLORS.white,
            opacity: interpolate(frame, [12, 32], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
            translate: interpolate(frame, [12, 36], ["0px 46px", "0px 0px"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          Evidence<br />
          <span style={{color: COLORS.mint}}>before action.</span>
        </Interactive.Div>
        <Interactive.Div
          name="Final product description"
          style={{
            marginTop: 34,
            maxWidth: 900,
            fontFamily: "Geist Variable",
            fontSize: 34,
            lineHeight: 1.35,
            color: COLORS.silver,
            opacity: interpolate(frame, [30, 52], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          Source-backed answers. Reviewable work. Local-first by design.
        </Interactive.Div>
        <div
          style={{
            marginTop: 46,
            display: "inline-flex",
            alignItems: "center",
            gap: 18,
            padding: "17px 24px",
            borderRadius: 18,
            backgroundColor: "rgba(82,224,196,.10)",
            outline: "1px solid rgba(82,224,196,.34)",
            boxShadow: `0 20px 70px ${COLORS.mint}18`,
            opacity: interpolate(frame, [48, 70], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          <span style={{width: 10, height: 10, borderRadius: 999, backgroundColor: COLORS.mint, boxShadow: `0 0 18px ${COLORS.mint}`}} />
          <span style={{fontFamily: "monospace", fontSize: 22, color: COLORS.mintSoft}}>github.com/Hasan-Al-Hussein/localguard-ai</span>
        </div>
      </div>
      <div style={{position: "absolute", left: 140, bottom: 250, fontFamily: "Geist Variable", fontSize: 18, letterSpacing: 2.5, textTransform: "uppercase", color: COLORS.muted}}>
        LocalGuard AI · Local processing · Human controlled
      </div>
    </AbsoluteFill>
  );
};
