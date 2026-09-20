import { useState } from "react";
import { api } from "../api";
import { Banner, ListingCard, Spinner } from "../components";

const EXAMPLES = [
  "I'm moving into an apartment next week and need a desk, chair and kitchen supplies for under $50",
  "I need a cheap desk near campus before Friday",
  "Looking for free stuff for a dorm room",
  "Need a paint brush this weekend",
];

export default function SmartMatch() {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = async (value) => {
    const query = (value ?? text).trim();
    if (!query) return;
    setText(query);
    setLoading(true);
    setError("");
    try {
      setResult(await api.match(query));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const u = result?.understood;

  return (
    <>
      <h1>What do you need?</h1>
      <p className="muted" style={{ maxWidth: "62ch" }}>
        Describe your move-in the way you'd text a friend. We turn it into item, budget,
        distance and timing, then rank what other students already have.
      </p>

      <div className="card pad mt">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="I'm moving into an apartment next week and need a desk, chair and kitchen supplies for under $50"
          aria-label="Describe what you need"
        />
        <div className="spread mt">
          <div className="chips">
            {EXAMPLES.map((ex) => (
              <button key={ex} className="chip" onClick={() => run(ex)}>
                {ex.length > 42 ? `${ex.slice(0, 42)}…` : ex}
              </button>
            ))}
          </div>
          <button className="btn" onClick={() => run()} disabled={loading || !text.trim()}>
            {loading ? "Matching…" : "Find matches"}
          </button>
        </div>
      </div>

      {error && <div className="mt"><Banner kind="bad">{error}</Banner></div>}
      {loading && <Spinner />}

      {result && !loading && (
        <>
          <div className="card pad mt2">
            <div className="spread">
              <h3>Here's what we understood</h3>
              <span className="tag grey">
                {u.engine === "claude" ? "parsed by Claude" : "parsed on-device"}
              </span>
            </div>
            <div className="understood">
              {u.items.map((i) => <span key={i}>🔎 {i}</span>)}
              {u.budget_cents != null && (
                <span>💰 {u.budget_cents === 0 ? "free only" : `under $${(u.budget_cents / 100).toFixed(0)}`}</span>
              )}
              {u.needed_by && <span>📅 by {u.needed_by}</span>}
              <span>📍 within {u.radius_km} km</span>
              <span>🏷️ {u.modes.join(", ")}</span>
            </div>
          </div>

          <div className={`banner mt2 ${result.fallback ? "soft" : ""}`}>
            {result.fallback
              ? "No exact match for that. Here's everything students near you have right now — ask, and they may have what you need unlisted."
              : `${result.total_found} matching item${result.total_found === 1 ? "" : "s"} from students near you`}
          </div>

          {result.groups.map((group) => (
            <div key={group.need} style={{ marginBottom: 26 }}>
              <div className="section-head" style={{ margin: "18px 0 10px" }}>
                <h3>{group.need}</h3>
                <span className="muted small">{group.found} found</span>
              </div>
              {group.listings.length === 0 ? (
                <div className="card pad muted">
                  Nobody nearby is passing this on right now. It'll show up here the
                  moment someone lists one — or widen your search from Browse.
                </div>
              ) : (
                <div className="grid">
                  {group.listings.map((l) => <ListingCard key={l.id} listing={l} />)}
                </div>
              )}
            </div>
          ))}

          {result.you_might_also_need?.length > 0 && (
            <div className="card pad">
              <h3>You might also need</h3>
              <p className="muted small">Students who needed these usually needed these next.</p>
              <div className="chips">
                {result.you_might_also_need.map((n) => (
                  <button key={n} className="chip" onClick={() => run(n)}>{n}</button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
