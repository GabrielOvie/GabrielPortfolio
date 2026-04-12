"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import { labsApi, runsApi } from "../../lib/api";
import { ScoreDisplay } from "../../../components/ScoreDisplay";
import {
  Clock, Terminal, Shield, Target, Zap, ChevronLeft, Play
} from "lucide-react";
import { clsx } from "clsx";

const DIFFICULTY_COLOR: Record<string, string> = {
  beginner: "badge-green",
  intermediate: "badge-yellow",
  advanced: "badge-red",
  expert: "badge-red",
};

const CATEGORY_LABEL: Record<string, string> = {
  linux: "Linux",
  containers: "Containers",
  kubernetes: "Kubernetes",
  cloud_aws: "AWS",
  cloud_gcp: "GCP",
  iac: "IaC",
  security: "Security",
};

export default function LabDetail({ params }: { params: { slug: string } }) {
  const router = useRouter();
  const qc = useQueryClient();

  const { data: lab, isLoading } = useQuery({
    queryKey: ["lab", params.slug],
    queryFn: () => labsApi.get(params.slug),
  });

  const launch = useMutation({
    mutationFn: () => runsApi.launch(params.slug),
    onSuccess: (run) => {
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      router.push(`/runs/${run.id}`);
    },
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!lab) return null;

  return (
    <div className="min-h-screen bg-gray-950">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center gap-4">
        <Link href="/labs" className="btn-ghost text-sm flex items-center gap-1">
          <ChevronLeft className="w-4 h-4" /> Labs
        </Link>
        <span className="text-gray-600">/</span>
        <span className="text-gray-300 text-sm">{lab.title}</span>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-10 grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Header */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className={DIFFICULTY_COLOR[lab.difficulty]}>
                {lab.difficulty}
              </span>
              <span className="badge badge-blue">
                {CATEGORY_LABEL[lab.category] ?? lab.category}
              </span>
              {lab.is_free && <span className="badge badge-green">Free</span>}
            </div>
            <h1 className="text-2xl font-bold text-white">{lab.title}</h1>
            <p className="text-gray-400 mt-2">{lab.description}</p>
          </div>

          {/* Scenario */}
          <div className="card prose prose-invert prose-sm max-w-none">
            <ReactMarkdown>{lab.scenario_markdown ?? ""}</ReactMarkdown>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Launch card */}
          <div className="card space-y-4">
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between text-gray-400">
                <span className="flex items-center gap-1.5">
                  <Clock className="w-4 h-4" /> Est. time
                </span>
                <span className="text-white">{lab.estimated_minutes} min</span>
              </div>
              <div className="flex items-center justify-between text-gray-400">
                <span className="flex items-center gap-1.5">
                  <Terminal className="w-4 h-4" /> Environment
                </span>
                <span className="text-white capitalize">{lab.execution_model}</span>
              </div>
              {lab.pass_rate !== null && (
                <div className="flex items-center justify-between text-gray-400">
                  <span>Pass rate</span>
                  <span className="text-white">{Math.round((lab.pass_rate ?? 0) * 100)}%</span>
                </div>
              )}
            </div>

            <button
              onClick={() => launch.mutate()}
              disabled={launch.isPending}
              className="btn-primary w-full justify-center"
            >
              {launch.isPending ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Provisioning...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Launch lab
                </>
              )}
            </button>

            {launch.isError && (
              <p className="text-red-400 text-xs text-center">
                {(launch.error as any)?.response?.data?.detail ?? "Launch failed"}
              </p>
            )}
          </div>

          {/* Scoring breakdown */}
          <div className="card space-y-3">
            <h3 className="text-sm font-semibold text-gray-300">How scoring works</h3>
            <div className="space-y-2">
              {[
                { icon: Target, label: "Correctness", value: lab.weight_correctness, color: "text-brand-500" },
                { icon: Shield, label: "Safety", value: lab.weight_safety, color: "text-blue-400" },
                { icon: Zap, label: "Efficiency", value: lab.weight_efficiency, color: "text-yellow-400" },
              ].map(({ icon: Icon, label, value, color }) => (
                <div key={label} className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${color} flex-shrink-0`} />
                  <div className="flex-1">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-400">{label}</span>
                      <span className="text-white">{Math.round(value * 100)}%</span>
                    </div>
                    <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${color.replace("text-", "bg-")}`}
                        style={{ width: `${value * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Stats */}
          {lab.total_runs > 0 && (
            <div className="card space-y-2 text-sm text-gray-400">
              <p>{lab.total_runs.toLocaleString()} attempts</p>
              {lab.avg_score && <p>Avg score: <span className="text-white">{Math.round(lab.avg_score)}</span></p>}
              {lab.avg_completion_minutes && (
                <p>Avg completion: <span className="text-white">{Math.round(lab.avg_completion_minutes)} min</span></p>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
