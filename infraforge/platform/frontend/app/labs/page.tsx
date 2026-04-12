"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { labsApi } from "../lib/api";
import { LabCard } from "../../components/LabCard";
import { Search, Filter } from "lucide-react";
import Link from "next/link";

const CATEGORIES = [
  { value: "", label: "All" },
  { value: "linux", label: "Linux" },
  { value: "containers", label: "Containers" },
  { value: "kubernetes", label: "Kubernetes" },
  { value: "cloud_aws", label: "AWS" },
  { value: "iac", label: "IaC" },
  { value: "security", label: "Security" },
];

const DIFFICULTIES = [
  { value: "", label: "All levels" },
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
  { value: "expert", label: "Expert" },
];

export default function LabCatalog() {
  const [category, setCategory] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [freeOnly, setFreeOnly] = useState(false);

  const { data: labs, isLoading } = useQuery({
    queryKey: ["labs", category, difficulty, freeOnly],
    queryFn: () =>
      labsApi.list({
        category: category || undefined,
        difficulty: difficulty || undefined,
        free_only: freeOnly || undefined,
      }),
  });

  return (
    <div className="min-h-screen bg-gray-950">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold text-white no-underline">InfraForge</Link>
        <div className="flex items-center gap-4">
          <Link href="/dashboard" className="btn-ghost text-sm">Dashboard</Link>
          <Link href="/portfolio/me" className="btn-ghost text-sm">Portfolio</Link>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Lab catalog</h1>
          <p className="text-gray-400 mt-1">
            Real infra problems. Isolated environments. Graded results.
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 mb-8">
          {/* Category pills */}
          <div className="flex items-center gap-1 bg-gray-900 border border-gray-800 rounded-lg p-1">
            {CATEGORIES.map((c) => (
              <button
                key={c.value}
                onClick={() => setCategory(c.value)}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                  category === c.value
                    ? "bg-brand-500 text-white"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>

          {/* Difficulty select */}
          <select
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value)}
            className="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-brand-500"
          >
            {DIFFICULTIES.map((d) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>

          {/* Free only */}
          <label className="flex items-center gap-2 cursor-pointer select-none text-sm text-gray-400">
            <input
              type="checkbox"
              checked={freeOnly}
              onChange={(e) => setFreeOnly(e.target.checked)}
              className="w-4 h-4 rounded accent-brand-500"
            />
            Free only
          </label>

          {labs && (
            <span className="ml-auto text-sm text-gray-500">{labs.length} labs</span>
          )}
        </div>

        {/* Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="card animate-pulse h-48 bg-gray-900" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {labs?.map((lab) => <LabCard key={lab.id} lab={lab} />)}
            {labs?.length === 0 && (
              <p className="col-span-3 text-gray-500 text-center py-16">
                No labs match these filters.
              </p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
