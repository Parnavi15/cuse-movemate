import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { Banner } from "../components";
import LocationPicker from "../LocationPicker";
import PhotoPicker from "../PhotoPicker";

const BLANK = {
  title: "",
  description: "",
  category_slug: "furniture",
  mode: "free",
  price_cents: 0,
  trade_for: "",
  condition: "good",
  photo_url: "",
  address_label: "Near campus",
  latitude: 43.0392,
  longitude: -76.1351,
  pickup_deadline: "",
  ownership_confirmed: false,
};

export default function NewListing() {
  const { id } = useParams();
  const editing = Boolean(id);
  const navigate = useNavigate();

  const [form, setForm] = useState(BLANK);
  const [dollars, setDollars] = useState("");
  const [cats, setCats] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.categories().then(setCats).catch(() => {});
    if (editing) {
      api.listing(id).then((l) => {
        setDollars(l.price_cents ? (l.price_cents / 100).toFixed(2) : "");
        setForm({
          title: l.title,
          description: l.description,
          category_slug: l.category.slug,
          mode: l.mode,
          price_cents: l.price_cents,
          trade_for: l.trade_for,
          condition: l.condition,
          photo_url: l.photo_url,
          address_label: l.address_label,
          latitude: l.latitude,
          longitude: l.longitude,
          pickup_deadline: l.pickup_deadline || "",
          ownership_confirmed: l.ownership_confirmed,
        });
      });
    }
  }, [id, editing]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const payload = {
      ...form,
      price_cents: form.mode === "sale" ? Math.round(Number(form.price_cents) || 0) : 0,
      pickup_deadline: form.pickup_deadline || null,
    };
    try {
      const saved = editing
        ? await api.updateListing(id, payload)
        : await api.createListing(payload);
      navigate(`/listing/${saved.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const eligible = form.photo_url && form.description && form.pickup_deadline;

  return (
    <div style={{ maxWidth: 680, margin: "0 auto" }}>
      <h1>{editing ? "Edit listing" : "List an item"}</h1>
      <p className="muted">
        A photo, a description and a pickup deadline make the listing point-eligible.
      </p>

      {error && <Banner kind="bad">{error}</Banner>}

      <form className="card pad mt" onSubmit={submit}>
        <div className="field">
          <label htmlFor="title">What is it?</label>
          <input id="title" type="text" required value={form.title}
            onChange={(e) => set("title", e.target.value)} placeholder="IKEA study desk" />
        </div>

        <div className="field">
          <label htmlFor="desc">Describe the condition honestly</label>
          <textarea id="desc" value={form.description}
            onChange={(e) => set("description", e.target.value)}
            placeholder="Solid white desk, one small scratch on the left side. Comes apart with an allen key." />
        </div>

        <div className="field">
          <label>How are you passing it on?</label>
          <div className="chips">
            {[["free", "🎁 Free"], ["sale", "💵 For sale"], ["trade", "🔄 Trade"]].map(([k, l]) => (
              <button key={k} type="button" className={`chip ${form.mode === k ? "on" : ""}`}
                onClick={() => set("mode", k)}>{l}</button>
            ))}
          </div>
          <p className="small muted" style={{ marginTop: 8, marginBottom: 0 }}>
            {form.mode === "free"
              ? "Giving it away earns the most points — 50, plus the 25 circulation bonus."
              : form.mode === "trade" ? "Trades earn 30 points for both students."
              : "Selling earns 20 points, plus the 25 circulation bonus."}
          </p>
        </div>

        {form.mode === "sale" && (
          <div className="field">
            <label htmlFor="price">Price</label>
            <div style={{ position: "relative" }}>
              <span style={{
                position: "absolute", left: 13, top: 11, color: "var(--muted)",
                fontSize: 15.5, pointerEvents: "none",
              }}>$</span>
              <input
                id="price"
                type="text"
                inputMode="decimal"
                value={dollars}
                onChange={(e) => {
                  const clean = e.target.value.replace(/[^0-9.]/g, "");
                  setDollars(clean);
                  set("price_cents", Math.round((Number(clean) || 0) * 100));
                }}
                placeholder="20.00"
                style={{ paddingLeft: 26 }}
              />
            </div>
            <p className="small muted" style={{ margin: "6px 0 0" }}>
              Buyers can cover up to half of this with MovePoints credit — you still
              get at least ${((form.price_cents || 0) / 200).toFixed(2)} in cash.
            </p>
          </div>
        )}

        {form.mode === "free" && (
          <p className="small muted" style={{ marginTop: -6, marginBottom: 15 }}>
            Free items have no price. Choose <b>For sale</b> above if you want to charge
            for this.
          </p>
        )}

        {form.mode === "trade" && (
          <div className="field">
            <label htmlFor="trade">What would you trade it for?</label>
            <input id="trade" type="text" value={form.trade_for}
              onChange={(e) => set("trade_for", e.target.value)} placeholder="a floor pump or a helmet" />
          </div>
        )}

        <div className="field-row">
          <div className="field">
            <label htmlFor="cat">Category</label>
            <select id="cat" value={form.category_slug} onChange={(e) => set("category_slug", e.target.value)}>
              {cats.map((c) => <option key={c.slug} value={c.slug}>{c.icon} {c.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="cond">Condition</label>
            <select id="cond" value={form.condition} onChange={(e) => set("condition", e.target.value)}>
              <option value="new">Like new</option>
              <option value="good">Good</option>
              <option value="fair">Fair</option>
              <option value="worn">Well used</option>
            </select>
          </div>
        </div>

        <PhotoPicker value={form.photo_url} onChange={(url) => set("photo_url", url)} />

        <LocationPicker
          value={form}
          onChange={(loc) => setForm((f) => ({ ...f, ...loc }))}
          label="Where can it be picked up?"
        />

        <div className="field">
          <label htmlFor="by">Pickup by</label>
          <input id="by" type="date" value={form.pickup_deadline}
            onChange={(e) => set("pickup_deadline", e.target.value)} />
        </div>

        <div className={`banner ${eligible ? "good" : "soft"} mt`}>
          {eligible
            ? "Point-eligible: this listing can earn MovePoints when it's handed off."
            : "Add a photo, a description and a pickup date to make this point-eligible."}
        </div>

        <label
          className="card"
          style={{ display: "flex", gap: 11, alignItems: "flex-start", padding: 14,
                   boxShadow: "none", cursor: "pointer", fontWeight: 400, marginBottom: 14 }}
        >
          <input
            type="checkbox"
            checked={form.ownership_confirmed}
            onChange={(e) => set("ownership_confirmed", e.target.checked)}
            style={{ width: 18, height: 18, marginTop: 2, accentColor: "var(--o)", flex: "none" }}
          />
          <span>
            <b style={{ display: "block", fontSize: 15 }}>
              This is mine and I'm passing it on
            </b>
            <span className="small muted">
              You'll be the seller on this listing. When someone claims it you'll get a
              notification and an email, and nothing completes until you both confirm
              the handoff in person.
            </span>
          </span>
        </label>

        <button
          className="btn full"
          type="submit"
          disabled={busy || !form.ownership_confirmed}
        >
          {busy ? "Saving…" : editing ? "Save changes" : "Publish listing"}
        </button>
      </form>
    </div>
  );
}
