import {Video} from "@remotion/media";
import {Easing, Img, interpolate, staticFile, useCurrentFrame} from "remotion";
import {COLORS} from "../constants";

type Props = {
  screenshot?: string;
  video?: string;
  trimBefore?: number;
  title: string;
  route: string;
  width?: number;
  height?: number;
  objectPosition?: string;
  enterFrom?: "left" | "right" | "bottom";
  zoom?: number;
};

export const ProductFrame: React.FC<Props> = ({
  screenshot,
  video,
  trimBefore = 0,
  title,
  route,
  width = 1500,
  height = 830,
  objectPosition = "center top",
  enterFrom = "right",
  zoom = 1,
}) => {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        width,
        height,
        borderRadius: 30,
        overflow: "hidden",
        backgroundColor: "rgba(5,17,26,.96)",
        outline: "1px solid rgba(189,248,237,.24)",
        boxShadow: "0 45px 120px rgba(1,10,15,.52), 0 0 0 8px rgba(255,255,255,.025)",
        opacity: interpolate(frame, [0, 16], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
        translate: interpolate(
          frame,
          [0, 22],
          [
            enterFrom === "left" ? "-80px 0px" : enterFrom === "bottom" ? "0px 70px" : "80px 0px",
            "0px 0px",
          ],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          },
        ),
        scale: interpolate(frame, [0, 22], [0.97, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
          output: "perceptual-scale",
        }),
      }}
    >
      <div
        style={{
          height: 66,
          display: "flex",
          alignItems: "center",
          gap: 18,
          padding: "0 24px",
          borderBottom: "1px solid rgba(220,230,232,.12)",
          background: "linear-gradient(180deg, rgba(17,39,52,.98), rgba(7,25,37,.98))",
        }}
      >
        <div style={{display: "flex", gap: 9}}>
          <div style={{width: 12, height: 12, borderRadius: 12, backgroundColor: "#FF806C"}} />
          <div style={{width: 12, height: 12, borderRadius: 12, backgroundColor: COLORS.amber}} />
          <div style={{width: 12, height: 12, borderRadius: 12, backgroundColor: COLORS.mint}} />
        </div>
        <div
          style={{
            flex: 1,
            height: 36,
            borderRadius: 12,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 16px",
            backgroundColor: "rgba(255,255,255,.055)",
            outline: "1px solid rgba(255,255,255,.07)",
            fontFamily: "Geist Variable",
            fontSize: 17,
            color: COLORS.muted,
          }}
        >
          <span>{title}</span>
          <span style={{fontFamily: "monospace", fontSize: 14, color: COLORS.mint}}>localhost:3000{route}</span>
        </div>
        <div
          style={{
            padding: "8px 13px",
            borderRadius: 999,
            backgroundColor: "rgba(82,224,196,.10)",
            outline: "1px solid rgba(82,224,196,.26)",
            fontFamily: "Geist Variable",
            fontSize: 14,
            fontWeight: 650,
            color: COLORS.mintSoft,
          }}
        >
          LOCAL · PRIVATE
        </div>
      </div>
      <div style={{position: "relative", width: "100%", height: height - 66, overflow: "hidden", backgroundColor: "#DDE8EC"}}>
        {video ? (
          <Video
            name="Real LocalGuard browser recording"
            src={staticFile(video)}
            trimBefore={trimBefore}
            muted
            objectFit="cover"
            style={{
              width: "100%",
              height: "100%",
              objectPosition,
              scale: zoom,
            }}
          />
        ) : null}
        {screenshot ? (
          <Img
            name="Verified LocalGuard screenshot"
            src={staticFile(screenshot)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition,
              scale: zoom,
            }}
          />
        ) : null}
        <div
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            background: "linear-gradient(180deg, rgba(255,255,255,.025), transparent 22%, transparent 78%, rgba(5,20,30,.09))",
          }}
        />
      </div>
    </div>
  );
};
