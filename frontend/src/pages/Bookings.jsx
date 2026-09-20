import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, money } from "../api";
import Chat from "../Chat";
import PickupTime from "../PickupTime";
import { Banner, Empty, Spinner, StateTag, Stars } from "../components";
import { useAuth } from "../store";

export default function Bookings() {
  const { refresh } = useAuth();
  const [tab, setTab] = useState("owner");
  const [rows, setRows] = useState(null);
  const [flash, setFlash] = useState(null);
  const [error, setError] = useState("");

  // Blanking rows on every refresh would unmount open chat panels mid-typing,
  // so only the first load of a tab shows the spinner.
  const load = useCallback(async () => {
    try {
      setRows(await api.transactions({ role: tab }));
    } catch (err) {
      setError(err.message);
      setRows([]);
    }
  }, [tab]);

  useEffect(() => {
    setRows(null);
    load();
  }, [tab, load]);

  const act = async (fn, successMessage) => {
    setError("");
    try {
      const result = await fn();
      if (successMessage) setFlash(successMessage);
      if (result?.state === "completed") {
        setFlash(
          result.blocked_reason
            ? `Handoff confirmed. No points this time — ${result.blocked_reason}`
            : "Handoff confirmed. Points are pending for 24 hours, then they post to your wallet."
        );
      }
      await refresh();
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <>
      <h1>Requests</h1>
      <p className="muted">
        Points are created by one thing only: both students confirming the handoff.
      </p>

      <div className="tabs mt">
        <button className={tab === "owner" ? "on" : ""} onClick={() => setTab("owner")}>
          People want my stuff
        </button>
        <button className={tab === "claimant" ? "on" : ""} onClick={() => setTab("claimant")}>
          Stuff I asked for
        </button>
      </div>

      {flash && <Banner kind="good">{flash}</Banner>}
      {error && <Banner kind="bad">{error}</Banner>}

      {!rows ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <Empty icon="🤝" title="Nothing here yet">
          {tab === "owner"
            ? "When someone claims one of your listings, it lands here for you to accept or decline."
            : "Claim something from Browse and it'll show up here."}
        </Empty>
      ) : (
        rows.map((txn) => (
          <TransactionRow key={txn.id} txn={txn} act={act} reload={load} />
        ))
      )}
    </>
  );
}

const STAGES = ["Requested", "Accepted", "Handed off", "Reviewed"];

function stageIndex(txn) {
  if (["rejected", "cancelled", "disputed"].includes(txn.state)) return -1;
  return { requested: 0, accepted: 1, completed: 2, reviewed: 3 }[txn.state] ?? 0;
}

/**
 * The single most useful thing a marketplace can tell you is what to do next.
 * Two people are coordinating a real-world meetup through an app neither has
 * used before, so spell it out per role and per state.
 */
function nextStep(txn, them) {
  const owner = txn.my_role === "owner";
  switch (txn.state) {
    case "requested":
      return owner
        ? {
            title: "Decide on this request",
            body: `${them.username} wants it. Accepting declines anyone else waiting, so check their rating first.`,
          }
        : {
            title: `Waiting on ${them.username}`,
            body: "You'll get a notification the moment they accept or decline. Nothing to do yet.",
          };
    case "accepted":
      if (txn.i_confirmed && !txn.they_confirmed) {
        return {
          title: `Waiting on ${them.username} to confirm`,
          body: "Points are released when you've both tapped confirm. Nudge them in the chat if it's been a while.",
        };
      }
      if (txn.they_confirmed) {
        return {
          title: "Your tap completes this",
          body: `${them.username} already confirmed. Once the item has actually changed hands, tap Confirm handoff.`,
        };
      }
      if (txn.pickup_at && txn.pickup_agreed) {
        return {
          title: "Meet up, then both confirm",
          body: `Pickup is set. Once the item has actually changed hands, both of you tap Confirm handoff${
            !owner && txn.amount_due_cents > 0 ? `, and bring ${money(txn.amount_due_cents)} in cash` : ""
          }.`,
        };
      }
      if (txn.pickup_at) {
        return {
          title: txn.pickup_proposed_by_me ? "Waiting on a reply" : "Agree a time",
          body: txn.pickup_proposed_by_me
            ? `${them.username} hasn't confirmed your suggested time yet.`
            : `${them.username} suggested a time. Agree to it or suggest another.`,
        };
      }
      return {
        title: "Agree a time and meet up",
        body: owner
          ? `Message ${them.username} to set a spot and a time. Once you've handed it over, both of you tap Confirm handoff.`
          : `Message ${them.username} to set a spot and a time${
              txn.amount_due_cents > 0 ? `, and bring ${money(txn.amount_due_cents)} in cash` : ""
            }. Once you have it, both of you tap Confirm handoff.`,
      };
    case "completed":
      return txn.i_reviewed
        ? {
            title: "Done — points are pending",
            body: "They post to your wallet 24 hours after the handoff. Report a problem before then if something was wrong.",
          }
        : {
            title: "Leave a review",
            body: `Worth 5 points, and it's what makes ${them.username} trustworthy to the next student.`,
          };
    case "reviewed":
      return {
        title: "All done",
        body: "Points post 24 hours after the handoff. Check your wallet to see the impact.",
      };
    case "rejected":
      return owner
        ? { title: "Declined", body: "The listing is back up for anyone else who wants it." }
        : { title: "Not this time", body: "Try the smart match — students list new things every day." };
    case "cancelled":
      return { title: "Cancelled", body: "The listing is active again." };
    case "disputed":
      return { title: "Reported", body: "Points for this handoff were reversed." };
    default:
      return null;
  }
}

