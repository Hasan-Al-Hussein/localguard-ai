import {parseSrt} from "@remotion/captions";
import type {Caption} from "@remotion/captions";
import {useCallback, useEffect, useState} from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  staticFile,
  useCurrentFrame,
  useDelayRender,
  useVideoConfig,
} from "remotion";
import {COLORS} from "../constants";

export const CaptionLayer: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const [captions, setCaptions] = useState<Caption[] | null>(null);
  const {delayRender, continueRender, cancelRender} = useDelayRender();
  const [handle] = useState(() => delayRender("Load LocalGuard captions"));

  const loadCaptions = useCallback(async () => {
    try {
      const response = await fetch(staticFile("captions/product-demo.srt"));
      if (!response.ok) {
        throw new Error(`Unable to load captions: HTTP ${response.status}`);
      }
      const input = await response.text();
      const {captions: parsed} = parseSrt({input});
      setCaptions(parsed);
      continueRender(handle);
    } catch (error) {
      cancelRender(error instanceof Error ? error : new Error(String(error)));
    }
  }, [cancelRender, continueRender, handle]);

  useEffect(() => {
    loadCaptions();
  }, [loadCaptions]);

  if (!captions) {
    return null;
  }

  const currentMs = (frame / fps) * 1000;
  const cue = captions.find((item) => currentMs >= item.startMs && currentMs < item.endMs);

  if (!cue) {
    return null;
  }

  const localFrame = frame - (cue.startMs / 1000) * fps;
  const remainingFrames = ((cue.endMs - currentMs) / 1000) * fps;

  return (
    <AbsoluteFill style={{pointerEvents: "none", justifyContent: "flex-end", alignItems: "center"}}>
      <div
        style={{
          maxWidth: 1500,
          marginBottom: 100,
          padding: "16px 28px 18px",
          borderRadius: 18,
          backgroundColor: "rgba(4,16,24,.88)",
          outline: "1px solid rgba(189,248,237,.24)",
          boxShadow: "0 20px 60px rgba(0,0,0,.32), inset 0 1px 0 rgba(255,255,255,.08)",
          backdropFilter: "blur(18px)",
          opacity:
            interpolate(localFrame, [0, 8], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }) *
            interpolate(remainingFrames, [0, 7], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          translate: interpolate(localFrame, [0, 10], ["0px 18px", "0px 0px"], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
          fontFamily: "Geist Variable",
          fontSize: 38,
          lineHeight: 1.22,
          fontWeight: 590,
          textAlign: "center",
          whiteSpace: "pre-line",
          color: COLORS.white,
        }}
      >
        {cue.text.trim()}
      </div>
    </AbsoluteFill>
  );
};
