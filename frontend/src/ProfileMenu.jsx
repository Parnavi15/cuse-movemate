import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Icon from "./Icon";
import { useAuth } from "./store";

export default function ProfileMenu() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const panel = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const away = (e) => {
      if (panel.current && !panel.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, []);

  if (!user) return null;

  const out = async () => {
    setOpen(false);
    await signOut();
    navigate("/");
  };

  const go = (path) => {
    setOpen(false);
    navigate(path);
  };

  const a = user.activity || {};
  const pending = (a.open_requests || 0) + (a.awaiting_me || 0);

  return (
    <div style={{ position: "relative" }} ref={panel}>
      <button
        className="avatar-btn"
        onClick={() => setOpen(!open)}
        aria-label="Your profile"
        aria-expanded={open}
      >
        <span className="avatar">{user.avatar_emoji}</span>
        {pending > 0 && <span className="avatar-dot" />}
      </button>

      {open && (
        <div className="profile-panel card">
          <div className="profile-head">
            <span className="avatar lg">{user.avatar_emoji}</span>
            <div style={{ minWidth: 0 }}>
              <b style={{ display: "block", fontSize: 16 }}>{user.username}</b>
              <span className="small muted" style={{ display: "block", wordBreak: "break-all" }}>
                {user.campus_email || user.email}
              </span>
              <span className={`tag ${user.is_verified_student ? "free" : "grey"}`}
                    style={{ marginTop: 6, display: "inline-block" }}>
                {user.is_verified_student ? "🎓 Verified student" : "Unverified"}
              </span>
            </div>
          </div>

          <div className="profile-stats">
            <div>
              <b>{user.wallet?.points_posted ?? 0}</b>
              <span>MovePoints</span>
            </div>
            <div>
              <b>{a.sold ?? 0}</b>
              <span>Handed off</span>
            </div>
            <div>
              <b>{a.claimed ?? 0}</b>
              <span>Claimed</span>
            </div>
            <div>
              <b>{user.rating_count > 0 ? user.rating_avg : "—"}</b>
              <span>Rating</span>
            </div>
          </div>

          <div className="profile-loc">
            <Icon name="pin" size={15} />
            <span className="small">{user.address_label}</span>
          </div>

          <div className="profile-links">
            <button onClick={() => go("/profile")}>Profile &amp; settings</button>
            <button onClick={() => go("/items")}>
              My items {a.listed > 0 && <span className="count">{a.listed}</span>}
            </button>
            <button onClick={() => go("/requests")}>
              Requests {pending > 0 && <span className="count on">{pending}</span>}
            </button>
            <button onClick={() => go("/wallet")}>
              Wallet {user.wallet?.credit_cents > 0 && (
                <span className="count">${(user.wallet.credit_cents / 100).toFixed(2)}</span>
              )}
            </button>
          </div>

          <button className="profile-out" onClick={out}>Sign out</button>
        </div>
      )}
    </div>
  );
}