function StageBar({ txn }) {
  const at = stageIndex(txn);
  if (at < 0) return null;
  return (
    <div className="stages">
      {STAGES.map((label, i) => (
        <div key={label} className={`stage ${i < at ? "done" : ""} ${i === at ? "now" : ""}`}>
          <span className="dot">{i < at ? "✓" : i + 1}</span>
          <span className="lbl">{label}</span>
        </div>
      ))}
    </div>
  );
}

function TransactionRow({ txn, act, reload }) {
  const isOwner = txn.my_role === "owner";
  const them = isOwner ? txn.claimant : txn.owner;

  return (
    <div className="card pad mb">
      <div className="spread" style={{ flexWrap: "wrap", alignItems: "flex-start" }}>
        <div>
          <Link to={`/listing/${txn.listing.id}`}>
            <b style={{ fontSize: 17 }}>{txn.listing.title}</b>
          </Link>
          <div className="small muted">
            {isOwner ? "Requested by" : "Listed by"} {them.avatar_emoji} {them.username}
            {them.is_verified_student && <span className="tag free" style={{ marginLeft: 6 }}>🎓</span>}
            {them.rating_count > 0 && ` · ${them.rating_avg}★ (${them.rating_count})`}
          </div>
          <div className="small muted">
            {txn.listing.price_display}
            {txn.credit_applied_cents > 0 &&
              ` · ${money(txn.credit_applied_cents)} credit applied · ${money(txn.amount_due_cents)} due`}
          </div>
        </div>
        <StateTag state={txn.state} />
      </div>

      <StageBar txn={txn} />

      {(() => {
        const step = nextStep(txn, isOwner ? txn.claimant : txn.owner);
        if (!step) return null;
        return (
          <div className="nextstep">
            <b>Next: {step.title}</b>
            <span>{step.body}</span>
          </div>
        );
      })()}

      {txn.message && (
        <p className="mt" style={{ background: "var(--bg)", padding: "10px 13px", borderRadius: 10, marginBottom: 0 }}>
          “{txn.message}”
        </p>
      )}
      {txn.pickup_note && txn.state === "accepted" && (
        <p className="small muted mt" style={{ marginBottom: 0 }}>📍 Pickup note: {txn.pickup_note}</p>
      )}

      {txn.state === "requested" && isOwner && <AcceptReject txn={txn} act={act} />}

      {txn.state === "requested" && !isOwner && (
        <div className="row mt">
          <span className="muted small" style={{ marginRight: "auto" }}>
            Waiting on {them.username} to accept.
          </span>
          <button className="btn quiet sm" onClick={() => act(() => api.cancel(txn.id), "Request withdrawn.")}>
            Withdraw
          </button>
        </div>
      )}

      {txn.state === "accepted" && <ConfirmPanel txn={txn} act={act} them={them} />}

      {(txn.state === "completed" || txn.state === "reviewed") && (
        <ReviewPanel txn={txn} act={act} them={them} />
      )}

      <PickupTime txn={txn} them={them} onChange={reload} />

      <Chat txn={txn} them={them} onRead={reload} />
    </div>
  );
}

