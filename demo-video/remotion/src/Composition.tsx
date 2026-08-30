import {AbsoluteFill, Series} from "remotion";
import {CaptionLayer} from "./components/CaptionLayer";
import {NarrationTracks} from "./components/NarrationTracks";
import type {DemoProps} from "./constants";
import {AnswerScene} from "./scenes/AnswerScene";
import {CloseScene} from "./scenes/CloseScene";
import {ExampleScene} from "./scenes/ExampleScene";
import {InputScene} from "./scenes/InputScene";
import {PipelineScene} from "./scenes/PipelineScene";
import {ProblemScene} from "./scenes/ProblemScene";
import {ProposalScene} from "./scenes/ProposalScene";
import {ResultScene} from "./scenes/ResultScene";
import {SolutionScene} from "./scenes/SolutionScene";

export const LocalGuardProductDemo: React.FC<DemoProps> = ({showCaptions, narrationEnabled}) => {
  return (
    <AbsoluteFill style={{backgroundColor: "#07121C"}}>
      <Series>
        <Series.Sequence name="00 · Problem" durationInFrames={330}><ProblemScene /></Series.Sequence>
        <Series.Sequence name="01 · Solution" durationInFrames={330}><SolutionScene /></Series.Sequence>
        <Series.Sequence name="02 · Example" durationInFrames={240}><ExampleScene /></Series.Sequence>
        <Series.Sequence name="03 · Input" durationInFrames={240}><InputScene /></Series.Sequence>
        <Series.Sequence name="04 · Answer + proof" durationInFrames={570}><AnswerScene /></Series.Sequence>
        <Series.Sequence name="05 · Action proposal" durationInFrames={540}><ProposalScene /></Series.Sequence>
        <Series.Sequence name="06 · Approved result" durationInFrames={450}><ResultScene /></Series.Sequence>
        <Series.Sequence name="07 · Architecture" durationInFrames={420}><PipelineScene /></Series.Sequence>
        <Series.Sequence name="08 · Close" durationInFrames={180}><CloseScene /></Series.Sequence>
      </Series>
      {narrationEnabled ? <NarrationTracks /> : null}
      {showCaptions ? <CaptionLayer /> : null}
    </AbsoluteFill>
  );
};
