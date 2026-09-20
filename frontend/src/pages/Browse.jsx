import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import Icon from "../Icon";
import { Empty, ListingCard, Spinner } from "../components";

const MODES = [
  { key: "", label: "All" },
  { key: "free", label: "Free" },
  { key: "sale", label: "For sale" },
  { key: "trade", label: "Trade" },
];

const SORTS = [
  { key: "distance", label: "Closest" },
  { key: "match", label: "Best match" },
  { key: "price_low", label: "Cheapest" },
  { key: "newest", label: "Newest" },
];

export default function Browse() {
  const [params, setParams] = useSearchParams();
  const [cats, setCats] = useState([]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const q = params.get("q") || "";
  const category = params.get("category") || "all";
  const mode = params.get("mode") || "";
  const radius = params.get("radius_km") || "8";
  const maxPrice = params.get("max_price") || "";
  const sort = params.get("sort") || (q ? "match" : "distance");

  // The price box needs its own state: writing straight to the URL on every
  // keystroke would remount the input and steal focus after one character.
  const [priceDraft, setPriceDraft] = useState(maxPrice);
  const priceTimer = useRef(null);

  useEffect(() => {
    setPriceDraft(maxPrice);
  }, [maxPrice]);

  const onPrice = (text) => {
    const clean = text.replace(/[^0-9.]/g, "");
    setPriceDraft(clean);
    clearTimeout(priceTimer.current);
    priceTimer.current = setTimeout(() => set("max_price", clean), 350);
  };

  useEffect(() => () => clearTimeout(priceTimer.current), []);

  const set = (key, value) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  };

  useEffect(() => {
    api.categories().then(setCats).catch(() => {});
  }, []);

  // A stuck filter is the commonest reason a page looks empty, so show
  // exactly what's narrowing the results and make each one one click to drop.
  const activeFilters = [];
  if (q) activeFilters.push({ key: "q", label: `"${q}"` });
  if (category !== "all") {
    const c = cats.find((x) => x.slug === category);
    activeFilters.push({ key: "category", label: c ? `${c.icon} ${c.name}` : category });
  }
  if (mode) activeFilters.push({ key: "mode", label: MODES.find((m) => m.key === mode)?.label || mode });
  if (maxPrice) activeFilters.push({ key: "max_price", label: `under $${maxPrice}` });

  useEffect(() => {
    setLoading(true);
    api
      .listings({
        q,
        category,
        mode: mode || undefined,
        radius_km: radius,
        max_cents: maxPrice ? Math.round(Number(maxPrice) * 100) : undefined,
        sort,
      })
      .then(setData)
      .catch(() => setData({ count: 0, results: [] }))
      .finally(() => setLoading(false));
  }, [q, category, mode, radius, maxPrice, sort]);

  return (
    <>
      <div className="searchbar mb">
        <span className="mag">🔍</span>
        <input
          type="search"
          defaultValue={q}
          placeholder="Search for desks, fridges, textbooks…"
          onKeyDown={(e) => e.key === "Enter" && set("q", e.currentTarget.value)}
          aria-label="Search listings"
        />
      </div>

      <div className="chips mb">
        <button className={`chip ${category === "all" ? "on" : ""}`} onClick={() => set("category", "")}>
          All
        </button>
        {cats.map((c) => (
          <button
            key={c.slug}
            className={`chip ${category === c.slug ? "on" : ""}`}
            onClick={() => set("category", c.slug)}
          >
            <Icon slug={c.slug} size={16} style={{ display: "inline-block", verticalAlign: "-3px", marginRight: 5 }} />
            {c.name}
          </button>
        ))}
      </div>

      <div className="card pad mb">
        <div className="field-row" style={{ gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <div>
            <label>Type</label>
            <div className="chips">
              {MODES.map((m) => (
                <button
                  key={m.key}
                  className={`chip ${mode === m.key ? "on" : ""}`}
                  onClick={() => set("mode", m.key)}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label htmlFor="radius">Within {radius} km of you</label>
            <input
              id="radius"
              className="slider"
              type="range"
              min="0.5"
              max="20"
              step="0.5"
              value={radius}
              onChange={(e) => set("radius_km", e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="budget">Max price ($)</label>
            <input
              id="budget"
              type="text"
              inputMode="decimal"
              placeholder="any"
              value={priceDraft}
              onChange={(e) => onPrice(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  clearTimeout(priceTimer.current);
                  set("max_price", priceDraft);
                }
              }}
            />
            {priceDraft && (
              <p className="small muted" style={{ margin: "6px 0 0" }}>
                Showing items ${priceDraft} and under, plus everything free.
              </p>
            )}
          </div>
        </div>

        <div style={{ marginTop: 16, borderTop: "1px solid var(--line)", paddingTop: 14 }}>
          <label>Sort by</label>
          <div className="chips">
            {SORTS.map((o) => (
              <button
                key={o.key}
                className={`chip ${sort === o.key ? "on" : ""}`}
                onClick={() => set("sort", o.key)}
              >
                {o.label}
              </button>
            ))}
          </div>
          {sort === "match" && (
            <p className="small muted" style={{ margin: "8px 0 0" }}>
              Best match blends distance, price, condition and how soon pickup closes —
              so a free item slightly further away can outrank a closer paid one.
            </p>
          )}
        </div>
      </div>

      {activeFilters.length > 0 && (
        <div className="row wrap-row mb" style={{ gap: 8 }}>
          <span className="small muted">Filtering by</span>
          {activeFilters.map((f) => (
            <button key={f.key} className="chip on" onClick={() => set(f.key, "")}>
              {f.label} ✕
            </button>
          ))}
          <button className="btn quiet sm" onClick={() => setParams(new URLSearchParams())}>
            Clear all
          </button>
        </div>
      )}

      {loading ? (
        <Spinner />
      ) : data.results.length === 0 ? (
        <Empty icon="🔍" title="Nothing matches yet">
          Try widening the distance or clearing the price filter.
        </Empty>
      ) : (
        <>
          <div className="banner">
            {data.count} item{data.count === 1 ? "" : "s"} within {radius} km
            {data.nearest_km != null &&
              ` · nearest ${data.nearest_km} km, furthest ${data.furthest_km} km`}
          </div>
          <div className="grid">
            {data.results.map((l) => <ListingCard key={l.id} listing={l} />)}
          </div>
        </>
      )}
    </>
  );
}
