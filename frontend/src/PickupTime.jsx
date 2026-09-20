import { useState } from "react";
import { api } from "./api";
import Icon from "./Icon";

/**
 * Agreeing when to meet, as a two-tap handshake rather than a chat thread.
 *
 * "Message them to agree a time" is a weak instruction when the app already
 * knows both people, the item and the pickup deadline. One side proposes, the
 * other agrees, and then it lands in a real calendar.
 */

function atHour(daysAhead, hour) {
  const d = new Date();
  d.setDate(d.getDate() + daysAhead);
  d.setHours(hour, 0, 0, 0);
  return d;
}

// Value for <input type="datetime-local">, which wants local time, no zone.
function toInput(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

function pretty(iso) {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

const QUICK = [
  { label: "Today 5pm", date: () => atHour(0, 17) },
  { label: "Tomorrow noon", date: () => atHour(1, 12) },
  { label: "Tomorrow 6pm", date: () => atHour(1, 18) },
  { label: "Saturday noon", date: () => {
      const d = new Date();
      d.setDate(d.getDate() + ((6 - d.getDay() + 7) % 7 || 7));
      d.setHours(12, 0, 0, 0);
      return d;
    } },
];

// Google Calendar wants UTC basic format: 20260920T170000Z
function gcalStamp(date) {
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

function googleUrl(txn) {
  const start = new Date(txn.pickup_at);
  const end = new Date(start.getTime() + 30 * 60000);
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: `Cuse-MoveMate pickup: ${txn.listing.title}`,
    dates: `${gcalStamp(start)}/${gcalStamp(end)}`,
    details: `Picking up "${txn.listing.title}" with ${
      txn.my_role === "owner" ? txn.claimant.username : txn.owner.username
    }. Both of you confirm the handoff in the app afterwards.`,
    location: txn.listing.address_label,
  });
  return `https://calendar.google.com/calendar/render?${params}`;
}

function downloadIcs(txn) {
  const start = new Date(txn.pickup_at);
  const end = new Date(start.getTime() + 30 * 60000);
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Cuse-MoveMate//EN",
    "BEGIN:VEVENT",
    `UID:movemate-${txn.id}@cuse-movemate`,
    `DTSTAMP:${gcalStamp(new Date())}`,
    `DTSTART:${gcalStamp(start)}`,
    `DTEND:${gcalStamp(end)}`,
    `SUMMARY:Cuse-MoveMate pickup: ${txn.listing.title}`,
    `LOCATION:${txn.listing.address_label}`,
    "DESCRIPTION:Confirm the handoff in the app once the item changes hands.",
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  const blob = new Blob([lines.join("\r\n")], { type: "text/calendar" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `movemate-pickup-${txn.id}.ics`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function PickupTime({ txn, them, onChange }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(
    txn.pickup_at ? toInput(new Date(txn.pickup_at)) : toInput(atHour(1, 12))
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!["requested", "accepted"].includes(txn.state) && !txn.pickup_at) return null;

  const propose = async (date) => {
    setBusy(true);
    setError("");
    try {
      // Send local wall-clock time; the server attaches the campus timezone.
      await api.proposeTime(txn.id, date ? toInput(date) : value);
      setEditing(false);
      onChange?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const agree = async () => {
    setBusy(true);
    setError("");
    try {
      await api.agreeTime(txn.id);
      onChange?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  // ---- agreed ----
  if (txn.pickup_at && txn.pickup_agreed) {
    return (
      <div className="pickup agreed">
        <div className="pickup-head">
          <Icon name="bus" size={18} />
          <div>
            <b>Pickup {pretty(txn.pickup_at)}</b>
            <span className="small muted"> · {txn.listing.address_label}</span>
          </div>
        </div>
        <div className="row wrap-row" style={{ marginTop: 10 }}>
          <a className="btn ghost sm" href={googleUrl(txn)} target="_blank" rel="noreferrer">
            Add to Google Calendar
          </a>
          <button className="btn quiet sm" onClick={() => downloadIcs(txn)}>
            Apple / Outlook (.ics)
          </button>
          <button className="btn quiet sm" onClick={() => setEditing(true)}>
            Change
          </button>
        </div>
        {editing && (
          <Editor {...{ value, setValue, propose, busy, setEditing, error }} />
        )}
      </div>
    );
  }

  // ---- proposed, waiting on someone ----
  if (txn.pickup_at && !editing) {
    return (
      <div className="pickup">
        <div className="pickup-head">
          <Icon name="bus" size={18} />
          <div>
            <b>{pretty(txn.pickup_at)}</b>
            <span className="small muted">
              {txn.pickup_proposed_by_me
                ? ` · you suggested this, waiting on ${them.username}`
                : ` · ${them.username} suggested this`}
            </span>
          </div>
        </div>
        {error && <p className="small" style={{ color: "var(--danger)", margin: "8px 0 0" }}>{error}</p>}
        <div className="row wrap-row" style={{ marginTop: 10 }}>
          {!txn.pickup_proposed_by_me && (
            <button className="btn sm" onClick={agree} disabled={busy}>
              That works
            </button>
          )}
          <button className="btn quiet sm" onClick={() => setEditing(true)}>
            {txn.pickup_proposed_by_me ? "Change time" : "Suggest another"}
          </button>
        </div>
      </div>
    );
  }

  // ---- nothing proposed yet ----
  return (
    <div className="pickup">
      {!editing ? (
        <>
          <div className="pickup-head">
            <Icon name="bus" size={18} />
            <b>When are you meeting?</b>
          </div>
          <div className="chips" style={{ marginTop: 10 }}>
            {QUICK.map((q) => (
              <button key={q.label} className="chip" disabled={busy}
                      onClick={() => propose(q.date())}>
                {q.label}
              </button>
            ))}
            <button className="chip" onClick={() => setEditing(true)}>Pick a time…</button>
          </div>
          {error && <p className="small" style={{ color: "var(--danger)", margin: "8px 0 0" }}>{error}</p>}
        </>
      ) : (
        <Editor {...{ value, setValue, propose, busy, setEditing, error }} />
      )}
    </div>
  );
}

function Editor({ value, setValue, propose, busy, setEditing, error }) {
  return (
    <div style={{ marginTop: 10 }}>
      <label className="small" htmlFor="when">Date and time</label>
      <input
        id="when"
        type="datetime-local"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      {error && <p className="small" style={{ color: "var(--danger)", margin: "8px 0 0" }}>{error}</p>}
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn sm" onClick={() => propose()} disabled={busy}>
          {busy ? "Saving…" : "Suggest this time"}
        </button>
        <button className="btn quiet sm" onClick={() => setEditing(false)}>Cancel</button>
      </div>
    </div>
  );
}
