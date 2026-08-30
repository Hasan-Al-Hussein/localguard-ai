import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { COLORS, SCREENSHOTS } from "../constants";
import { CinematicBackdrop } from "../components/CinematicBackdrop";
import { Headline, Kicker } from "../components/Typography";
import { SceneChrome } from "../components/SceneChrome";

type NodeProps = {
  x: number;
  y: number;
  width: number;
  number: string;
  label: string;
  detail: string;
  accent: string;
  delay: number;
};

const PipelineNode: React.FC<NodeProps> = ({
  x,
  y,
  width,
  number,
  label,
  detail,
  accent,
  delay,
}) => {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width,
        minHeight: 132,
        padding: "22px 24px",
        borderRadius: 22,
        background:
          "linear-gradient(145deg, rgba(12,37,52,.96), rgba(5,20,30,.96))",
        outline: `1px solid ${accent}55`,
        boxShadow:
          "0 24px 70px rgba(0,0,0,.32), inset 0 1px 0 rgba(255,255,255,.07)",
        opacity: interpolate(frame, [delay, delay + 18], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
        translate: interpolate(
          frame,
          [delay, delay + 22],
          ["0px 34px", "0px 0px"],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          },
        ),
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 13 }}>
        <div
          style={{
            width: 34,
            height: 34,
            display: "grid",
            placeItems: "center",
            borderRadius: 12,
            backgroundColor: `${accent}22`,
            color: accent,
            fontFamily: "monospace",
            fontSize: 13,
            fontWeight: 800,
          }}
        >
          {number}
        </div>
        <div
          style={{
            fontFamily: "Manrope Variable",
            fontSize: 25,
            fontWeight: 740,
            color: COLORS.white,
          }}
        >
          {label}
        </div>
      </div>
      <div
        style={{
          marginTop: 14,
          fontFamily: "Geist Variable",
          fontSize: 18,
          lineHeight: 1.28,
          color: COLORS.muted,
        }}
      >
        {detail}
      </div>
    </div>
  );
};

export const PipelineScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill>
      <CinematicBackdrop accent="blue" />
      <Img
        name="Evaluation background"
        src={staticFile(SCREENSHOTS.evaluation)}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          objectPosition: "center top",
          opacity: 0.08,
          filter: "blur(7px) saturate(.7)",
          scale: 1.06,
        }}
      />
      <div style={{ position: "absolute", left: 110, top: 142 }}>
        <Kicker color={COLORS.blue}>Technical pipeline</Kicker>
        <div style={{ marginTop: 24 }}>
          <Headline size={84} maxWidth={1540}>
            One local chain of custody.
          </Headline>
        </div>
      </div>
      <svg
        width="1920"
        height="1080"
        viewBox="0 0 1920 1080"
        style={{ position: "absolute", inset: 0 }}
      >
        <defs>
          <linearGradient id="evidenceLine" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor={COLORS.blue} />
            <stop offset="0.6" stopColor={COLORS.mint} />
            <stop offset="1" stopColor={COLORS.amber} />
          </linearGradient>
        </defs>
        <path
          d="M220 512 H1675 M395 512 V710 M760 512 V710 M1125 512 V710 M1490 512 V710"
          stroke="rgba(220,230,232,.14)"
          strokeWidth="3"
          fill="none"
        />
        <path
          d="M220 512 H1675"
          stroke="url(#evidenceLine)"
          strokeWidth="4"
          fill="none"
          strokeLinecap="round"
          strokeDasharray="1500"
          strokeDashoffset={interpolate(frame, [30, 340], [1500, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          })}
        />
        <circle
          cx={interpolate(frame, [60, 480], [220, 1675], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          })}
          cy="512"
          r="10"
          fill={COLORS.mint}
          opacity={interpolate(frame, [50, 64, 480, 510], [0, 1, 1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })}
        />
      </svg>
      <PipelineNode
        x={105}
        y={420}
        width={245}
        number="01"
        label="Next.js"
        detail="Private reviewer workspace"
        accent={COLORS.blue}
        delay={40}
      />
      <PipelineNode
        x={380}
        y={420}
        width={250}
        number="02"
        label="FastAPI"
        detail="Authenticated request boundary"
        accent={COLORS.blue}
        delay={80}
      />
      <PipelineNode
        x={660}
        y={420}
        width={290}
        number="03"
        label="PostgreSQL"
        detail="pgvector evidence retrieval"
        accent={COLORS.mint}
        delay={120}
      />
      <PipelineNode
        x={980}
        y={420}
        width={290}
        number="04"
        label="Celery"
        detail="Local Ollama verification"
        accent={COLORS.mint}
        delay={160}
      />
      <PipelineNode
        x={1300}
        y={420}
        width={255}
        number="05"
        label="LangGraph"
        detail="Interrupt before action"
        accent={COLORS.mint}
        delay={200}
      />
      <PipelineNode
        x={1585}
        y={420}
        width={235}
        number="06"
        label="Human gate"
        detail="Evidence-bound decision"
        accent={COLORS.amber}
        delay={240}
      />
      <div
        style={{
          position: "absolute",
          left: 660,
          top: 700,
          width: 900,
          padding: "28px 34px",
          borderRadius: 24,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background:
            "linear-gradient(90deg, rgba(82,224,196,.15), rgba(79,140,255,.08))",
          outline: "1px solid rgba(82,224,196,.42)",
          boxShadow: `0 30px 100px rgba(0,0,0,.34), 0 0 70px ${COLORS.mint}18`,
          opacity: interpolate(frame, [300, 350], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
          scale: interpolate(frame, [300, 350], [0.92, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            output: "perceptual-scale",
          }),
        }}
      >
        <div>
          <div
            style={{
              fontFamily: "monospace",
              fontSize: 16,
              letterSpacing: 2.5,
              color: COLORS.mint,
            }}
          >
            07 · PERSISTED RESULT
          </div>
          <div
            style={{
              marginTop: 10,
              fontFamily: "Manrope Variable",
              fontSize: 34,
              fontWeight: 760,
              color: COLORS.white,
            }}
          >
            Exactly one workflow task
          </div>
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <span
            style={{
              padding: "12px 16px",
              borderRadius: 999,
              backgroundColor: "rgba(82,224,196,.13)",
              color: COLORS.mintSoft,
              fontFamily: "Geist Variable",
              fontSize: 18,
            }}
          >
            source attached
          </span>
          <span
            style={{
              padding: "12px 16px",
              borderRadius: 999,
              backgroundColor: "rgba(242,169,59,.12)",
              color: "#FFDCA7",
              fontFamily: "Geist Variable",
              fontSize: 18,
            }}
          >
            approval attached
          </span>
        </div>
      </div>
      <SceneChrome chapter="Architecture" chapterNumber="07" />
    </AbsoluteFill>
  );
};
