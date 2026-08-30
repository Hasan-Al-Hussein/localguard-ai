import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {COLORS} from "../constants";

type Props = {
  accent?: "mint" | "blue" | "amber";
  light?: boolean;
  grid?: boolean;
};

export const CinematicBackdrop: React.FC<Props> = ({
  accent = "mint",
  light = false,
  grid = true,
}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const accentColor =
    accent === "amber" ? COLORS.amber : accent === "blue" ? COLORS.blue : COLORS.mint;

  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        background: light
          ? "linear-gradient(135deg, #EEF5F6 0%, #F8FBFC 48%, #E9F7F4 100%)"
          : "linear-gradient(145deg, #061019 0%, #071925 52%, #041018 100%)",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: grid ? (light ? 0.16 : 0.12) : 0,
          backgroundImage: light
            ? "linear-gradient(rgba(10,48,72,.24) 1px, transparent 1px), linear-gradient(90deg, rgba(10,48,72,.24) 1px, transparent 1px)"
            : "linear-gradient(rgba(220,230,232,.16) 1px, transparent 1px), linear-gradient(90deg, rgba(220,230,232,.16) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          translate: interpolate(frame, [0, durationInFrames], ["0px 0px", "-24px -18px"], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 900,
          height: 900,
          right: -260,
          top: -330,
          borderRadius: 999,
          opacity: light ? 0.18 : 0.22,
          filter: "blur(90px)",
          backgroundColor: accentColor,
          scale: interpolate(frame, [0, durationInFrames], [0.92, 1.08], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
            output: "perceptual-scale",
          }),
          translate: interpolate(frame, [0, durationInFrames], ["0px 0px", "-36px 52px"], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 640,
          height: 640,
          left: -250,
          bottom: -320,
          borderRadius: 999,
          opacity: light ? 0.11 : 0.12,
          filter: "blur(80px)",
          backgroundColor: accent === "amber" ? COLORS.blue : COLORS.amber,
          translate: interpolate(frame, [0, durationInFrames], ["0px 0px", "50px -24px"], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at center, transparent 38%, rgba(2,9,14,.42) 100%), linear-gradient(90deg, rgba(255,255,255,.025), transparent 18%, transparent 82%, rgba(255,255,255,.018))",
          opacity: light ? 0.18 : 1,
        }}
      />
    </AbsoluteFill>
  );
};
