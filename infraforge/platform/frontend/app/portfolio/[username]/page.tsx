"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { portfolioApi, PortfolioItem } from "../../lib/api";
import { ScoreDisplay } from "../../../components/ScoreDisplay";
import { formatDistanceToNow, format } from "date-fns";
import { Shield, Target, Zap, ExternalLink } from "lucide-react";

const DIFFICULTY_COLOR: Record<string, string> = {
  beginner: "badge-green",
  intermediate: "badge-yellow",
  advanced: "badge-red",
  expert: "badge-red",
};

const CATEGORY_LABEL: Record<string, string> = {
  linux: "Linux", containers: "Containers", kubernetes: "Kubernetes",
  cloud_aws: "AWS", iac: "IaC", security: "Security",
};

function PortfolioCard({ item }: { item: PortfolioItem }) {
  const mins = item.duration_seconds ? Math.round(item.duration_seconds / 60) : null;

  return (
    <Link
      href={`/portfolio/p/${item.shareable_slug}`}
      className="card hover:border-gray-700 transition-colors no-underline block"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className={DIFFICULTY_COLOR[item.lab_difficulty]}>{item.lab_difficulty}</span>
            <span className="badge badge-blue">{CATEGORY_LABEL[item.lab_category] ?? item.lab_category}</span>
          </div>
          <h3 className="text-white font-semibold truncate">{item.lab_title}</h3>
          {item.summary && (
            <p className="text-gray-400 text-sm mt-1 line-clamp-2">{item.summary}</p>
          )}
          <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
            <span>{format(new Date(item.completed_at), "MMM d, yyyy")}</span>
            {mins && <span>{mins} min</span>}
          </div>
        </div>
        <div className="flex-shrink-0">
          <ScoreDisplay score={item.final_score} passed={item.passed} />
        </div>
      </div>

      {/* Layer scores */}
      <div className="mt-4 grid grid-cols-3 gap-2 border-t border-gray-800 pt-4">
        {[
          { icon: Target, label: "Correctness", score: item.correctness_score, color: "text-brand-500" },
          { icon: Shield, label: "Safety", score: item.safety_score, color: "text-blue-400" },
          { icon: Zap, label: "Efficiency", score: item.efficiency_score, color: "text-yellow-400" },
        ].map(({ icon: Icon, label, score, color }) => (
          <div key={label} className="text-center">
            <Icon className={`w-4 h-4 ${color} mx-auto mb-1`} />
            <p className="text-white text-sm font-semibold">{Math.round(score)}</p>
            <p className="text-gray-500 text-xs">{label}</p>
          </div>
        ))}
      </div>
    </Link>
  );
}

export default function Portfolio({ params }: { params: { username: string } }) {
  const isMe = params.username === "me";
  const { data: items, isLoading } = useQuery({
    queryKey: ["portfolio", params.username],
    queryFn: () => isMe ? portfolioApi.mine() : portfolioApi.public(params.username),
  });

  const passed = items?.filter((i) => i.passed) ?? [];
  const avgScore = items?.length
    ? Math.round(items.reduce((s, i) => s + i.final_score, 0) / items.length)
    : 0;

  return (
    <div className="min-h-screen bg-gray-950">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold text-white no-underline">InfraForge</Link>
        {isMe && (
          <Link href="/labs" className="btn-primary text-sm">Browse labs</Link>
        )}
      </nav>

      <main className="max-w-3xl mx-auto px-6 py-10 space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">
              {isMe ? "My portfolio" : `${params.username}'s portfolio`}
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              Verified lab results — graded automatically, no self-reporting.
            </p>
          </div>
          {!isMe && (
            <a
              href="#"
              className="btn-ghost text-sm flex items-center gap-1.5"
            >
              <ExternalLink className="w-4 h-4" /> Share
            </a>
          )}
        </div>

        {/* Stats */}
        {items && items.length > 0 && (
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Labs passed", value: passed.length },
              { label: "Avg score", value: avgScore },
              { label: "Total attempts", value: items.length },
            ].map(({ label, value }) => (
              <div key={label} className="card text-center">
                <p className="text-2xl font-bold text-white">{value}</p>
                <p className="text-gray-400 text-sm mt-0.5">{label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Results */}
        {isLoading ? (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="card animate-pulse h-40 bg-gray-900" />
            ))}
          </div>
        ) : items?.length === 0 ? (
          <div className="card text-center py-16">
            <p className="text-gray-400">No completed labs yet.</p>
            {isMe && (
              <Link href="/labs" className="btn-primary mt-4 inline-flex">
                Start your first lab
              </Link>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {items?.map((item) => <PortfolioCard key={item.id} item={item} />)}
          </div>
        )}
      </main>
    </div>
  );
}
