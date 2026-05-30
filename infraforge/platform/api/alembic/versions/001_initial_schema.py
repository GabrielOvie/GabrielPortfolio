"""Initial InfraForge schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # ── subscriptions ─────────────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tier", sa.String(32), nullable=False, server_default="free"),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("current_period_end", sa.DateTime, nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_subscriptions_stripe_customer", "subscriptions", ["stripe_customer_id"])

    # ── labs ──────────────────────────────────────────────────────────────────
    op.create_table(
        "labs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("difficulty", sa.String(32), nullable=False),
        sa.Column("execution_model", sa.String(32), nullable=False, server_default="container"),
        sa.Column("estimated_minutes", sa.Integer, nullable=False),
        sa.Column("max_runtime_minutes", sa.Integer, nullable=False, server_default="90"),
        sa.Column("weight_correctness", sa.Float, nullable=False, server_default="0.60"),
        sa.Column("weight_safety", sa.Float, nullable=False, server_default="0.25"),
        sa.Column("weight_efficiency", sa.Float, nullable=False, server_default="0.15"),
        sa.Column("is_free", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("total_runs", sa.Integer, server_default="0"),
        sa.Column("avg_completion_minutes", sa.Float, nullable=True),
        sa.Column("avg_score", sa.Float, nullable=True),
        sa.Column("pass_rate", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_labs_slug", "labs", ["slug"], unique=True)

    # ── lab_versions ──────────────────────────────────────────────────────────
    op.create_table(
        "lab_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("template_id", sa.String(128), nullable=False),
        sa.Column("image_tag", sa.String(256), nullable=False),
        sa.Column("grading_spec", JSON, nullable=False),
        sa.Column("scenario_markdown", sa.Text, nullable=False),
        sa.Column("change_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lab_versions_lab_id", "lab_versions", ["lab_id"])

    # ── challenge_runs ────────────────────────────────────────────────────────
    op.create_table(
        "challenge_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("lab_id", UUID(as_uuid=True), sa.ForeignKey("labs.id"), nullable=False),
        sa.Column("lab_version_id", UUID(as_uuid=True), sa.ForeignKey("lab_versions.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("orchestrator_run_id", sa.String(128), nullable=True),
        sa.Column("access_credentials", JSON, nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("timeout_at", sa.DateTime, nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("command_count", sa.Integer, server_default="0"),
        sa.Column("restart_count", sa.Integer, server_default="0"),
        sa.Column("final_score", sa.Float, nullable=True),
        sa.Column("passed", sa.Boolean, nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("artifact_path", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_challenge_runs_user_id", "challenge_runs", ["user_id"])
    op.create_index("ix_challenge_runs_lab_id", "challenge_runs", ["lab_id"])
    op.create_index("ix_challenge_runs_status", "challenge_runs", ["status"])
    op.create_index("ix_challenge_runs_orchestrator_run_id", "challenge_runs", ["orchestrator_run_id"])

    # ── scoring_results ───────────────────────────────────────────────────────
    op.create_table(
        "scoring_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("challenge_runs.id"), nullable=False),
        sa.Column("final_score", sa.Float, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("correctness_score", sa.Float, nullable=False),
        sa.Column("safety_score", sa.Float, nullable=False),
        sa.Column("efficiency_score", sa.Float, nullable=False),
        sa.Column("weight_correctness", sa.Float, nullable=False),
        sa.Column("weight_safety", sa.Float, nullable=False),
        sa.Column("weight_efficiency", sa.Float, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("check_results", JSON, nullable=False),
        sa.Column("graded_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("run_id"),
    )

    # ── score_breakdowns ──────────────────────────────────────────────────────
    op.create_table(
        "score_breakdowns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("scoring_result_id", UUID(as_uuid=True), sa.ForeignKey("scoring_results.id"), nullable=False),
        sa.Column("check_id", sa.String(128), nullable=False),
        sa.Column("layer", sa.String(32), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("weight", sa.Float, nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("points_earned", sa.Float, nullable=False),
        sa.Column("points_possible", sa.Float, nullable=False),
    )
    op.create_index("ix_score_breakdowns_scoring_result_id", "score_breakdowns", ["scoring_result_id"])

    # ── badges ────────────────────────────────────────────────────────────────
    op.create_table(
        "badges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("icon_url", sa.String(512), nullable=True),
        sa.Column("criteria", JSON, nullable=False),
        sa.UniqueConstraint("slug"),
    )

    # ── user_badges ───────────────────────────────────────────────────────────
    op.create_table(
        "user_badges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("badge_id", UUID(as_uuid=True), sa.ForeignKey("badges.id"), nullable=False),
        sa.Column("awarded_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("challenge_runs.id"), nullable=True),
    )
    op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"])

    # ── portfolio_items ───────────────────────────────────────────────────────
    op.create_table(
        "portfolio_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("challenge_runs.id"), nullable=False),
        sa.Column("shareable_slug", sa.String(256), nullable=False),
        sa.Column("is_public", sa.Boolean, server_default="true"),
        sa.Column("lab_title", sa.String(256), nullable=False),
        sa.Column("lab_slug", sa.String(128), nullable=False),
        sa.Column("lab_category", sa.String(64), nullable=False),
        sa.Column("lab_difficulty", sa.String(32), nullable=False),
        sa.Column("final_score", sa.Float, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("correctness_score", sa.Float, nullable=False),
        sa.Column("safety_score", sa.Float, nullable=False),
        sa.Column("efficiency_score", sa.Float, nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("run_id"),
        sa.UniqueConstraint("shareable_slug"),
    )
    op.create_index("ix_portfolio_items_user_id", "portfolio_items", ["user_id"])
    op.create_index("ix_portfolio_items_shareable_slug", "portfolio_items", ["shareable_slug"])

    # ── audit_events ──────────────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("payload", JSON, nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("occurred_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("portfolio_items")
    op.drop_table("user_badges")
    op.drop_table("badges")
    op.drop_table("score_breakdowns")
    op.drop_table("scoring_results")
    op.drop_table("challenge_runs")
    op.drop_table("lab_versions")
    op.drop_table("labs")
    op.drop_table("subscriptions")
    op.drop_table("users")
