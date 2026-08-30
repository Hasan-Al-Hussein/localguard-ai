import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {COLORS} from "../constants";
import {BrandMark} from "./BrandMark";

type Props = {
  chapter: string;
  chapterNumber: string;
  light?: boolean;
};

export const SceneChrome: React.FC<Props> = ({chapter, chapterNumber, light = false}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();

  return (
    <AbsoluteFill style={{pointerEvents: "none"}}>
      <div style={{position: "absolute", left: 80, top: 54}}>
        <BrandMark size={52} animate={false} />
      </div>
      <div
        style={{
          position: "absolute",
          right: 82,
          top: 61,
          display: "flex",
          alignItems: "center",
          gap: 14,
          fontFamily: "Geist Variable",
          fontSize: 17,
          letterSpacing: 2.4,
          textTransform: "uppercase",
          color: light ? COLORS.ink : COLORS.silver,
        }}
      >
        <span style={{fontFamily: "monospace", color: COLORS.mint}}>{chapterNumber}</span>
        <span style={{width: 38, height: 1, backgroundColor: light ? "rgba(10,48,72,.32)" : "rgba(220,230,232,.28)"}} />
        {chapter}
      </div>
      <div
        style={{
          position: "absolute",
          left: 80,
          right: 80,
          bottom: 54,
          height: 3,
          borderRadius: 9,
          overflow: "hidden",
          backgroundColor: light ? "rgba(10,48,72,.12)" : "rgba(220,230,232,.10)",
        }}
      >
        <div
          style={{
            width: `${interpolate(frame, [0, durationInFrames - 1], [0, 100], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })}%`,
            height: "100%",
            background: `linear-gradient(90deg, ${COLORS.mint}, ${COLORS.blue})`,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
