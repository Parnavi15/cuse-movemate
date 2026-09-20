import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, money } from "../api";
import { Banner, ListingCard, Spinner, Stars } from "../components";
import Icon from "../Icon";
import TravelOptions from "../TravelOptions";
import { useAuth } from "../store";

export default function ListingDetail() {
  const { id } = useParams();
  const { user, refresh } = useAuth();
  const navigate = useNavigate();

  const [listing, setListing] = useState(null);
  const [related, setRelated] = useState(null);
  const [message, setMessage] = useState("");
  const [credit, setCredit] = useState(0);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listing(id).then(setListing).catch(() => setListing(false));
    api.related(id).then(setRelated).catch(() => {});
  }, [id]);

  if (listing === false) return <Banner kind="bad">That listing is gone.</Banner>;
  if (!listing) return <Spinner />;

  const mine = user && listing.owner.id === user.id;
  const walletCredit = user?.wallet?.credit_cents || 0;
  const maxCredit = Math.min(walletCredit, Math.floor(listing.price_cents * 0.5));

  const claim = async () => {
    setBusy(true);
    setError("");
    try {
      await api.claim({ listing_id: listing.id, message, credit_cents: credit });
      await refresh();
      setNote("Request sent. You'll see it under Requests once the owner replies.");
      setTimeout(() => navigate("/requests"), 900);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Link to="/browse" className="small">← Back to browse</Link>

      <div className="grid2 mt" style={{ gridTemplateColumns: "minmax(0,1.3fr) minmax(0,1fr)" }}>
        <div>
          <div className="card" style={{ overflow: "hidden" }}>
            <div className="hero-photo">
              {listing.photo_url ? (
                <img src={listing.photo_url} alt={listing.title} />
              ) : (
                <Icon slug={listing.category.slug} size={72} strokeWidth={1.2} />
              )}
            </div>
            <div className="pad">
              <div className="row wrap-row mb">
                <span className={`tag ${listing.mode === "free" ? "free" : ""}`}>
                  {listing.mode === "free" ? "Free" : listing.mode === "trade" ? "Trade" : "For sale"}
                </span>
                <span className="tag grey">{listing.category.icon} {listing.category.name}</span>
                <span className="tag grey">{listing.condition}</span>
                {listing.status !== "active" && <span className="tag grey">{listing.status}</span>}
              </div>
              <h1>{listing.title}</h1>
              <p className="mt">{listing.description}</p>
              <div className="spread mt" style={{ borderTop: "1px solid var(--line)", paddingTop: 14 }}>
                <span style={{ fontSize: 26, fontWeight: 900, color: "var(--o)" }}>
                  {listing.price_display}
                </span>
                <span className="muted">
                  📍 {listing.address_label}
                  {listing.distance_km != null && ` · ${listing.distance_km} km away`}
                </span>
              </div>
              {listing.pickup_deadline && (
                <p className="muted small mt">⏳ Pickup by {listing.pickup_deadline}</p>
              )}
            </div>
          </div>

          <TravelOptions listingId={listing.id} />

          {related?.suggestions?.some((s) => s.available > 0) && (
            <>
              <div className="section-head"><h2>You might also need</h2></div>
              {related.suggestions.filter((s) => s.available > 0).slice(0, 3).map((s) => (
                <div key={s.term} style={{ marginBottom: 20 }}>
                  <h3 style={{ marginBottom: 10 }}>{s.term}</h3>
                  <div className="grid">
                    {s.listings.map((l) => <ListingCard key={l.id} listing={l} />)}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        <div>
          <div className="card pad">
            <h3>Listed by</h3>
            <div className="row mt" style={{ gap: 10 }}>
              <span style={{ fontSize: 32 }}>{listing.owner.avatar_emoji}</span>
              <div>
                <b>{listing.owner.username}</b>
                {listing.owner.is_verified_student && (
                  <span className="tag free" style={{ marginLeft: 6 }}>🎓 verified</span>
                )}
                <div className="small muted">
                  {listing.owner.rating_count > 0 ? (
                    <span className="row" style={{ gap: 6 }}>
                      <Stars value={Math.round(listing.owner.rating_avg)} readOnly />
                      {listing.owner.rating_avg} ({listing.owner.rating_count})
                    </span>
                  ) : "No reviews yet"}
                </div>
              </div>
            </div>
          </div>

          <div className="card pad mt">
            {note && <Banner kind="good">{note}</Banner>}
            {error && <Banner kind="bad">{error}</Banner>}

            {mine ? (
              <>
                <h3>This is your listing</h3>
                <p className="muted small">Requests from other students show up under Requests.</p>
                <Link to={`/edit/${listing.id}`} className="btn full mt">Edit listing</Link>
              </>
            ) : !user ? (
              <>
                <h3>Want this?</h3>
                <p className="muted small">Sign in to claim it and earn MovePoints.</p>
                <Link to="/login" className="btn full mt">Sign in</Link>
              </>
            ) : listing.status !== "active" ? (
              <>
                <h3>Already spoken for</h3>
                <p className="muted small">Someone else got there first. Try the smart match for alternatives.</p>
                <Link to="/match" className="btn ghost full mt">Find something similar</Link>
              </>
            ) : (
              <>
                <h3>Claim this item</h3>
                <div className="field mt">
                  <label htmlFor="msg">Message to {listing.owner.username}</label>
                  <textarea
                    id="msg"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Hi! I'm moving in Friday, could I pick this up Thursday evening?"
                  />
                </div>

                {listing.mode === "sale" && maxCredit > 0 && (
                  <div className="field">
                    <label htmlFor="credit">
                      Apply wallet credit — {money(credit)} of {money(maxCredit)} available
                    </label>
                    <input
                      id="credit"
                      className="slider"
                      type="range"
                      min="0"
                      max={maxCredit}
                      step="100"
                      value={credit}
                      onChange={(e) => setCredit(Number(e.target.value))}
                    />
                    <div className="spread small muted">
                      <span>You pay {money(listing.price_cents - credit)}</span>
                      <span>Credit covers half at most</span>
                    </div>
                  </div>
                )}

                <button className="btn full" onClick={claim} disabled={busy}>
                  {busy ? "Sending…" : listing.mode === "free" ? "Ask for this item" : "Request to buy"}
                </button>
                <p className="muted small mt" style={{ marginBottom: 0 }}>
                  You'll earn points once you both confirm the handoff.
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
