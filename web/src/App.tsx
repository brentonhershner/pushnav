import { useEffect, useState } from "react";
import { useEngineState } from "@/hooks/useEngineState";
import { useView } from "@/hooks/useView";
import { LiveView } from "@/components/live-view/LiveView";
import { Wizard } from "@/components/wizard/Wizard";
import { Settings } from "@/components/settings/Settings";
import { Splash } from "@/components/splash/Splash";
import { ErrorModal } from "@/components/ErrorModal";
import { StateHeader } from "@/components/StateHeader";
import { StepIndicator } from "@/components/StepIndicator";
import { DebugPanel } from "@/components/debug/DebugPanel";
import { WhatToSee } from "@/components/catalog/WhatToSee";

function useLocalStorageBool(key: string, defaultValue: boolean) {
  const [v, setV] = useState<boolean>(() => {
    const saved = localStorage.getItem(key);
    return saved === null ? defaultValue : saved === "true";
  });
  useEffect(() => {
    localStorage.setItem(key, String(v));
  }, [key, v]);
  return [v, setV] as const;
}

export default function App() {
  const state = useEngineState();
  const [showStars, setShowStars] = useLocalStorageBool("pushnav.show_stars", false);
  const [view, setView] = useView();

  return (
    <>
      <Splash state={state} />
      <ErrorModal state={state} />
      {state && (
        <div className="bg-background text-foreground h-screen overflow-hidden flex flex-col">
          <div className="px-2 pt-2 w-full shrink-0">
            <StateHeader state={state} view={view} onViewChange={setView} />
          </div>
          {view === "navigation" ? (
            // Two-column grid that fills the remaining viewport height.
            // Left column: live view (fixed aspect ratio) + wizard (scrollable remainder).
            // Right column: scrollable settings sidebar.
            <div className="grid md:grid-cols-3 gap-2 px-2 pt-3 pb-2 w-full flex-1 min-h-0">
              <div className="md:col-span-2 flex flex-col gap-2 min-h-0">
                <LiveView state={state} showStars={showStars} />
                <StepIndicator state={state} />
                <div className="flex-1 min-h-0 overflow-y-auto [&>*]:h-full">
                  <Wizard state={state} />
                </div>
              </div>
              <div className="flex flex-col min-h-0 overflow-y-auto">
                <Settings
                  state={state}
                  showStars={showStars}
                  setShowStars={setShowStars}
                  className="flex-1"
                />
              </div>
            </div>
          ) : (
            <div className="px-2 pt-3 pb-2 w-full flex-1 min-h-0">
              <WhatToSee
                state={state}
                onSwitchToNavigation={() => setView("navigation")}
              />
            </div>
          )}
          {state.dev_mode && (
            <section className="px-2 pb-2 w-full shrink-0">
              <DebugPanel state={state} />
            </section>
          )}
        </div>
      )}
    </>
  );
}
