"use client";

import { useAuth } from "@/contexts/AuthContext";
import { API_BASE } from "@/lib/config";
import UserAvatar from "@/components/UserAvatar";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ComponentType } from "react";
import { IconEye, IconStar, IconMicroscope, IconComment } from "@/components/icons/MarineIcons";

/* ── Types ────────────────────────────────────────────────── */

interface Comment {
  id: number;
  submission_id: string;
  user_id: number;
  display_name: string | null;
  reputation_tier: string | null;
  avatar_url: string | null;
  body: string;
  created_at: string;
  updated_at: string | null;
}

const TIER_STYLE: Record<string, { color: string; Icon: ComponentType<{ className?: string }> }> = {
  newcomer: { color: "text-slate-400", Icon: ({ className }) => <span className={className}>●</span> },
  observer: { color: "text-ocean-400", Icon: IconEye },
  contributor: { color: "text-green-400", Icon: IconStar },
  expert: { color: "text-purple-400", Icon: IconMicroscope },
  authority: { color: "text-yellow-400", Icon: IconStar },
};

/* ── Component ────────────────────────────────────────────── */

export default function CommentSection({
  submissionId,
}: {
  submissionId: string;
}) {
  const { user, authHeader } = useAuth();
  const [comments, setComments] = useState<Comment[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [newBody, setNewBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editBody, setEditBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  /* ── Fetch comments ──────────────────────────────────────── */

  const fetchComments = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/submissions/${submissionId}/comments?limit=200`,
      );
      if (!res.ok) return;
      const data = await res.json();
      setComments(data.comments ?? []);
      setTotal(data.total ?? 0);
    } catch {
      /* network error — silently ignore for read */
    } finally {
      setLoading(false);
    }
  }, [submissionId]);

  useEffect(() => {
    fetchComments();
  }, [fetchComments]);

  /* ── Post a new comment ──────────────────────────────────── */

  const handlePost = async () => {
    if (!authHeader || !newBody.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/submissions/${submissionId}/comments`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: authHeader,
          },
          body: JSON.stringify({ body: newBody.trim() }),
        },
      );
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        setError(err?.detail ?? "Failed to post comment");
        return;
      }
      setNewBody("");
      await fetchComments();
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch {
      setError("Network error");
    } finally {
      setSubmitting(false);
    }
  };

  /* ── Edit a comment ──────────────────────────────────────── */

  const handleEdit = async (commentId: number) => {
    if (!authHeader || !editBody.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/submissions/${submissionId}/comments/${commentId}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: authHeader,
          },
          body: JSON.stringify({ body: editBody.trim() }),
        },
      );
      if (!res.ok) {
        setError("Failed to update comment");
        return;
      }
      setEditingId(null);
      setEditBody("");
      await fetchComments();
    } catch {
      setError("Network error");
    } finally {
      setSubmitting(false);
    }
  };

  /* ── Delete a comment ────────────────────────────────────── */

  const handleDelete = async (commentId: number) => {
    if (!authHeader) return;
    if (!window.confirm("Delete this comment?")) return;
    try {
      await fetch(
        `${API_BASE}/api/v1/submissions/${submissionId}/comments/${commentId}`,
        {
          method: "DELETE",
          headers: { Authorization: authHeader },
        },
      );
      await fetchComments();
    } catch {
      /* ignore */
    }
  };

  /* ── Render ──────────────────────────────────────────────── */

  const fmtDate = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 60_000) return "just now";
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    if (diff < 604_800_000) return `${Math.floor(diff / 86_400_000)}d ago`;
    return d.toLocaleDateString();
  };

  return (
    <div className="rounded-xl border border-ocean-800 bg-abyss-900/60 p-5">
      <h3 className="mb-4 flex items-center gap-1.5 text-sm font-semibold text-white">
        <IconComment className="h-4 w-4" /> Comments{total > 0 && ` (${total})`}
      </h3>

      {/* Comment list */}
      {loading ? (
        <p className="text-sm text-slate-500">Loading comments…</p>
      ) : comments.length === 0 ? (
        <p className="mb-4 text-sm text-slate-500">
          No comments yet. Be the first to share your thoughts!
        </p>
      ) : (
        <div className="mb-4 max-h-96 space-y-3 overflow-y-auto pr-1">
          {comments.map((c) => {
            const tier =
              TIER_STYLE[c.reputation_tier ?? ""] ?? TIER_STYLE.newcomer;
            const isAuthor = user?.id === c.user_id;
            const isEditing = editingId === c.id;

            return (
              <div
                key={c.id}
                className="rounded-lg border border-ocean-900/50 bg-abyss-800/60 px-4 py-3"
              >
                {/* Header */}
                <div className="mb-1.5 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs">
                    <Link
                      href={`/users/${c.user_id}`}
                      className="flex items-center gap-1.5 hover:underline"
                    >
                      <UserAvatar
                        avatarUrl={c.avatar_url}
                        displayName={c.display_name}
                        size={22}
                      />
                      <tier.Icon className={`h-3.5 w-3.5 ${tier.color}`} />
                      <span className="font-medium text-slate-300">
                        {c.display_name ?? "Anonymous"}
                      </span>
                    </Link>
                    <span className="text-slate-600">·</span>
                    <span className="text-slate-500">{fmtDate(c.created_at)}</span>
                    {c.updated_at && (
                      <span className="text-slate-600">(edited)</span>
                    )}
                  </div>

                  {/* Actions for the author */}
                  {isAuthor && !isEditing && (
                    <div className="flex gap-2 text-xs">
                      <button
                        onClick={() => {
                          setEditingId(c.id);
                          setEditBody(c.body);
                        }}
                        className="text-slate-500 hover:text-ocean-400"
                      >
                        edit
                      </button>
                      <button
                        onClick={() => handleDelete(c.id)}
                        className="text-slate-500 hover:text-red-400"
                      >
                        delete
                      </button>
                    </div>
                  )}
                </div>

                {/* Body — either editing or read-only */}
                {isEditing ? (
                  <div className="space-y-2">
                    <textarea
                      value={editBody}
                      onChange={(e) => setEditBody(e.target.value)}
                      rows={2}
                      className="w-full rounded-lg border border-ocean-800 bg-abyss-900 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-ocean-500 focus:outline-none"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEdit(c.id)}
                        disabled={submitting || !editBody.trim()}
                        className="rounded-lg bg-ocean-700 px-3 py-1 text-xs font-medium text-white hover:bg-ocean-600 disabled:opacity-50"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => {
                          setEditingId(null);
                          setEditBody("");
                        }}
                        className="rounded-lg bg-abyss-700 px-3 py-1 text-xs text-slate-300 hover:bg-abyss-600"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap text-sm text-slate-300">
                    {c.body}
                  </p>
                )}
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      )}

      {/* Error banner */}
      {error && (
        <p className="mb-3 text-xs text-red-400">{error}</p>
      )}

      {/* New comment form */}
      {user ? (
        <div className="space-y-2">
          <textarea
            value={newBody}
            onChange={(e) => setNewBody(e.target.value)}
            placeholder="Add a comment…"
            rows={2}
            maxLength={2000}
            className="w-full rounded-lg border border-ocean-800 bg-abyss-800 px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-ocean-500 focus:outline-none"
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-600">
              {newBody.length}/2000
            </span>
            <button
              onClick={handlePost}
              disabled={submitting || !newBody.trim()}
              className="rounded-lg bg-ocean-700 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-ocean-600 disabled:opacity-50"
            >
              {submitting ? "Posting…" : "Post"}
            </button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-slate-500">
          <Link href="/login" className="text-ocean-400 hover:underline">
            Sign in
          </Link>{" "}
          to leave a comment.
        </p>
      )}
    </div>
  );
}
