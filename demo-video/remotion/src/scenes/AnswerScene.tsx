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

const StatusCard: React.FC<{
  number: string;
  label: string;
  detail: string;
  accent: string;
}> = ({ number, label, detail, accent }) => {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 18,
        padding: "17px 22px",
        borderRadius: 18,
        backgroundColor: "rgba(4,18,27,.91)",
        outline: `1px solid ${accent}55`,
        boxShadow: "0 20px 60px rgba(0,0,0,.30)",
        opacity: interpolate(frame, [12, 28], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
      }}
    >
      <div
        style={{
          width: 42,
          height: 42,
          borderRadius: 14,
          display: "grid",
          placeItems: "center",
          backgroundColor: `${accent}22`,
          color: accent,
          fontFamily: "monospace",
          fontSize: 15,
          fontWeight: 800,
        }}
      >
        {number}
      </div>
      <div>
        <div
          style={{
            fontFamily: "Manrope Variable",
            fontSize: 24,
            fontWeight: 720,
            color: COLORS.white,
          }}
        >
          {label}
        </div>
        <div
          style={{
            marginTop: 3,
            fontFamily: "Geist Variable",
            fontSize: 17,
            color: COLORS.muted,
          }}
        >
          {detail}
        </div>
      </div>
    </div>
  );
};

export const AnswerScene: React.FC = () => {
  return (
    <AbsoluteFill>
      <CinematicBackdrop accent="blue" />
      <Sequence
        name="Question entered · real recording"
        durationInFrames={150}
        premountFor={30}
      >
        <Shot>
          <ProductFrame
            video="recordings/source-product-flow.webm"
            trimBefore={475}
            title="Ask LocalGuard · LocalGuard AI"
            route="/ask"
            width={1590}
            height={842}
            objectPosition="center top"
            enterFrom="bottom"
          />
        </Shot>
      </Sequence>
      <Sequence
        name="Evidence retrieval"
        from={125}
        durationInFrames={200}
        premountFor={30}
      >
        <Shot>
          <ProductFrame
            screenshot={SCREENSHOTS.queued}
            title="Ask LocalGuard · LocalGuard AI"
            route="/ask"
            width={1590}
            height={842}
            objectPosition="center center"
          />
        </Shot>
      </Sequence>
      <Sequence
        name="Cited answer"
        from={290}
        durationInFrames={330}
        premountFor={30}
      >
        <Shot>
          <ProductFrame
            screenshot={SCREENSHOTS.answer}
            title="Cited answer · LocalGuard AI"
            route="/ask"
            width={1590}
            height={842}
            objectPosition="center center"
          />
        </Shot>
      </Sequence>
      <Sequence
        name="Exact source proof"
        from={590}
        durationInFrames={250}
        premountFor={30}
      >
        <Shot>
          <ProductFrame
            screenshot={SCREENSHOTS.citation}
            title="Document evidence · LocalGuard AI"
            route="/documents/…?anchor=page%3A2"
            width={1590}
            height={842}
            objectPosition="center top"
          />
        </Shot>
      </Sequence>
      <div
        style={{
          position: "absolute",
          left: 102,
          top: 128,
          display: "flex",
          gap: 14,
          zIndex: 8,
        }}
      >
        <Sequence durationInFrames={200} layout="none">
          <StatusCard
            number="01"
            label="Ask"
            detail="A precise evidence question"
            accent={COLORS.blue}
          />
        </Sequence>
        <Sequence from={170} durationInFrames={240} layout="none">
          <StatusCard
            number="02"
            label="Retrieve"
            detail="Sufficiency checked locally"
            accent={COLORS.mint}
          />
        </Sequence>
        <Sequence from={410} durationInFrames={430} layout="none">
          <StatusCard
            number="03"
            label="Cite"
            detail="Page 2 · offsets 767–889"
            accent={COLORS.mint}
          />
        </Sequence>
      </div>
      <SceneChrome chapter="Answer + proof" chapterNumber="04" />
    </AbsoluteFill>
  );
};
