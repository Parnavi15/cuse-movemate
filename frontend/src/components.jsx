import { useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { api } from "./api";
import Icon from "./Icon";
import NotificationBell from "./NotificationBell";
import ProfileMenu from "./ProfileMenu";
import { useAuth } from "./store";

export function Nav() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const close = () => setOpen(false);

  const out = async () => {
    await signOut();
    close();
    navigate("/");
  };

  return (
    <nav className="nav">
      <div className="wrap">
        <Link to="/" className="brand" onClick={close}>
          ♻️ Cuse-MoveMate
        </Link>

        <div className={`link-group row ${open ? "open" : ""}`}>
          <NavLink to="/browse" className="link" onClick={close}>Browse</NavLink>
          <NavLink to="/match" className="link" onClick={close}>What do I need?</NavLink>
          {user && <NavLink to="/new" className="link" onClick={close}>List an item</NavLink>}
          {user && <NavLink to="/items" className="link" onClick={close}>My items</NavLink>}
          {user && <NavLink to="/requests" className="link" onClick={close}>Requests</NavLink>}

          {user ? (
            <>
              <NavLink to="/wallet" className="pts" onClick={close}>
                ♻️ {user.wallet?.points_posted ?? 0}
                {user.wallet?.credit_cents ? ` · $${(user.wallet.credit_cents / 100).toFixed(2)}` : " pts"}
              </NavLink>
              <NotificationBell />
              <ProfileMenu />
            </>
          ) : (
            <>
              <NavLink to="/login" className="link" onClick={close}>Sign in</NavLink>
              <Link to="/register" className="btn sm" onClick={close}>Join</Link>
            </>
          )}
        </div>

        <button
          className="navtoggle"
          aria-label="Menu"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          ☰
        </button>
      </div>
    </nav>
  );
}

const MODE_TAG = {
  free: { label: "Free", cls: "tag free" },
  sale: { label: "For sale", cls: "tag" },
  trade: { label: "Trade", cls: "tag" },
};

export function ListingCard({ listing }) {
  const mode = MODE_TAG[listing.mode] || MODE_TAG.sale;
  return (
    <div className="listing">
      <Link to={`/listing/${listing.id}`} className="thumb" aria-label={listing.title}>
        {listing.photo_url ? (
          <img src={listing.photo_url} alt="" loading="lazy" />
        ) : (
          <span style={{ color: "var(--o)" }}>
            <Icon slug={listing.category?.slug} size={42} strokeWidth={1.3} />
          </span>
        )}
      </Link>
      <div className="body">
        <div className="row" style={{ marginBottom: 6 }}>
          <span className={mode.cls}>{mode.label}</span>
          {listing.status !== "active" && <span className="tag grey">{listing.status}</span>}
        </div>
        <h4>
          <Link to={`/listing/${listing.id}`} style={{ color: "inherit" }}>
            {listing.title}
          </Link>
        </h4>
        <div className="small muted">
          {listing.category?.name} · {listing.condition}
        </div>
        {listing.match_reason && <div className="reason">{listing.match_reason}</div>}
        <div className="grow" />
        <div className="meta">
          <span className="price">{listing.price_display}</span>
          {listing.distance_km != null && (
            <span className="dist">📍 {listing.distance_km} km</span>
          )}
        </div>
      </div>
    </div>
  );
}

export function Stars({ value = 0, onChange, readOnly = false }) {
  return (
    <div className={`stars ${readOnly ? "read" : ""}`} role="group" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={`star ${n <= value ? "lit" : ""}`}
          aria-label={`${n} star${n > 1 ? "s" : ""}`}
          disabled={readOnly}
          onClick={() => onChange && onChange(n)}
        >
          ★
        </button>
      ))}
    </div>
  );
}

export function Banner({ kind = "soft", children }) {
  if (!children) return null;
  return <div className={`banner ${kind}`}>{children}</div>;
}

export function Empty({ icon = "📦", title, children }) {
  return (
    <div className="empty">
      <span className="ic">{icon}</span>
      <h3 style={{ color: "var(--ink)" }}>{title}</h3>
      <p style={{ marginTop: 8 }}>{children}</p>
    </div>
  );
}

export function Spinner() {
  return <div className="spinner" role="status" aria-label="Loading" />;
}

export function VerifyNudge() {
  const { user } = useAuth();
  const [config, setConfig] = useState(null);

  useEffect(() => {
    if (user && !user.is_verified_student) {
      api.config().then(setConfig).catch(() => {});
    }
  }, [user]);

  if (!user || user.is_verified_student) return null;

  const live = config?.email_live;
  return (
    <div className="banner soft" style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
      <span>
        🎓 Verify {user.campus_email || "your campus email"} to list items, claim items
        and redeem points.
        {config && !live && (
          <b style={{ display: "block", fontWeight: 700, marginTop: 4 }}>
            No mail server is configured, so nothing was emailed — request a code on the
            Wallet page and it appears on screen.
          </b>
        )}
      </span>
      <Link to="/wallet" className="btn sm">Verify now</Link>
    </div>
  );
}

export function StateTag({ state }) {
  const labels = {
    requested: "Waiting on owner",
    accepted: "Accepted — arrange pickup",
    completed: "Handed off",
    reviewed: "Done",
    rejected: "Declined",
    cancelled: "Cancelled",
    disputed: "Disputed",
  };
  return <span className={`tag state-${state}`}>{labels[state] || state}</span>;
}
