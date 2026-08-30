import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from "remotion";
import {COLORS, SCREENSHOTS} from "../constants";
import {CinematicBackdrop} from "../components/CinematicBackdrop";
import {ProductFrame} from "../components/ProductFrame";
import {SceneChrome} from "../components/SceneChrome";

export const InputScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill>
      <CinematicBackdrop accent="mint" light />
      <div style={{position: "absolute", left: 165, top: 105}}>
        <ProductFrame
          screenshot={SCREENSHOTS.document}
          title="Documents · LocalGuard AI"
          route="/documents"
          width={1590}
          height={840}
          objectPosition="center top"
          enterFrom="bottom"
        />
      </div>
      <div
        style={{
          position: "absolute",
          left: 112,
          top: 142,
          width: 450,
          padding: "26px 28px",
          borderRadius: 22,
          backgroundColor: "rgba(5,22,32,.94)",
          outline: "1px solid rgba(82,224,196,.40)",
          boxShadow: "0 28px 86px rgba(4,15,22,.36)",
          opacity: interpolate(frame, [32, 50], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
          translate: interpolate(frame, [32, 54], ["-34px 0px", "0px 0px"], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      >
        <div style={{fontFamily: "monospace", fontSize: 16, letterSpacing: 2.4, color: COLORS.mint}}>01 · INPUT</div>
        <div style={{marginTop: 16, fontFamily: "Manrope Variable", fontSize: 38, lineHeight: 1.05, fontWeight: 740, color: COLORS.white}}>A stable evidence revision.</div>
        <div style={{marginTop: 18, fontFamily: "Geist Variable", fontSize: 22, lineHeight: 1.35, color: COLORS.silver}}>
          PDF pages are indexed locally while the immutable source revision remains visible.
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 740,
          top: 480,
          width: interpolate(frame, [46, 90], [0, 610], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
          height: 4,
          borderRadius: 9,
          backgroundColor: COLORS.mint,
          boxShadow: `0 0 22px ${COLORS.mint}`,
        }}
      />
      <SceneChrome chapter="Input" chapterNumber="03" light />
    </AbsoluteFill>
  );
};
