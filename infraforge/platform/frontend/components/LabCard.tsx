import Link from "next/link";
import { Clock, Users, TrendingUp } from "lucide-react";
import { Lab } from "../app/lib/api";
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
  cloud_azure: "Azure",
  iac: "IaC",
  security: "Security",
  observability: "Observability",
};

export function LabCard({ lab }: { lab: Lab }) {
  return (
    <Link
      href={`/labs/${lab.slug}`}
      className="card flex flex-col hover:border-gray-700 transition-colors no-underline group"
    >
      {/* Category + difficulty */}
      <div className="flex items-center gap-2 mb-3">
        <span className={DIFFICULTY_COLOR[lab.difficulty] ?? "badge-gray"}>
          {lab.difficulty}
        </span>
        <span className="badge badge-blue">
          {CATEGORY_LABEL[lab.category] ?? lab.category}
        </span>
        {lab.is_free && <span className="badge badge-green">Free</span>}
      </div>

      {/* Title */}
      <h3 className="text-white font-semibold group-hover:text-brand-400 transition-colors leading-snug">
        {lab.title}
      </h3>

      {/* Description */}
      <p className="text-gray-400 text-sm mt-2 line-clamp-2 flex-1">
        {lab.description}
      </p>

      {/* Stats footer */}
      <div className="flex items-center gap-4 mt-4 pt-4 border-t border-gray-800 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <Clock className="w-3.5 h-3.5" />
          {lab.estimated_minutes} min
        </span>
        {lab.total_runs > 0 && (
          <span className="flex items-center gap-1">
            <Users className="w-3.5 h-3.5" />
            {lab.total_runs.toLocaleString()}
          </span>
        )}
        {lab.avg_score !== null && (
          <span className="flex items-center gap-1 ml-auto">
            <TrendingUp className="w-3.5 h-3.5" />
            avg {Math.round(lab.avg_score)}
          </span>
        )}
      </div>
    </Link>
  );
}
