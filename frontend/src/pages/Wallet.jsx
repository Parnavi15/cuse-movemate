import { useEffect, useState } from "react";
import { api, money } from "../api";
import { Banner, Spinner } from "../components";
import { useAuth } from "../store";

export default function Wallet() {
  const { user, refresh } = useAuth();
  const [wallet, setWallet] = useState(null);
  const [impact, setImpact] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");
  const [redeemPoints, setRedeemPoints] = useState(100);

  const load = async () => {
    try {
      const [w, i, l] = await Promise.all([api.wallet(), api.impact(), api.ledger()]);
      setWallet(w);
      setImpact(i);
      setLedger(l);
      setRedeemPoints(Math.max(100, Math.floor(w.points_posted / 100) * 100));
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const redeem = async () => {
    setError("");
    setFlash("");
    try {
      await api.redeem(redeemPoints);
      setFlash(`Redeemed ${redeemPoints} points for ${money((redeemPoints / 20) * 100)} of credit.`);
      await refresh();
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const settle = async () => {
    await api.settle();
    setFlash("Pending points posted. (Demo shortcut — normally this takes 24 hours.)");
    await refresh();
    await load();
  };

  if (!wallet || !impact) return <Spinner />;

  const canRedeem = wallet.can_redeem && wallet.points_posted >= wallet.redeem_block;

  return (
    <>
      <h1>Your Impact Wallet</h1>
      <p className="muted">
        A balance on its own is a score. Next to what it kept out of a dumpster, it's the point.
      </p>

      {flash && <Banner kind="good">{flash}</Banner>}
      {error && <Banner kind="bad">{error}</Banner>}

      <div className="impact mt">
        <div className="bal">
          ♻️ {wallet.points_posted}
          <small>
            MovePoints · {money(wallet.credit_cents)} credit available
            {wallet.points_pending > 0 && ` · ${wallet.points_pending} pending`}
          </small>
        </div>
        <div className="impact-stats">
          <div><b>{impact.items_circulated}</b><span>items kept in circulation</span></div>
          <div><b>{money(impact.savings_cents)}</b><span>estimated savings</span></div>
          <div><b>{impact.weight_kg} kg</b><span>kept out of the waste stream</span></div>
          <div><b>{impact.co2e_kg} kg</b><span>CO₂e avoided</span></div>
        </div>
      </div>
      <p className="small muted mt">{impact.note}</p>

      {!user.is_verified_student && <VerifyCard onDone={load} />}

      <div className="grid2 mt2" style={{ gridTemplateColumns: "minmax(0,1.25fr) minmax(0,1fr)" }}>
        <div>
          <div className="card pad">
            <div className="spread mb">
              <h3>Recent activity</h3>
              {wallet.points_pending > 0 && (
                <button className="btn quiet sm" onClick={settle}>Fast-forward 24h</button>
              )}
            </div>
            {ledger.length === 0 ? (
              <p className="muted">
                Nothing yet. Hand off your first item and 75 points land here.
              </p>
            ) : (
              <div className="ledger">
                {ledger.map((e) => (
                  <div key={e.id} className="lrow">
                    <div>
                      <b>{e.note || e.rule_label}</b>
                      <div className="small muted">
                        {e.status === "pending"
                          ? `Pending until ${new Date(e.posts_at).toLocaleString()}`
                          : e.status === "reversed"
                          ? "Reversed"
                          : `Posted ${new Date(e.created_at).toLocaleDateString()}`}
                      </div>
                    </div>
                    <div className={`amt ${e.points < 0 ? "neg" : ""} ${e.status === "pending" ? "pending" : ""}`}>
                      {e.points > 0 ? "+" : ""}{e.points}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card pad mt">
            <h3>Badges</h3>
            <div className="grid2 mt" style={{ gap: 10 }}>
              {wallet.badges.map((b) => (
                <div key={b.slug} className={`badge-pill ${b.earned ? "earned" : ""}`}>
                  <span className="ic">{b.icon}</span>
                  <div style={{ flex: 1 }}>
                    <b>{b.name}</b>
                    <div className="small muted">
                      {b.earned ? `Earned · +${b.bonus_points} pts` : `${b.progress}/${b.threshold} — ${b.description}`}
                    </div>
                    {!b.earned && (
                      <div className="bar">
                        <i style={{ width: `${(b.progress / b.threshold) * 100}%` }} />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div>
          <div className="card pad">
            <h3>Turn points into credit</h3>
            <p className="small muted">
              {wallet.points_per_dollar} points = $1.00. Redeem in blocks of {wallet.redeem_block}.
              Credit covers at most {Math.round(wallet.max_credit_share * 100)}% of an item's price,
              so the student selling still gets paid.
            </p>

            {!wallet.can_redeem ? (
              <Banner kind="soft">Verify your .edu email to redeem points.</Banner>
            ) : wallet.points_posted < wallet.redeem_block ? (
              <Banner kind="soft">
                {wallet.redeem_block - wallet.points_posted} more points until your first redemption.
              </Banner>
            ) : (
              <>
                <div className="field mt">
                  <label htmlFor="redeem">
                    Redeem {redeemPoints} points → {money((redeemPoints / wallet.points_per_dollar) * 100)}
                  </label>
                  <input
                    id="redeem"
                    className="slider"
                    type="range"
                    min={wallet.redeem_block}
                    max={Math.floor(wallet.points_posted / wallet.redeem_block) * wallet.redeem_block}
                    step={wallet.redeem_block}
                    value={redeemPoints}
                    onChange={(e) => setRedeemPoints(Number(e.target.value))}
                  />
                </div>
                <button className="btn full" onClick={redeem} disabled={!canRedeem}>
                  Redeem for credit
                </button>
              </>
            )}
          </div>

          <div className="card pad mt">
            <h3>How points are earned</h3>
            <div className="mt">
              {wallet.reward_table.map((r) => (
                <div key={r.rule} className="reward-row">
                  <span>{r.icon} {r.label}</span>
                  <b>+{r.points}</b>
                </div>
              ))}
            </div>
            <p className="small muted mt" style={{ marginBottom: 0 }}>
              Earned {wallet.weekly_earned} of {wallet.weekly_ceiling} points this week.
              Points post 24 hours after both students confirm.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

function VerifyCard({ onDone }) {
  const { refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [demoCode, setDemoCode] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const send = async () => {
    setError("");
    try {
      const res = await api.verifyRequest({ campus_email: email });
      setSent(true);
      setMsg(res.detail);
      if (res.demo_code) setDemoCode(res.demo_code);
    } catch (err) {
      setError(err.message);
    }
  };

  const confirm = async () => {
    setError("");
    try {
      await api.verifyConfirm({ code });
      await refresh();
      onDone();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="card pad mt">
      <h3>🎓 Verify you're a student</h3>
      <p className="small muted">
        Anyone can browse and earn. Only a verified student can turn points into credit.
        Verifying is worth 25 points on its own.
      </p>
      {error && <Banner kind="bad">{error}</Banner>}
      {!sent ? (
        <div className="row wrap-row">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@syr.edu"
            aria-label="Campus email"
            style={{ maxWidth: 280 }}
          />
          <button className="btn" onClick={send} disabled={!email.endsWith(".edu")}>
            Send code
          </button>
        </div>
      ) : (
        <>
          <Banner kind="soft">
            {msg}
            {demoCode
              ? ` No mail server configured — your code is ${demoCode}.`
              : " Check Junk or Other if it doesn't arrive in a minute."}
          </Banner>
          <div className="row wrap-row">
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="6-digit code"
              aria-label="Verification code"
              style={{ maxWidth: 180 }}
            />
            <button className="btn" onClick={confirm} disabled={code.length !== 6}>
              Verify
            </button>
          </div>
        </>
      )}
    </div>
  );
}
