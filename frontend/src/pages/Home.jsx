import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { ListingCard, Spinner } from "../components";
import Icon from "../Icon";
import { useAuth } from "../store";

function WelcomeStrip() {
  const { user } = useAuth();
  if (!user) return null;
  const a = user.activity || {};
  const pending = (a.open_requests || 0) + (a.awaiting_me || 0);
  return (
    <div className="welcome">
      <span className="avatar">{user.avatar_emoji}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <b>Welcome back, {user.username}</b>
        <div className="small muted">
          <Icon name="pin" size={12} style={{ display: "inline-block", verticalAlign: "-1px" }} />{" "}
          {user.address_label} · ♻️ {user.wallet?.points_posted ?? 0} MovePoints
        </div>
      </div>
      {pending > 0 ? (
        <Link to="/requests" className="btn sm">
          {pending} need{pending === 1 ? "s" : ""} your attention
        </Link>
      ) : (
        <Link to="/new" className="btn ghost sm">List an item</Link>
      )}
    </div>
  );
}

export default function Home() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [cats, setCats] = useState([]);
  const [recent, setRecent] = useState([]);
  const [board, setBoard] = useState([]);
  const [q, setQ] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    api.stats().then(setStats).catch(() => {});
    api.categories().then(setCats).catch(() => {});
    api.listings({ limit: 8 }).then((d) => setRecent(d.results)).catch(() => {});
    api.leaderboard().then(setBoard).catch(() => {});
  }, []);

  const search = (e) => {
    e.preventDefault();
    navigate(`/browse?q=${encodeURIComponent(q)}`);
  };

  return (
    <>
      <section className="hero">
        <h1>♻️ Cuse-MoveMate</h1>
        <p className="tagline">One student's move-out is another student's move-in</p>
        <p className="sub">Less waste. More reuse. Stronger community.</p>

        {stats && (
          <div className="hero-stats">
            <div><b>{stats.items_available}</b><span>Items available now</span></div>
            <div><b>{stats.items_circulated}</b><span>Kept in circulation</span></div>
            <div><b>{stats.weight_kg} kg</b><span>Diverted from disposal</span></div>
            <div><b>${(stats.savings_cents / 100).toFixed(0)}</b><span>Estimated student savings</span></div>
          </div>
        )}

        <form onSubmit={search} className="row" style={{ maxWidth: 520, margin: "0 auto", gap: 10 }}>
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search desks, fridges, textbooks…"
            aria-label="Search listings"
          />
          <button className="btn white" type="submit">Search</button>
        </form>
        <p className="sub" style={{ marginTop: 14 }}>
          Not sure what you need? <Link to="/match" style={{ color: "#fff", textDecoration: "underline" }}>
            Describe your move-in
          </Link>
        </p>
      </section>

      {user && <WelcomeStrip />}

      <div className="section-head"><h2>Browse by category</h2></div>
      <div className="catgrid">
        {cats.map((c) => (
          <Link key={c.slug} to={`/browse?category=${c.slug}`} className="cat">
            <span className="ic"><Icon slug={c.slug} size={26} /></span>
            {c.name}
          </Link>
        ))}
      </div>

      <div className="section-head">
        <h2>Near you right now</h2>
        <Link to="/browse">See all</Link>
      </div>
      {recent.length === 0 ? <Spinner /> : (
        <div className="grid">
          {recent.map((l) => <ListingCard key={l.id} listing={l} />)}
        </div>
      )}

      {board.length > 0 && (
        <>
          <div className="section-head"><h2>Top reusers this semester</h2></div>
          <div className="card pad">
            {board.map((u, i) => (
              <div key={u.username} className="spread" style={{ padding: "9px 0", borderBottom: i < board.length - 1 ? "1px solid var(--line)" : "none" }}>
                <span>
                  <b style={{ color: "var(--muted)", marginRight: 10 }}>{i + 1}</b>
                  {u.avatar_emoji} {u.username} {u.verified && <span className="tag free" style={{ marginLeft: 6 }}>verified</span>}
                </span>
                <span className="muted small">{u.items} items · <b style={{ color: "var(--o)" }}>{u.points} pts</b></span>
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
