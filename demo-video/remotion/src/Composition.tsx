import { AbsoluteFill, Series } from "remotion";
import { CaptionLayer } from "./components/CaptionLayer";
import { NarrationTracks } from "./components/NarrationTracks";
import { SCENE_DURATIONS, type DemoProps } from "./constants";
import { AnswerScene } from "./scenes/AnswerScene";
import { CloseScene } from "./scenes/CloseScene";
import { ExampleScene } from "./scenes/ExampleScene";
import { InputScene } from "./scenes/InputScene";
import { PipelineScene } from "./scenes/PipelineScene";
import { ProblemScene } from "./scenes/ProblemScene";
import { ProposalScene } from "./scenes/ProposalScene";
import { ResultScene } from "./scenes/ResultScene";
import { SolutionScene } from "./scenes/SolutionScene";

export const LocalGuardProductDemo: React.FC<DemoProps> = ({
  showCaptions,
  narrationEnabled,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#07121C" }}>
      <Series>
        <Series.Sequence
          name="00 · Problem"
          durationInFrames={SCENE_DURATIONS.problem}
        >
          <ProblemScene />
        </Series.Sequence>
        <Series.Sequence
          name="01 · Solution"
          durationInFrames={SCENE_DURATIONS.solution}
        >
          <SolutionScene />
        </Series.Sequence>
        <Series.Sequence
          name="02 · Example"
          durationInFrames={SCENE_DURATIONS.example}
        >
          <ExampleScene />
        </Series.Sequence>
        <Series.Sequence
          name="03 · Input"
          durationInFrames={SCENE_DURATIONS.input}
        >
          <InputScene />
        </Series.Sequence>
        <Series.Sequence
          name="04 · Answer + proof"
          durationInFrames={SCENE_DURATIONS.answer}
        >
          <AnswerScene />
        </Series.Sequence>
        <Series.Sequence
          name="05 · Action proposal"
          durationInFrames={SCENE_DURATIONS.proposal}
        >
          <ProposalScene />
        </Series.Sequence>
        <Series.Sequence
          name="06 · Approved result"
          durationInFrames={SCENE_DURATIONS.result}
        >
          <ResultScene />
        </Series.Sequence>
        <Series.Sequence
          name="07 · Architecture"
          durationInFrames={SCENE_DURATIONS.pipeline}
        >
          <PipelineScene />
        </Series.Sequence>
        <Series.Sequence
          name="08 · Close"
          durationInFrames={SCENE_DURATIONS.close}
        >
          <CloseScene />
        </Series.Sequence>
      </Series>
      {narrationEnabled ? <NarrationTracks /> : null}
      {showCaptions ? <CaptionLayer /> : null}
    </AbsoluteFill>
  );
};
