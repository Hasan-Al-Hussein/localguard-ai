import "./index.css";
import { Composition, Folder } from "remotion";
import { LocalGuardProductDemo } from "./Composition";
import { AnswerScene } from "./scenes/AnswerScene";
import { CloseScene } from "./scenes/CloseScene";
import { ExampleScene } from "./scenes/ExampleScene";
import { InputScene } from "./scenes/InputScene";
import { PipelineScene } from "./scenes/PipelineScene";
import { ProblemScene } from "./scenes/ProblemScene";
import { ProposalScene } from "./scenes/ProposalScene";
import { ResultScene } from "./scenes/ResultScene";
import { SolutionScene } from "./scenes/SolutionScene";
import {
  DURATION_IN_FRAMES,
  FPS,
  HEIGHT,
  SCENE_DURATIONS,
  WIDTH,
} from "./constants";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="LocalGuardProductDemo"
        component={LocalGuardProductDemo}
        durationInFrames={DURATION_IN_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        defaultProps={{ showCaptions: true, narrationEnabled: true }}
      />
      <Folder name="Editable-scenes">
        <Composition
          id="SceneProblem"
          component={ProblemScene}
          durationInFrames={SCENE_DURATIONS.problem}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="SceneSolution"
          component={SolutionScene}
          durationInFrames={SCENE_DURATIONS.solution}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="SceneExample"
          component={ExampleScene}
          durationInFrames={SCENE_DURATIONS.example}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="SceneInput"
          component={InputScene}
          durationInFrames={SCENE_DURATIONS.input}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="SceneAnswer"
          component={AnswerScene}
          durationInFrames={SCENE_DURATIONS.answer}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="SceneProposal"
          component={ProposalScene}
          durationInFrames={SCENE_DURATIONS.proposal}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="SceneResult"
          component={ResultScene}
          durationInFrames={SCENE_DURATIONS.result}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="ScenePipeline"
          component={PipelineScene}
          durationInFrames={SCENE_DURATIONS.pipeline}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
        <Composition
          id="SceneClose"
          component={CloseScene}
          durationInFrames={SCENE_DURATIONS.close}
          fps={FPS}
          width={WIDTH}
          height={HEIGHT}
        />
      </Folder>
    </>
  );
};
