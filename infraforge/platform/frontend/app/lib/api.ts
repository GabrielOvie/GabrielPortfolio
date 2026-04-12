import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

// Attach JWT from localStorage on every request
api.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-refresh on 401
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh = localStorage.getItem("refresh_token");
      if (refresh) {
        try {
          const { data } = await axios.post("/api/v1/auth/refresh", { refresh_token: refresh });
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("refresh_token", data.refresh_token);
          error.config.headers.Authorization = `Bearer ${data.access_token}`;
          return api.request(error.config);
        } catch {
          localStorage.clear();
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;

// ── Typed API methods ─────────────────────────────────────────────────────────

export interface Lab {
  id: string;
  slug: string;
  title: string;
  description: string;
  category: string;
  difficulty: string;
  execution_model: string;
  estimated_minutes: number;
  is_free: boolean;
  total_runs: number;
  avg_score: number | null;
  pass_rate: number | null;
  weight_correctness: number;
  weight_safety: number;
  weight_efficiency: number;
}

export interface Run {
  id: string;
  lab_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  timeout_at: string | null;
  duration_seconds: number | null;
  final_score: number | null;
  passed: boolean | null;
  access_credentials: {
    ssh_host: string;
    ssh_port: number;
    ssh_user: string;
    ssh_password: string;
  } | null;
}

export interface PortfolioItem {
  id: string;
  shareable_slug: string;
  lab_title: string;
  lab_slug: string;
  lab_category: string;
  lab_difficulty: string;
  final_score: number;
  passed: boolean;
  correctness_score: number;
  safety_score: number;
  efficiency_score: number;
  duration_seconds: number | null;
  summary: string | null;
  completed_at: string;
  is_public: boolean;
}

export const labsApi = {
  list: (params?: { category?: string; difficulty?: string; free_only?: boolean }) =>
    api.get<Lab[]>("/labs", { params }).then((r) => r.data),
  get: (slug: string) => api.get<Lab & { scenario_markdown: string }>(`/labs/${slug}`).then((r) => r.data),
};

export const runsApi = {
  launch: (lab_slug: string) => api.post<Run>("/runs", { lab_slug }).then((r) => r.data),
  get: (run_id: string) => api.get<Run>(`/runs/${run_id}`).then((r) => r.data),
  submit: (run_id: string) => api.post<Run>(`/runs/${run_id}/submit`).then((r) => r.data),
  cancel: (run_id: string) => api.delete(`/runs/${run_id}`),
};

export const portfolioApi = {
  mine: () => api.get<PortfolioItem[]>("/portfolio/me").then((r) => r.data),
  public: (username: string) => api.get<PortfolioItem[]>(`/portfolio/u/${username}`).then((r) => r.data),
  getItem: (slug: string) => api.get<PortfolioItem>(`/portfolio/p/${slug}`).then((r) => r.data),
};
