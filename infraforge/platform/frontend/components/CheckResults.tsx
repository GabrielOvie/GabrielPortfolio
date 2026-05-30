import { CheckCircle2, XCircle, Shield, Target, Zap } from "lucide-react";
import { clsx } from "clsx";

interface CheckResult {
  check_id: string;
  layer: "correctness" | "safety" | "efficiency";
  description: string;
  passed: boolean;
  weight: number;
  detail: string | null;
  points_earned: number;
  points_possible: number;
}

interface Props {
  checks: CheckResult[];
}

const LAYER_CONFIG = {
  correctness: { icon: Target, label: "Correctness", color: "text-brand-500" },
  safety: { icon: Shield, label: "Safety", color: "text-blue-400" },
  efficiency: { icon: Zap, label: "Efficiency", color: "text-yellow-400" },
};

export function CheckResults({ checks }: Props) {
  const byLayer = checks.reduce<Record<string, CheckResult[]>>((acc, c) => {
    acc[c.layer] = [...(acc[c.layer] ?? []), c];
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {(["correctness", "safety", "efficiency"] as const).map((layer) => {
        const layerChecks = byLayer[layer] ?? [];
        if (!layerChecks.length) return null;
        const { icon: Icon, label, color } = LAYER_CONFIG[layer];
        const passed = layerChecks.filter((c) => c.passed).length;

        return (
          <div key={layer}>
            <div className="flex items-center gap-2 mb-3">
              <Icon className={`w-4 h-4 ${color}`} />
              <h3 className="text-sm font-semibold text-gray-300">{label}</h3>
              <span className="text-xs text-gray-500 ml-auto">{passed}/{layerChecks.length} passed</span>
            </div>
            <div className="space-y-2">
              {layerChecks.map((check) => (
                <div
                  key={check.check_id}
                  className={clsx(
                    "rounded-lg px-4 py-3 border text-sm",
                    check.passed
                      ? "bg-green-950/20 border-green-900/30"
                      : "bg-red-950/20 border-red-900/30"
                  )}
                >
                  <div className="flex items-start gap-3">
                    {check.passed
                      ? <CheckCircle2 className="w-4 h-4 text-brand-500 flex-shrink-0 mt-0.5" />
                      : <XCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                    }
                    <div className="flex-1 min-w-0">
                      <p className="text-gray-200 font-medium">{check.description}</p>
                      {check.detail && !check.passed && (
                        <p className="text-gray-400 text-xs mt-1 font-mono truncate">{check.detail}</p>
                      )}
                    </div>
                    <span className="text-xs text-gray-500 flex-shrink-0">
                      {Math.round(check.points_earned)}/{Math.round(check.points_possible)} pts
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
