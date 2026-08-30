import {Audio} from "@remotion/media";
import {Sequence, staticFile} from "remotion";

/** Each chapter is isolated so an editor can replace or retime one voice segment. */
export const NarrationTracks: React.FC = () => {
  return (
    <>
      <Sequence name="Narration · Problem" durationInFrames={330} premountFor={30}>
        <Audio src={staticFile("audio/problem.mp3")} />
      </Sequence>
      <Sequence name="Narration · Solution" from={330} durationInFrames={330} premountFor={30}>
        <Audio src={staticFile("audio/solution.mp3")} />
      </Sequence>
      <Sequence name="Narration · Example" from={660} durationInFrames={240} premountFor={30}>
        <Audio src={staticFile("audio/example.mp3")} />
      </Sequence>
      <Sequence name="Narration · Input" from={900} durationInFrames={240} premountFor={30}>
        <Audio src={staticFile("audio/input.mp3")} />
      </Sequence>
      <Sequence name="Narration · Answer" from={1140} durationInFrames={570} premountFor={30}>
        <Audio src={staticFile("audio/answer.mp3")} />
      </Sequence>
      <Sequence name="Narration · Proposal" from={1710} durationInFrames={540} premountFor={30}>
        <Audio src={staticFile("audio/proposal.mp3")} />
      </Sequence>
      <Sequence name="Narration · Result" from={2250} durationInFrames={450} premountFor={30}>
        <Audio src={staticFile("audio/result.mp3")} />
      </Sequence>
      <Sequence name="Narration · Pipeline" from={2700} durationInFrames={420} premountFor={30}>
        <Audio src={staticFile("audio/pipeline.mp3")} playbackRate={1.04} />
      </Sequence>
      <Sequence name="Narration · Close" from={3120} durationInFrames={180} premountFor={30}>
        <Audio src={staticFile("audio/close.mp3")} />
      </Sequence>
    </>
  );
};
