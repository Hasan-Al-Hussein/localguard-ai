import "./index.css";
import {Composition, Folder} from "remotion";
import {LocalGuardProductDemo} from "./Composition";
import {AnswerScene} from "./scenes/AnswerScene";
import {CloseScene} from "./scenes/CloseScene";
import {ExampleScene} from "./scenes/ExampleScene";
import {InputScene} from "./scenes/InputScene";
import {PipelineScene} from "./scenes/PipelineScene";
import {ProblemScene} from "./scenes/ProblemScene";
import {ProposalScene} from "./scenes/ProposalScene";
import {ResultScene} from "./scenes/ResultScene";
import {SolutionScene} from "./scenes/SolutionScene";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="LocalGuardProductDemo"
        component={LocalGuardProductDemo}
        durationInFrames={3300}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{showCaptions: true, narrationEnabled: true}}
      />
      <Folder name="Editable-scenes">
        <Composition id="SceneProblem" component={ProblemScene} durationInFrames={330} fps={30} width={1920} height={1080} />
        <Composition id="SceneSolution" component={SolutionScene} durationInFrames={330} fps={30} width={1920} height={1080} />
        <Composition id="SceneExample" component={ExampleScene} durationInFrames={240} fps={30} width={1920} height={1080} />
        <Composition id="SceneInput" component={InputScene} durationInFrames={240} fps={30} width={1920} height={1080} />
        <Composition id="SceneAnswer" component={AnswerScene} durationInFrames={570} fps={30} width={1920} height={1080} />
        <Composition id="SceneProposal" component={ProposalScene} durationInFrames={540} fps={30} width={1920} height={1080} />
        <Composition id="SceneResult" component={ResultScene} durationInFrames={450} fps={30} width={1920} height={1080} />
        <Composition id="ScenePipeline" component={PipelineScene} durationInFrames={420} fps={30} width={1920} height={1080} />
        <Composition id="SceneClose" component={CloseScene} durationInFrames={180} fps={30} width={1920} height={1080} />
      </Folder>
    </>
  );
};
