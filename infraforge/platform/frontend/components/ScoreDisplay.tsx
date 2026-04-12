import { clsx } from "clsx";
import { CheckCircle2, XCircle } from "lucide-react";

interface Props {
  score: number;
  passed: boolean;
  durationSeconds?: number | null;
  detailed?: boolean;
}

function scoreColor(score: number): string {
  if (score >= 85) return "text-brand-500";
  if (score >= 70) return "text-yellow-400";
  if (score >= 60) return "text-orange-400";
  return "text-red-400";
}

function scoreRingColor(score: number): string {
  if (score >= 85) return "stroke-brand-500";
  if (score >= 70) return "stroke-yellow-400";
  if (score >= 60) return "stroke-orange-400";
  return "stroke-red-400";
}

export function ScoreDisplay({ score, passed, durationSeconds, detailed }: Props) {
  const pct = Math.min(100, Math.max(0, score));
  const circumference = 2 * Math.PI * 20; // r=20
  const offset = circumference - (pct / 100) * circumference;

  if (!detailed) {
    // Compact variant: inline score badge
    return (
      <div className={clsx(
        "flex items-center gap-1.5 text-sm font-semibold",
        passed ? "text-brand-500" : "text-red-400",
      )}>
        {passed ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
        <span>{Math.round(pct)}</span>
      </div>
    );
  }

  // Detailed variant: full card
  const mins = durationSeconds ? Math.round(durationSeconds / 60) : null;

  return (
    <div className="card space-y-4">
      <div className="flex items-center gap-6">
        {/* Ring */}
        <div className="relative w-20 h-20 flex-shrink-0">
          <svg className="w-20 h-20 -rotate-90" viewBox="0 0 50 50">
            <circle cx="25" cy="25" r="20" fill="none" className="stroke-gray-800" strokeWidth="4" />
            <circle
              cx="25" cy="25" r="20" fill="none"
              className={scoreRingColor(pct)}
              strokeWidth="4"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className={clsx("text-lg font-bold", scoreColor(pct))}>
              {Math.round(pct)}
            </span>
          </div>
        </div>

        <div>
          <div className={clsx(
            "flex items-center gap-2 font-semibold text-lg",
            passed ? "text-brand-400" : "text-red-400"
          )}>
            {passed
              ? <><CheckCircle2 className="w-5 h-5" /> Passed</>
              : <><XCircle className="w-5 h-5" /> Not passed</>
            }
          </div>
          {mins && (
            <p className="text-gray-400 text-sm mt-0.5">
              Completed in {mins} min
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