function AcceptReject({ txn, act }) {
  const [note, setNote] = useState("");
  return (
    <div className="mt">
      <div className="field">
        <label htmlFor={`note-${txn.id}`}>Where and when should they pick it up?</label>
        <input
          id={`note-${txn.id}`}
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Front porch on Comstock, Thursday after 5pm"
        />
      </div>
      <div className="row">
        <button className="btn" onClick={() => act(() => api.accept(txn.id, { pickup_note: note }), "Accepted. Other requests for this item were declined.")}>
          Accept request
        </button>
        <button className="btn danger" onClick={() => act(() => api.reject(txn.id), "Request declined.")}>
          Decline
        </button>
      </div>
    </div>
  );
}

function ConfirmPanel({ txn, act, them }) {
  return (
    <div className="mt">
      <div className={`banner ${txn.i_confirmed ? "good" : "soft"}`}>
        {txn.i_confirmed && txn.they_confirmed
          ? "Both confirmed."
          : txn.i_confirmed
          ? `You confirmed. Waiting on ${them.username}.`
          : txn.they_confirmed
          ? `${them.username} confirmed. Your tap completes it.`
          : "Tap to confirm once the item has actually changed hands."}
      </div>
      <div className="row">
        <button className="btn" disabled={txn.i_confirmed} onClick={() => act(() => api.confirm(txn.id))}>
          {txn.i_confirmed ? "You confirmed ✓" : "Confirm handoff"}
        </button>
        <button className="btn quiet sm" onClick={() => act(() => api.cancel(txn.id), "Cancelled.")}>
          Cancel
        </button>
      </div>
      {txn.amount_due_cents > 0 && (
        <p className="small muted mt" style={{ marginBottom: 0 }}>
          {money(txn.amount_due_cents)} is settled in person. MoveMate doesn't handle cash.
        </p>
      )}
    </div>
  );
}

function ReviewPanel({ txn, act, them }) {
  const [stars, setStars] = useState(0);
  const [answers, setAnswers] = useState({});
  const [body, setBody] = useState("");

  const ready = stars > 0 && Object.keys(answers).length === 3;

  if (txn.i_reviewed) {
    return (
      <div className="mt">
        <Banner kind="good">Reviewed. Thanks — that's what makes the next handoff trustworthy.</Banner>
        <button className="btn quiet sm" onClick={() => act(() => api.dispute(txn.id), "Reported. Points for this handoff were reversed.")}>
          Report a problem
        </button>
      </div>
    );
  }

  const toggle = (key, value) => setAnswers((a) => ({ ...a, [key]: value }));

  const Q = ({ label, name }) => (
    <div style={{ marginBottom: 12 }}>
      <div className="small" style={{ marginBottom: 6 }}>{label}</div>
      <div className="chips">
        {[["yes", true], ["no", false]].map(([lbl, val]) => (
          <button
            key={lbl}
            className={`chip ${answers[name] === val ? "on" : ""}`}
            onClick={() => toggle(name, val)}
          >
            {lbl === "yes" ? "Yes" : "No"}
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="mt" style={{ borderTop: "1px solid var(--line)", paddingTop: 16 }}>
      <h3>How was the pickup?</h3>
      <p className="small muted">Your review is worth 5 points and builds {them.username}'s rating.</p>
      <Stars value={stars} onChange={setStars} />
      <div className="mt">
        <Q label="Was the pickup on time?" name="on_time" />
        <Q label="Easy to communicate with?" name="easy_to_reach" />
        <Q label="Would you pass something on to them again?" name="would_repeat" />
      </div>
      <div className="field">
        <input
          type="text"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Anything the next student should know (optional)"
          aria-label="Review comment"
        />
      </div>
      <button
        className="btn"
        disabled={!ready}
        onClick={() =>
          act(
            () => api.review({ transaction: txn.id, stars, body, ...answers }),
            "Review posted. +5 points pending."
          )
        }
      >
        Post review · +5 pts
      </button>
    </div>
  );
}
