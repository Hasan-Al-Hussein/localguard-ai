import {
  AbsoluteFill,
  Easing,
  interpolate,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { COLORS, SCREENSHOTS } from "../constants";
import { CinematicBackdrop } from "../components/CinematicBackdrop";
import { ProductFrame } from "../components/ProductFrame";
import { SceneChrome } from "../components/SceneChrome";

const Shot: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity:
          interpolate(frame, [0, 14], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }) *
          interpolate(
            frame,
            [durationInFrames - 14, durationInFrames],
            [1, 0],
            {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            },
          ),
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

export const ProposalScene: React.FC = () => {
  const frame = useCurrentFrame();
  const pending = frame >= 340;

  return (
    <AbsoluteFill>
      <CinematicBackdrop accent="amber" light />
      <Sequence name="Action request" durationInFrames={370} premountFor={30}>
        <Shot>
          <ProductFrame
            screenshot={SCREENSHOTS.action}
            title="Propose an action · LocalGuard AI"
            route="/ask"
            width={1590}
            height={842}
            objectPosition="center center"
            enterFrom="bottom"
          />
        </Shot>
      </Sequence>
      <Sequence
        name="Pending approval"
        from={340}
        durationInFrames={440}
        premountFor={30}
      >
        <Shot>
          <ProductFrame
            screenshot={SCREENSHOTS.approval}
            title="Approval review · LocalGuard AI"
            route="/approvals/…"
            width={1590}
            height={842}
            objectPosition="center center"
          />
        </Shot>
      </Sequence>
      <div
        style={{
          position: "absolute",
          left: 108,
          top: 126,
          width: 520,
          padding: "24px 28px",
          borderRadius: 22,
          backgroundColor: "rgba(5,22,32,.95)",
          outline: `1px solid ${pending ? COLORS.amber : COLORS.mint}66`,
          boxShadow: "0 28px 86px rgba(4,15,22,.36)",
          opacity: interpolate(frame, [18, 38], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 16,
            letterSpacing: 2.4,
            color: pending ? COLORS.amber : COLORS.mint,
          }}
        >
          {pending ? "HUMAN GATE · PENDING" : "03 · PROPOSE"}
        </div>
        <div
          style={{
            marginTop: 14,
            fontFamily: "Manrope Variable",
            fontSize: 36,
            lineHeight: 1.08,
            fontWeight: 740,
            color: COLORS.white,
          }}
        >
          {pending
            ? "Evidence is ready. Execution is not."
            : "Notice received at 09:00 UTC."}
        </div>
        <div
          style={{ marginTop: 18, display: "flex", gap: 10, flexWrap: "wrap" }}
        >
          <span
            style={{
              padding: "9px 13px",
              borderRadius: 999,
              backgroundColor: "rgba(82,224,196,.11)",
              color: COLORS.mintSoft,
              fontFamily: "Geist Variable",
              fontSize: 17,
            }}
          >
            Service Desk
          </span>
          <span
            style={{
              padding: "9px 13px",
              borderRadius: 999,
              backgroundColor: "rgba(242,169,59,.12)",
              color: "#FFDCA7",
              fontFamily: "Geist Variable",
              fontSize: 17,
            }}
          >
            High priority
          </span>
          <span
            style={{
              padding: "9px 13px",
              borderRadius: 999,
              backgroundColor: "rgba(79,140,255,.12)",
              color: "#C6D7FF",
              fontFamily: "Geist Variable",
              fontSize: 17,
            }}
          >
            Due 10:00 UTC
          </span>
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          right: 112,
          top: 130,
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "18px 24px",
          borderRadius: 20,
          backgroundColor: "rgba(5,22,32,.94)",
          outline: "1px solid rgba(242,169,59,.42)",
          boxShadow: "0 28px 86px rgba(4,15,22,.30)",
          opacity: interpolate(frame, [370, 402], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
          scale: interpolate(frame, [370, 402], [0.88, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
        }}
      >
        <span
          style={{
            fontFamily: "Manrope Variable",
            fontSize: 48,
            fontWeight: 780,
            color: COLORS.amber,
          }}
        >
          0
        </span>
        <span
          style={{
            fontFamily: "Geist Variable",
            fontSize: 20,
            lineHeight: 1.12,
            color: COLORS.silver,
          }}
        >
          tasks before
          <br />
          approval
        </span>
      </div>
      <SceneChrome chapter="Action proposal" chapterNumber="05" light />
    </AbsoluteFill>
  );
};
