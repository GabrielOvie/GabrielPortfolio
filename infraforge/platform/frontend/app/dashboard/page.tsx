"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { labsApi, portfolioApi } from "../lib/api";
import { LabCard } from "../../components/LabCard";
import { ScoreDisplay } from "../../components/ScoreDisplay";
import { Clock, Award, TrendingUp } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

export default function Dashboard() {
  const { data: labs } = useQuery({
    queryKey: ["labs", "free"],
    queryFn: () => labsApi.list({ free_only: true }),
  });

  const { data: portfolio } = useQuery({
    queryKey: ["portfolio", "mine"],
    queryFn: () => portfolioApi.mine(),
  });

  const completedLabs = portfolio?.filter((p) => p.passed) ?? [];
  const avgScore = portfolio?.length
    ? Math.round(portfolio.reduce((s, p) => s + p.final_score, 0) / portfolio.length)
    : null;

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Nav */}
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold text-white no-underline">
          InfraForge
        </Link>
        <div className="flex items-center gap-4">
          <Link href="/labs" className="btn-ghost text-sm">Labs</Link>
          <Link href="/portfolio/me" className="btn-ghost text-sm">Portfolio</Link>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 py-10 space-y-10">
        {/* Stats strip */}
        <div className="grid grid-cols-3 gap-4">
          <div className="card flex items-center gap-4">
            <div className="p-3 bg-brand-500/10 rounded-lg">
              <Award className="w-6 h-6 text-brand-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{completedLabs.length}</p>
              <p className="text-gray-400 text-sm">Labs passed</p>
            </div>
          </div>
          <div className="card flex items-center gap-4">
            <div className="p-3 bg-blue-500/10 rounded-lg">
              <TrendingUp className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{avgScore ?? "—"}</p>
              <p className="text-gray-400 text-sm">Avg score</p>
            </div>
          </div>
          <div className="card flex items-center gap-4">
            <div className="p-3 bg-purple-500/10 rounded-lg">
              <Clock className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{portfolio?.length ?? 0}</p>
              <p className="text-gray-400 text-sm">Total attempts</p>
            </div>
          </div>
        </div>

        {/* Start somewhere */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Free labs to start</h2>
            <Link href="/labs" className="text-sm text-brand-500 hover:text-brand-600">
              View all labs
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {labs?.slice(0, 3).map((lab) => (
              <LabCard key={lab.id} lab={lab} />
            ))}
          </div>
        </section>

        {/* Recent results */}
        {portfolio && portfolio.length > 0 && (
          <section>
            <h2 className="text-lg font-semibold text-white mb-4">Recent results</h2>
            <div className="space-y-3">
              {portfolio.slice(0, 5).map((item) => (
                <Link
                  key={item.id}
                  href={`/portfolio/p/${item.shareable_slug}`}
                  className="card flex items-center justify-between hover:border-gray-700 transition-colors no-underline"
                >
                  <div>
                    <p className="text-white font-medium">{item.lab_title}</p>
                    <p className="text-gray-400 text-sm mt-0.5">
                      {formatDistanceToNow(new Date(item.completed_at), { addSuffix: true })}
                      {item.duration_seconds && ` · ${Math.round(item.duration_seconds / 60)} min`}
                    </p>
                  </div>
                  <ScoreDisplay score={item.final_score} passed={item.passed} />
                </Link>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
