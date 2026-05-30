"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { runsApi } from "../../lib/api";
import { ScoreDisplay } from "../../../components/ScoreDisplay";
import { CheckResults } from "../../../components/CheckResults";
import {
  Terminal, Clock, CheckCircle2, XCircle, Loader2, Send, StopCircle
} from "lucide-react";
import { formatDistanceToNow, differenceInSeconds } from "date-fns";

function useCountdown(timeoutAt: string | null) {
  const [remaining, setRemaining] = useState<number | null>(null);

  useEffect(() => {
    if (!timeoutAt) return;
    const tick = () => {
      const secs = differenceInSeconds(new Date(timeoutAt), new Date());
      setRemaining(Math.max(0, secs));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [timeoutAt]);

  return remaining;
}

function formatSeconds(secs: number) {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function RunPage({ params }: { params: { id: string } }) {
  const qc = useQueryClient();
  const [pollInterval, setPollInterval] = useState(3000);

  const { data: run } = useQuery({
    queryKey: ["run", params.id],
    queryFn: () => runsApi.get(params.id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || ["completed", "failed", "timeout", "cancelled"].includes(status)) return false;
      return pollInterval;
    },
  });

  const submit = useMutation({
    mutationFn: () => runsApi.submit(params.id),
    onSuccess: () => {
      setPollInterval(2000);
      qc.invalidateQueries({ queryKey: ["run", params.id] });
    },
  });

  const cancel = useMutation({
    mutationFn: () => runsApi.cancel(params.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["run", params.id] }),
  });

  const remaining = useCountdown(run?.timeout_at ?? null);

  const isActive = run && ["running"].includes(run.status);
  const isFinished = run && ["completed", "failed", "timeout", "cancelled"].includes(run.status);

  const creds = run?.access_credentials;

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Header */}
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <Link href="/labs" className="text-xl font-bold text-white no-underline">InfraForge</Link>
        {remaining !== null && remaining > 0 && (
          <div className={`flex items-center gap-2 text-sm font-mono ${remaining < 300 ? "text-red-400" : "text-gray-400"}`}>
            <Clock className="w-4 h-4" />
            {formatSeconds(remaining)} remaining
          </div>
        )}
      </nav>

      <main className="flex-1 max-w-5xl mx-auto px-6 py-8 w-full space-y-6">
        {/* Status */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {run?.status === "provisioning" && (
              <><Loader2 className="w-5 h-5 text-brand-500 animate-spin" />
              <span className="text-gray-400">Provisioning environment…</span></>
            )}
            {run?.status === "running" && (
              <><div className="w-2 h-2 bg-brand-500 rounded-full animate-pulse" />
              <span className="text-brand-400 font-medium">Lab is running</span></>
            )}
            {run?.status === "grading" && (
              <><Loader2 className="w-5 h-5 text-yellow-400 animate-spin" />
              <span className="text-gray-400">Grading…</span></>
            )}
            {run?.status === "completed" && run.passed && (
              <><CheckCircle2 className="w-5 h-5 text-brand-500" />
              <span className="text-brand-400 font-medium">Lab passed</span></>
            )}
            {run?.status === "completed" && !run.passed && (
              <><XCircle className="w-5 h-5 text-red-400" />
              <span className="text-red-400 font-medium">Lab not passed</span></>
            )}
            {run?.status === "timeout" && (
              <><XCircle className="w-5 h-5 text-yellow-400" />
              <span className="text-yellow-400">Time expired</span></>
            )}
          </div>

          {isActive && (
            <div className="flex items-center gap-3">
              <button
                onClick={() => cancel.mutate()}
                disabled={cancel.isPending}
                className="btn-ghost text-sm"
              >
                <StopCircle className="w-4 h-4" /> Cancel
              </button>
              <button
                onClick={() => submit.mutate()}
                disabled={submit.isPending || run?.status === "grading"}
                className="btn-primary"
              >
                {submit.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                Submit for grading
              </button>
            </div>
          )}
        </div>

        {/* SSH Credentials panel */}
        {creds && (
          <div className="card border-brand-500/30 space-y-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-300">
              <Terminal className="w-4 h-4 text-brand-500" />
              SSH Access
            </div>
            <div className="bg-gray-950 rounded-lg p-4 font-mono text-sm space-y-1">
              <p className="text-gray-400">
                <span className="text-brand-400">ssh</span>{" "}
                {creds.ssh_user}@{creds.ssh_host}{" "}
                <span className="text-gray-500">-p</span>{" "}
                {creds.ssh_port}
              </p>
              <p className="text-gray-400">
                <span className="text-gray-500">Password:</span>{" "}
                <span className="text-yellow-300 select-all">{creds.ssh_password}</span>
              </p>
            </div>
            <p className="text-xs text-gray-500">
              Credentials are valid for this session only. Do not share them.
            </p>
          </div>
        )}

        {/* Score display after completion */}
        {isFinished && run.final_score !== null && (
          <ScoreDisplay
            score={run.final_score}
            passed={run.passed ?? false}
            durationSeconds={run.duration_seconds}
            detailed
          />
        )}

        {/* Link to portfolio after completion */}
        {run?.status === "completed" && (
          <div className="card flex items-center justify-between">
            <div>
              <p className="text-white font-medium">Result saved to your portfolio</p>
              <p className="text-gray-400 text-sm mt-0.5">
                Share a link to prove your skills to employers.
              </p>
            </div>
            <Link href="/portfolio/me" className="btn-primary">
              View portfolio
            </Link>
          </div>
        )}
      </main>
    </div>
  );
}
