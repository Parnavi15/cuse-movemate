import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "./api";
import { useAuth } from "./store";

const ICONS = {
  request_received: "🙋",
  request_accepted: "✅",
  request_rejected: "😕",
  handoff_pending: "⏳",
  handoff_complete: "♻️",
  review_received: "⭐",
  points_posted: "💰",
  badge_earned: "🏆",
  item_claimed: "📦",
  message: "💬",
  time_proposed: "🗓️",
  time_agreed: "✅",
};

function ago(iso) {
  const seconds = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export default function NotificationBell() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const panel = useRef(null);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    try {
      const data = await api.notifications();
      setItems(data.results);
      setUnread(data.unread);
    } catch {
      /* offline or signed out; the next poll will catch up */
    }
  }, []);

  // Polling, not websockets. A 20-second delay is invisible to a student
  // arranging a pickup, and it's a fraction of the complexity.
  useEffect(() => {
    if (!user) return undefined;
    load();
    const timer = setInterval(load, 20000);
    return () => clearInterval(timer);
  }, [user, load]);

  useEffect(() => {
    const away = (e) => {
      if (panel.current && !panel.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, []);

  if (!user) return null;

  const openItem = async (n) => {
    setOpen(false);
    if (!n.is_read) {
      await api.markNotificationRead(n.id).catch(() => {});
      load();
    }
    navigate(n.link || "/requests");
  };

  const clearAll = async () => {
    await api.markAllNotificationsRead().catch(() => {});
    load();
  };

  return (
    <div style={{ position: "relative" }} ref={panel}>
      <button
        className="bell"
        aria-label={unread ? `${unread} unread notifications` : "Notifications"}
        onClick={() => setOpen(!open)}
      >
        🔔
        {unread > 0 && <span className="bell-dot">{unread > 9 ? "9+" : unread}</span>}
      </button>

      {open && (
        <div className="bell-panel card">
          <div className="spread" style={{ padding: "12px 14px", borderBottom: "1px solid var(--line)" }}>
            <b>Notifications</b>
            {unread > 0 && (
              <button className="btn quiet sm" onClick={clearAll}>Mark all read</button>
            )}
          </div>

          {items.length === 0 ? (
            <div className="pad muted small" style={{ textAlign: "center" }}>
              Nothing yet. You'll hear here when someone wants one of your items.
            </div>
          ) : (
            <div style={{ maxHeight: 380, overflowY: "auto" }}>
              {items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => openItem(n)}
                  className={`bell-row ${n.is_read ? "" : "new"}`}
                >
                  <span className="bell-ic">{ICONS[n.kind] || "🔔"}</span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <b style={{ display: "block", fontSize: 14.5 }}>{n.title}</b>
                    {n.body && <span className="small muted" style={{ display: "block" }}>{n.body}</span>}
                    <span className="small muted">{ago(n.created_at)}</span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
