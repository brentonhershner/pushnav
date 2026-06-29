import type { EnginePayload } from "@/lib/types";
import { StarOverlay } from "./StarOverlay";
import { NavOverlay } from "./NavOverlay";
import { SyncCandidatesOverlay } from "./SyncCandidatesOverlay";
import { AxesOverlay } from "./AxesOverlay";
import { LocationOverlay } from "./LocationOverlay";

interface Props {
  state: EnginePayload;
  showStars: boolean;
  redFilter: boolean;
}

const NO_STARS_STATES = ["CALIBRATE", "WARMING_UP", "TRACKING"];

export function LiveView({ state, showStars, redFilter }: Props) {
  const { image_w, image_h } = state;
  const noStars =
    NO_STARS_STATES.includes(state.state) && state.failures >= 3;

  return (
    <div
      className="relative bg-black w-full overflow-hidden rounded-xl border"
      style={{ aspectRatio: `${image_w} / ${image_h}` }}
    >
      <img
        src="/frame.mjpg"
        alt="Live camera frame"
        className="absolute inset-0 w-full h-full object-cover"
      />
      {redFilter && (
        <div className="absolute inset-0 bg-red-600 mix-blend-multiply pointer-events-none" />
      )}
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox={`0 0 ${image_w} ${image_h}`}
        preserveAspectRatio="xMidYMid slice"
      >
        <LocationOverlay state={state} />
        {showStars && <StarOverlay state={state} />}
        {!noStars && <AxesOverlay state={state} />}
        {!noStars && <NavOverlay state={state} />}
        {state.state === "SYNC_CONFIRM" && (
          <SyncCandidatesOverlay state={state} />
        )}
      </svg>
      {noStars && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-destructive text-destructive-foreground px-4 py-2 rounded font-semibold animate-pulse shadow-lg">
          NO STARS — point at darker sky / clouds?
        </div>
      )}
    </div>
  );
}
