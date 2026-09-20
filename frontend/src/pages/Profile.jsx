import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, money } from "../api";
import { Banner, Spinner, Stars } from "../components";
import Icon from "../Icon";
import LocationPicker from "../LocationPicker";
import { useAuth } from "../store";

const EMOJI = ["🧑‍🎓", "🎨", "🎧", "📗", "🛠️", "⚽", "🌱", "🍜", "📸", "🎹"];

export default function Profile() {
  const { user, refresh } = useAuth();
  const [impact, setImpact] = useState(null);
  const [draft, setDraft] = useState(null);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.impact().then(setImpact).catch(() => {});
  }, []);

  if (!user) return <Spinner />;

  const a = user.activity || {};

  const save = async (patch, message) => {
    setError("");
    try {
      await api.updateMe(patch);
      await refresh();
      setSaved(message);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <>
      <div className="profile-hero">
        <span className="avatar xl">{user.avatar_emoji}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 style={{ marginBottom: 4 }}>{user.username}</h1>
          <p className="muted" style={{ margin: 0 }}>
            {user.campus_email || user.email} · {user.school}
          </p>
          <div className="row wrap-row" style={{ gap: 7, marginTop: 10 }}>
            <span className={`tag ${user.is_verified_student ? "free" : "grey"}`}>
              {user.is_verified_student ? "🎓 Verified student" : "Unverified"}
            </span>
            <span className="tag grey">
              <Icon name="pin" size={12} style={{ display: "inline-block", verticalAlign: "-1px" }} />{" "}
              {user.address_label}
            </span>
            {user.rating_count > 0 && (
              <span className="tag grey">⭐ {user.rating_avg} ({user.rating_count})</span>
            )}
          </div>
        </div>
        <div className="profile-hero-points">
          <b>{user.wallet?.points_posted ?? 0}</b>
          <span>MovePoints</span>
          {user.wallet?.credit_cents > 0 && (
            <span className="credit">{money(user.wallet.credit_cents)} credit</span>
          )}
        </div>
      </div>

      {saved && <Banner kind="good">{saved}</Banner>}
      {error && <Banner kind="bad">{error}</Banner>}

      <div className="scorecards mt">
        <Link to="/items" className="scorecard">
          <b>{a.listed ?? 0}</b><span>Listed</span>
        </Link>
        <Link to="/requests" className="scorecard">
          <b>{a.sold ?? 0}</b><span>Handed off as seller</span>
        </Link>
        <Link to="/requests" className="scorecard">
          <b>{a.claimed ?? 0}</b><span>Claimed as buyer</span>
        </Link>
        <Link to="/requests" className={`scorecard ${a.open_requests ? "hot" : ""}`}>
          <b>{a.open_requests ?? 0}</b><span>Waiting on you</span>
        </Link>
        <Link to="/requests" className={`scorecard ${a.awaiting_me ? "hot" : ""}`}>
          <b>{a.awaiting_me ?? 0}</b><span>To confirm</span>
        </Link>
      </div>

      {impact && (
        <div className="card pad mt">
          <h3>Your impact so far</h3>
          <div className="impact-stats" style={{ marginTop: 14 }}>
            <div className="impact-plain"><b>{impact.items_circulated}</b><span>items kept in circulation</span></div>
            <div className="impact-plain"><b>{money(impact.savings_cents)}</b><span>estimated savings</span></div>
            <div className="impact-plain"><b>{impact.weight_kg} kg</b><span>diverted from disposal</span></div>
            <div className="impact-plain"><b>{impact.co2e_kg} kg</b><span>CO₂e avoided</span></div>
          </div>
          <p className="small muted" style={{ margin: "12px 0 0" }}>{impact.note}</p>
        </div>
      )}

      <div className="grid2 mt2">
        <div className="card pad">
          <h3>Where you are</h3>
          <p className="small muted">
            Distances on every listing are measured from here.
          </p>
          {draft ? (
            <>
              <LocationPicker
                value={draft}
                onChange={(loc) => setDraft({ ...draft, ...loc })}
                label="Your home location"
              />
              <div className="row">
                <button className="btn" onClick={async () => {
                  await save(draft, "Location updated.");
                  setDraft(null);
                }}>Save</button>
                <button className="btn quiet" onClick={() => setDraft(null)}>Cancel</button>
              </div>
            </>
          ) : (
            <>
              <div className="row" style={{ gap: 8, marginBottom: 12 }}>
                <Icon name="pin" size={18} />
                <div>
                  <b>{user.address_label}</b>
                  <div className="small muted">
                    {Number(user.latitude).toFixed(4)}, {Number(user.longitude).toFixed(4)}
                  </div>
                </div>
              </div>
              <button className="btn ghost sm" onClick={() => setDraft({
                latitude: user.latitude,
                longitude: user.longitude,
                address_label: user.address_label,
              })}>
                Change location
              </button>
            </>
          )}
        </div>

        <div className="card pad">
          <h3>Settings</h3>

          <div className="field mt">
            <label>Avatar</label>
            <div className="chips">
              {EMOJI.map((e) => (
                <button
                  key={e}
                  className={`chip ${user.avatar_emoji === e ? "on" : ""}`}
                  onClick={() => save({ avatar_emoji: e }, "Avatar updated.")}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <label htmlFor="bio">Short bio</label>
            <input
              id="bio"
              type="text"
              defaultValue={user.bio}
              placeholder="Grad student, moving out in May"
              maxLength={240}
              onBlur={(e) => e.target.value !== user.bio && save({ bio: e.target.value }, "Bio updated.")}
            />
          </div>

          <label className="row" style={{ gap: 9, cursor: "pointer", marginTop: 4 }}>
            <input
              type="checkbox"
              checked={user.email_notifications}
              onChange={(e) => save(
                { email_notifications: e.target.checked },
                e.target.checked ? "Email notifications on." : "Email notifications off."
              )}
              style={{ width: 17, height: 17, accentColor: "var(--o)" }}
            />
            <span className="small">Email me when someone wants my stuff</span>
          </label>

          {!user.is_verified_student && (
            <div style={{ marginTop: 14 }}>
              <Banner kind="soft">
                Verify your campus email to list, claim and redeem.
              </Banner>
              <Link to="/wallet" className="btn sm">Verify now</Link>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
