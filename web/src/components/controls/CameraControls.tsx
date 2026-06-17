import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { ControlDescriptor } from "@/lib/types";

// Sharpness ranges into the thousands on this camera, so the native
// spinner's default step of 1 would take forever to click through —
// step it by 100 instead. Every other control keeps its protocol-reported
// step (usually 1).
const LARGE_STEP_CONTROL_IDS = new Set(["sharpness"]);
const LARGE_STEP = 100;

interface Props {
  controls: ControlDescriptor[];
}

export function CameraControls({ controls }: Props) {
  const [autotuning, setAutotuning] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function runAutotune() {
    setAutotuning(true);
    setStatus(null);
    try {
      const result = await api.autotuneCamera();
      setStatus(`Done — ${result.stars_detected} star(s) detected`);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Autotune failed");
    } finally {
      setAutotuning(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Camera</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {controls.map((c) => (
          <ControlRow key={c.id ?? c.name} control={c} />
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
        {status && (
          <p className="text-xs text-muted-foreground text-center">{status}</p>
        )}
      </CardContent>
    </Card>
  );
}

function ControlRow({ control }: { control: ControlDescriptor }) {
  const id = control.id ?? control.name ?? "";
  const serverValue = control.cur ?? control.value ?? control.min;
  const stepSize = LARGE_STEP_CONTROL_IDS.has(id) ? LARGE_STEP : control.step ?? 1;

  return (
    <div className="flex items-center justify-between">
      <span className="text-sm">{control.label}</span>
      <Input
        type="number"
        min={control.min}
        max={control.max}
        step={stepSize}
        defaultValue={serverValue}
        key={`${id}-${serverValue}`}
        className="w-24 h-8"
        onBlur={(e) => {
          const v = Number(e.currentTarget.value);
          if (!Number.isNaN(v)) api.setControl(id, v).catch((e) => console.error(e));
        }}
      />
    </div>
  );
}
