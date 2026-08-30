import {AbsoluteFill, Easing, interpolate, Sequence, useCurrentFrame, useVideoConfig} from "remotion";
import {COLORS, SCREENSHOTS} from "../constants";
import {CinematicBackdrop} from "../components/CinematicBackdrop";
import {ProductFrame} from "../components/ProductFrame";
import {SceneChrome} from "../components/SceneChrome";

const Shot: React.FC<{children: React.ReactNode}> = ({children}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();

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
          interpolate(frame, [durationInFrames - 14, durationInFrames], [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

export const ResultScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill>
      <CinematicBackdrop accent="mint" />
      <Sequence name="Reviewer approval" durationInFrames={165} premountFor={30}>
        <Shot>
          <ProductFrame
            screenshot={SCREENSHOTS.approval}
            title="Approval review · LocalGuard AI"
            route="/approvals/…"
            width={1590}
            height={842}
            objectPosition="center center"
            enterFrom="bottom"
          />
        </Shot>
      </Sequence>
      <Sequence name="Task created once" from={140} durationInFrames={190} premountFor={30}>
        <Shot>
          <ProductFrame screenshot={SCREENSHOTS.task} title="Workflow task · LocalGuard AI" route="/tasks/…" width={1590} height={842} objectPosition="center center" />
        </Shot>
      </Sequence>
      <Sequence name="Causal audit trail" from={305} durationInFrames={145} premountFor={30}>
        <Shot>
          <ProductFrame screenshot={SCREENSHOTS.audit} title="Audit log · LocalGuard AI" route="/audit" width={1590} height={842} objectPosition="center center" />
        </Shot>
      </Sequence>
      <div
        style={{
          position: "absolute",
          left: 102,
          top: 126,
          display: "flex",
          alignItems: "center",
          gap: 18,
          padding: "20px 26px",
          borderRadius: 20,
          backgroundColor: "rgba(4,18,27,.93)",
          outline: "1px solid rgba(82,224,196,.48)",
          boxShadow: "0 24px 70px rgba(0,0,0,.32)",
          opacity: interpolate(frame, [126, 158], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
          scale: interpolate(frame, [126, 158], [0.86, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
        }}
      >
        <div style={{width: 50, height: 50, borderRadius: 999, display: "grid", placeItems: "center", backgroundColor: COLORS.mint, color: COLORS.obsidian, fontFamily: "Manrope Variable", fontSize: 28, fontWeight: 820}}>1</div>
        <div>
          <div style={{fontFamily: "Manrope Variable", fontSize: 29, fontWeight: 740, color: COLORS.white}}>One task. Created once.</div>
          <div style={{marginTop: 4, fontFamily: "Geist Variable", fontSize: 18, color: COLORS.muted}}>Approval provenance remains attached.</div>
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          right: 110,
          top: 140,
          fontFamily: "monospace",
          fontSize: 16,
          letterSpacing: 1.2,
          color: COLORS.mint,
          opacity: interpolate(frame, [300, 330], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        request → decision → execution
      </div>
      <SceneChrome chapter="Approved result" chapterNumber="06" />
    </AbsoluteFill>
  );
};
