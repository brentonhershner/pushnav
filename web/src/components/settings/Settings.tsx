import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useNumberInput } from "@/hooks/useNumberInput";
import type { EnginePayload } from "@/lib/types";

const DEFAULT_SHOW_STARS = false;
const DEFAULT_AUDIO_ENABLED = true;
const DEFAULT_MIN_MATCHES = 8;
const DEFAULT_MAX_PROB = 0.2;
const DEFAULT_STACK_COUNT = 1;

interface Props {
  state: EnginePayload;
  showStars: boolean;
  setShowStars: (v: boolean) => void;
  className?: string;
}

export function Settings({ state, showStars, setShowStars, className }: Props) {
  const minMatchesProps = useNumberInput(state.min_matches, (v) =>
    api.setAdvanced({ min_matches: v }).catch(console.error)
  );
  const maxProbProps = useNumberInput(state.max_prob, (v) =>
    api.setAdvanced({ max_prob: v }).catch(console.error)
  );
  const stackCountProps = useNumberInput(state.stack_count, (v) =>
    api.setAdvanced({ stack_count: v }).catch(console.error)
  );
  function resetToDefaults() {
    setShowStars(DEFAULT_SHOW_STARS);
    api
      .setSettings({ audio_enabled: DEFAULT_AUDIO_ENABLED })
      .catch(console.error);
    api
      .setAdvanced({
        min_matches: DEFAULT_MIN_MATCHES,
        max_prob: DEFAULT_MAX_PROB,
        stack_count: DEFAULT_STACK_COUNT,
      })
      .catch(console.error);
  }

  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle className="text-primary">Settings</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col flex-1 space-y-2">
        <Row label="Show detected stars">
          <Switch
            checked={showStars}
            onCheckedChange={(v) => setShowStars(v)}
          />
        </Row>
        <Row label="Audio feedback">
          <Switch
            checked={state.audio_enabled}
            onCheckedChange={(v) => api.setSettings({ audio_enabled: v })}
          />
        </Row>
        <Separator />
        <div className="space-y-2">
          <div className="text-sm font-medium text-primary">
            Advanced solver
          </div>
          <Row label="Min matches">
            <Input
              type="number"
              min={3}
              max={50}
              step={1}
              className="w-20 h-8"
              {...minMatchesProps}
            />
          </Row>
          <p className="text-xs text-muted-foreground leading-snug">
            Stars matched before a solve is accepted. Higher = stricter.
          </p>
          <Row label="Max prob">
            <Input
              type="number"
              min={0}
              max={1}
              step={0.01}
              className="w-20 h-8"
              {...maxProbProps}
            />
          </Row>
          <p className="text-xs text-muted-foreground leading-snug">
            Max false-match probability. Lower = stricter.
          </p>
          <Row label="Frame stack">
            <Input
              type="number"
              min={1}
              max={32}
              step={1}
              className="w-20 h-8"
              {...stackCountProps}
            />
          </Row>
          <p className="text-xs text-muted-foreground leading-snug">
            Frames averaged before solving. Higher = brighter stars, more
            latency. 1 = off, 8 = ~¼s effective exposure at 30fps.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="w-full mt-auto"
          onClick={resetToDefaults}
        >
          Reset to defaults
        </Button>
      </CardContent>
    </Card>
  );
}

function Row({
  label,
  children,
}: {
  label: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm">{label}</span>
      {children}
    </div>
  );
}
