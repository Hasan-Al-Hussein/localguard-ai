import { Audio } from "@remotion/media";
import { Sequence, staticFile } from "remotion";
import { SCENE_DURATIONS, SCENE_STARTS } from "../constants";

const narrationScenes = [
  { id: "problem", label: "Problem" },
  { id: "solution", label: "Solution" },
  { id: "example", label: "Example" },
  { id: "input", label: "Input" },
  { id: "answer", label: "Answer" },
  { id: "proposal", label: "Proposal" },
  { id: "result", label: "Result" },
  { id: "pipeline", label: "Pipeline" },
  { id: "close", label: "Close" },
] as const;

/** Each chapter is isolated so an editor can replace or retime one voice segment. */
export const NarrationTracks: React.FC = () => {
  return (
    <>
      {narrationScenes.map(({ id, label }) => (
        <Sequence
          key={id}
          name={`Narration · ${label}`}
          from={SCENE_STARTS[id]}
          durationInFrames={SCENE_DURATIONS[id]}
          premountFor={30}
        >
          <Audio src={staticFile(`audio/${id}.mp3`)} />
        </Sequence>
      ))}
    </>
  );
};
