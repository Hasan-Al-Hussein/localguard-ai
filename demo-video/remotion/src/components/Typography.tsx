import {Easing, Interactive, interpolate, useCurrentFrame} from "remotion";
import {COLORS} from "../constants";

export const Kicker: React.FC<{children: React.ReactNode; color?: string; delay?: number}> = ({
  children,
  color = COLORS.mint,
  delay = 0,
}) => {
  const frame = useCurrentFrame();

  return (
    <Interactive.Div
      name="Scene kicker"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        fontFamily: "Geist Variable",
        fontSize: 19,
        fontWeight: 720,
        letterSpacing: 4.2,
        textTransform: "uppercase",
        color,
        opacity: interpolate(frame, [delay, delay + 14], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
        translate: interpolate(frame, [delay, delay + 18], ["0px 18px", "0px 0px"], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
      }}
    >
      <span style={{width: 28, height: 2, backgroundColor: color}} />
      {children}
    </Interactive.Div>
  );
};

export const Headline: React.FC<{
  children: React.ReactNode;
  delay?: number;
  size?: number;
  maxWidth?: number;
  color?: string;
}> = ({children, delay = 8, size = 96, maxWidth = 1120, color = COLORS.white}) => {
  const frame = useCurrentFrame();

  return (
    <Interactive.Div
      name="Scene headline"
      style={{
        maxWidth,
        fontFamily: "Manrope Variable",
        fontSize: size,
        lineHeight: 0.99,
        letterSpacing: -5,
        fontWeight: 760,
        color,
        opacity: interpolate(frame, [delay, delay + 18], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
        translate: interpolate(frame, [delay, delay + 22], ["0px 42px", "0px 0px"], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
      }}
    >
      {children}
    </Interactive.Div>
  );
};

export const SupportingCopy: React.FC<{
  children: React.ReactNode;
  delay?: number;
  maxWidth?: number;
  color?: string;
}> = ({children, delay = 20, maxWidth = 900, color = COLORS.muted}) => {
  const frame = useCurrentFrame();

  return (
    <Interactive.Div
      name="Supporting copy"
      style={{
        maxWidth,
        fontFamily: "Geist Variable",
        fontSize: 34,
        lineHeight: 1.35,
        fontWeight: 440,
        color,
        opacity: interpolate(frame, [delay, delay + 18], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
        translate: interpolate(frame, [delay, delay + 20], ["0px 26px", "0px 0px"], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
      }}
    >
      {children}
    </Interactive.Div>
  );
};
