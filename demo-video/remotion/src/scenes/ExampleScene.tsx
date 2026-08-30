import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from "remotion";
import {COLORS, SCREENSHOTS} from "../constants";
import {CinematicBackdrop} from "../components/CinematicBackdrop";
import {ProductFrame} from "../components/ProductFrame";
import {Headline, Kicker} from "../components/Typography";
import {SceneChrome} from "../components/SceneChrome";

export const ExampleScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill>
      <CinematicBackdrop accent="blue" />
      <div style={{position: "absolute", left: 108, top: 152, width: 650, zIndex: 3}}>
        <Kicker color={COLORS.blue}>One concrete example</Kicker>
        <div style={{marginTop: 28}}>
          <Headline size={92} maxWidth={640}>
            Vendor<br />offboarding.
          </Headline>
        </div>
        <div
          style={{
            marginTop: 42,
            padding: "30px 32px",
            borderRadius: 25,
            background: "linear-gradient(145deg, rgba(13,43,61,.94), rgba(7,23,34,.94))",
            outline: "1px solid rgba(82,224,196,.32)",
            boxShadow: "0 30px 90px rgba(0,0,0,.3)",
            opacity: interpolate(frame, [26, 44], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
            translate: interpolate(frame, [26, 48], ["0px 32px", "0px 0px"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          <div style={{fontFamily: "Geist Variable", fontSize: 18, letterSpacing: 2.8, textTransform: "uppercase", color: COLORS.mint}}>
            Synthetic policy obligation
          </div>
          <div style={{marginTop: 18, fontFamily: "Manrope Variable", fontSize: 43, lineHeight: 1.14, fontWeight: 700, color: COLORS.white}}>
            Disable the vendor account within one hour.
          </div>
          <div style={{marginTop: 24, display: "flex", gap: 12}}>
            <span style={{padding: "10px 14px", borderRadius: 999, backgroundColor: "rgba(79,140,255,.12)", color: "#BFD2FF", fontFamily: "monospace", fontSize: 16}}>Notice 09:00 UTC</span>
            <span style={{padding: "10px 14px", borderRadius: 999, backgroundColor: "rgba(242,169,59,.12)", color: "#FFDCA7", fontFamily: "monospace", fontSize: 16}}>Due 10:00 UTC</span>
          </div>
        </div>
      </div>
      <div style={{position: "absolute", left: 785, top: 145, scale: 0.71, transformOrigin: "top left"}}>
        <ProductFrame screenshot={SCREENSHOTS.document} title="Documents · LocalGuard AI" route="/documents" width={1470} height={920} objectPosition="center top" />
      </div>
      <div
        style={{
          position: "absolute",
          left: 1340,
          top: 416,
          width: 280,
          height: 280,
          rotate: "45deg",
          borderRadius: 40,
          outline: "2px solid rgba(82,224,196,.32)",
          boxShadow: `0 0 70px ${COLORS.mint}22, inset 0 0 60px rgba(82,224,196,.08)`,
          opacity: interpolate(frame, [45, 80], [0, 0.8], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          scale: interpolate(frame, [45, 80], [0.72, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
        }}
      />
      <SceneChrome chapter="Example" chapterNumber="02" />
    </AbsoluteFill>
  );
};
