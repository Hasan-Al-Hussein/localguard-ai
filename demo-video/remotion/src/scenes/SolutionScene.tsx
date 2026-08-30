import {AbsoluteFill, Easing, Interactive, interpolate, useCurrentFrame} from "remotion";
import {COLORS, SCREENSHOTS} from "../constants";
import {BrandMark} from "../components/BrandMark";
import {CinematicBackdrop} from "../components/CinematicBackdrop";
import {PipelineRail} from "../components/PipelineRail";
import {ProductFrame} from "../components/ProductFrame";
import {Headline, Kicker, SupportingCopy} from "../components/Typography";
import {SceneChrome} from "../components/SceneChrome";

export const SolutionScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill>
      <CinematicBackdrop accent="mint" />
      <div style={{position: "absolute", left: 110, top: 158, width: 860, zIndex: 3}}>
        <Kicker>Local-first evidence workspace</Kicker>
        <div style={{marginTop: 26}}>
          <Headline size={104} maxWidth={850}>
            Evidence<br />
            <span style={{color: COLORS.mint}}>before action.</span>
          </Headline>
        </div>
        <div style={{marginTop: 30}}>
          <SupportingCopy delay={28} maxWidth={760}>
            Indexed files become inspectable answers. Every consequential step stops at a human gate.
          </SupportingCopy>
        </div>
        <div
          style={{
            marginTop: 40,
            opacity: interpolate(frame, [46, 62], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          <BrandMark size={78} label />
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 940,
          top: 138,
          opacity: interpolate(frame, [26, 48], [0.28, 0.82], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          scale: 0.62,
          transformOrigin: "top left",
        }}
      >
        <ProductFrame screenshot={SCREENSHOTS.overview} title="Overview · LocalGuard AI" route="/overview" width={1450} height={900} />
      </div>
      <Interactive.Div
        name="Evidence pipeline rail"
        style={{
          position: "absolute",
          left: 110,
          right: 110,
          bottom: 250,
          opacity: interpolate(frame, [58, 76], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      >
        <PipelineRail compact />
      </Interactive.Div>
      <SceneChrome chapter="Solution" chapterNumber="01" />
    </AbsoluteFill>
  );
};
