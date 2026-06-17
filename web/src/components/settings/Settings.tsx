import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { QRCodeSVG } from "qrcode.react";
import { ActivityDot } from "@/components/ActivityDot";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useNumberInput } from "@/hooks/useNumberInput";
import type { ControlDescriptor, EnginePayload } from "@/lib/types";

const DEFAULT_SHOW_STARS = false;
const DEFAULT_AUDIO_ENABLED = true;
const DEFAULT_MIN_MATCHES = 8;
const DEFAULT_MAX_PROB = 0.2;
const DEFAULT_STACK_COUNT = 1;

// Controls shown in the main camera section (user touches these every session).
const PRIMARY_CONTROL_IDS = new Set(["exposure", "gain"]);
// Controls hidden in the "Advanced camera" accordion section.
const ADVANCED_CONTROL_IDS = new Set([
  "brightness", "contrast", "gamma", "sharpness", "backlight_compensation",
]);
const LARGE_STEP_CONTROL_IDS = new Set(["sharpness"]);
const LARGE_STEP = 100;

interface Props {
  state: EnginePayload;
  showStars: boolean;
  setShowStars: (v: boolean) => void;
  className?: string;
}

export function Settings({ state, showStars, setShowStars, className }: Props) {
  const [autotuning, setAutotuning] = useState(false);
  const [autotuneStatus, setAutotuneStatus] = useState<string | null>(null);
  const [showQR, setShowQR] = useState(false);

  const minMatchesProps = useNumberInput(state.min_matches, (v) =>
    api.setAdvanced({ min_matches: v }).catch(console.error)
  );
  const maxProbProps = useNumberInput(state.max_prob, (v) =>
    api.setAdvanced({ max_prob: v }).catch(console.error)
  );
  const stackCountProps = useNumberInput(state.stack_count, (v) =>
    api.setAdvanced({ stack_count: v }).catch(console.error)
  );

  async function runAutotune() {
    setAutotuning(true);
    setAutotuneStatus(null);
    try {
      const result = await api.autotuneCamera();
      setAutotuneStatus(`Done — ${result.stars_detected} star(s) detected`);
    } catch (e) {
      setAutotuneStatus(e instanceof Error ? e.message : "Autotune failed");
    } finally {
      setAutotuning(false);
    }
  }

  function resetToDefaults() {
    setShowStars(DEFAULT_SHOW_STARS);
    api.setSettings({ audio_enabled: DEFAULT_AUDIO_ENABLED }).catch(console.error);
    api.setAdvanced({
      min_matches: DEFAULT_MIN_MATCHES,
      max_prob: DEFAULT_MAX_PROB,
      stack_count: DEFAULT_STACK_COUNT,
    }).catch(console.error);
  }

  const primaryControls = state.controls.filter((c) =>
    PRIMARY_CONTROL_IDS.has(c.id ?? c.name ?? "")
  );
  const advancedControls = state.controls.filter((c) =>
    ADVANCED_CONTROL_IDS.has(c.id ?? c.name ?? "")
  );
  const url = state.webserver.url;

  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-primary">Settings</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pb-4">

        {/* Always-visible: primary camera controls + auto-tune */}
        {primaryControls.length > 0 && (
          <div className="space-y-2">
            {primaryControls.map((c) => (
              <CameraControlRow key={c.id ?? c.name} control={c} />
            ))}
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              disabled={autotuning}
              onClick={runAutotune}
            >
              {autotuning ? "Auto-tuning…" : "Auto-tune for stars"}
            </Button>
            {autotuneStatus && (
              <p className="text-xs text-muted-foreground text-center">{autotuneStatus}</p>
            )}
          </div>
        )}

        {/* Accordion sections for everything else */}
        <Accordion type="multiple" defaultValue={["connectivity"]} className="w-full space-y-0">

          <AccordionItem value="display" className="border-b-0">
            <AccordionTrigger className="py-2 text-sm font-medium text-primary hover:no-underline">
              Display
            </AccordionTrigger>
            <AccordionContent className="space-y-2 pb-2">
              <Row label="Show detected stars">
                <Switch checked={showStars} onCheckedChange={setShowStars} />
              </Row>
              <Row label="Audio feedback">
                <Switch
                  checked={state.audio_enabled}
                  onCheckedChange={(v) => api.setSettings({ audio_enabled: v })}
                />
              </Row>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="solver" className="border-b-0">
            <AccordionTrigger className="py-2 text-sm font-medium text-primary hover:no-underline">
              Solver
            </AccordionTrigger>
            <AccordionContent className="space-y-2 pb-2">
              <Row label="Min matches">
                <Input type="number" min={3} max={50} step={1} className="w-20 h-8" {...minMatchesProps} />
              </Row>
              <p className="text-xs text-muted-foreground leading-snug">
                Stars matched before a solve is accepted. Higher = stricter.
              </p>
              <Row label="Max prob">
                <Input type="number" min={0} max={1} step={0.01} className="w-20 h-8" {...maxProbProps} />
              </Row>
              <p className="text-xs text-muted-foreground leading-snug">
                Max false-match probability. Lower = stricter.
              </p>
              <Row label="Frame stack">
                <Input type="number" min={1} max={32} step={1} className="w-20 h-8" {...stackCountProps} />
              </Row>
              <p className="text-xs text-muted-foreground leading-snug">
                Frames averaged before solving. 1 = off, 8 = ~¼s at 30fps.
              </p>
              <Button variant="outline" size="sm" className="w-full mt-1" onClick={resetToDefaults}>
                Reset to defaults
              </Button>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="connectivity" className="border-b-0">
            <AccordionTrigger className="py-2 text-sm font-medium text-primary hover:no-underline">
              Connectivity
            </AccordionTrigger>
            <AccordionContent className="space-y-2 pb-2">
              <div className="space-y-1">
                <div className="text-sm font-medium">Mobile phone URL</div>
                {url ? (
                  <>
                    <code className="block text-xs break-all">{url}</code>
                    <button
                      type="button"
                      onClick={() => setShowQR((v) => !v)}
                      className="text-xs text-primary underline-offset-2 hover:underline"
                    >
                      {showQR ? "Hide QR code" : "Show QR code"}
                    </button>
                    {showQR && (
                      <div className="pt-1">
                        <QRCodeSVG value={url} size={128} bgColor="#0a0000" fgColor="#ff4646" />
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-xs text-muted-foreground">No LAN IP detected</div>
                )}
              </div>
              <Row label={<span>Stellarium <ActivityDot active={state.stellarium.active} /></span>}>
                <code className="text-xs">{state.stellarium.address ?? "off"}</code>
              </Row>
              <Row label={<span>LX200 (SkySafari) <ActivityDot active={state.lx200.active} /></span>}>
                <code className="text-xs">{state.lx200.address ?? "off"}</code>
              </Row>
            </AccordionContent>
          </AccordionItem>

          {advancedControls.length > 0 && (
            <AccordionItem value="advanced-camera" className="border-b-0">
              <AccordionTrigger className="py-2 text-sm font-medium text-primary hover:no-underline">
                Advanced camera
              </AccordionTrigger>
              <AccordionContent className="space-y-2 pb-2">
                {advancedControls.map((c) => (
                  <CameraControlRow key={c.id ?? c.name} control={c} />
                ))}
              </AccordionContent>
            </AccordionItem>
          )}

        </Accordion>

      </CardContent>
    </Card>
  );
}

function CameraControlRow({ control }: { control: ControlDescriptor }) {
  const id = control.id ?? control.name ?? "";
  const serverValue = control.cur ?? control.value ?? control.min ?? 0;
  const stepSize = LARGE_STEP_CONTROL_IDS.has(id) ? LARGE_STEP : control.step ?? 1;
  const inputProps = useNumberInput(serverValue, (v) => api.setControl(id, v).catch(console.error));

  return (
    <Row label={control.label}>
      <Input
        type="number"
        min={control.min}
        max={control.max}
        step={stepSize}
        className="w-24 h-8"
        {...inputProps}
      />
    </Row>
  );
}

function Row({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm">{label}</span>
      {children}
    </div>
  );
}
