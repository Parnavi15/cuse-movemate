import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import Icon from "./Icon";

/**
 * Chat for one handoff, opened from the request card.
 *
 * Deliberately not a general inbox: the conversation exists because of a
 * specific item, so it's attached to that transaction and ends with it.
 */
export default function Chat({ txn, them, onRead }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const scroller = useRef(null);

  // onRead refreshes the parent list, which re-renders this component. Holding
  // it in a ref keeps it out of the dependency array, so polling doesn't
  // restart on every parent render.
  const onReadRef = useRef(onRead);
  const cleared = useRef(false);
  useEffect(() => {
    onReadRef.current = onRead;
  }, [onRead]);

  const load = useCallback(async () => {
    try {
      const rows = await api.messages(txn.id);
      setMessages(rows);
      // Reading marks the other side's messages read server-side. Tell the
      // parent once, so its unread badge clears without a refresh storm.
      if (!cleared.current) {
        cleared.current = true;
        onReadRef.current?.();
      }
    } catch (err) {
      setError(err.message);
    }
  }, [txn.id]);

  useEffect(() => {
    if (!open) return undefined;
    load();
    const timer = setInterval(load, 8000);
    return () => clearInterval(timer);
  }, [open, load]);

  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [messages]);

  const send = async () => {
    const body = draft.trim();
    if (!body) return;
    setSending(true);
    setError("");
    try {
      const message = await api.sendMessage(txn.id, body);
      setMessages((m) => [...m, message]);
      setDraft("");
      onReadRef.current?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  };

  const closed = ["rejected", "cancelled"].includes(txn.state);

  if (!open) {
    return (
      <button className="btn ghost sm" style={{ marginTop: 12 }} onClick={() => setOpen(true)}>
        <Icon name="chat" size={16} />
        {txn.message_count > 0
          ? `Chat with ${them.username} (${txn.message_count})`
          : `Message ${them.username}`}
        {txn.unread_messages > 0 && <span className="unread-dot">{txn.unread_messages}</span>}
      </button>
    );
  }

  return (
    <div className="chat">
      <div className="spread chat-head">
        <b>
          {them.avatar_emoji} {them.username}
          <span className="small muted" style={{ fontWeight: 400 }}> · {txn.listing.title}</span>
        </b>
        <button className="btn quiet sm" onClick={() => setOpen(false)}>Close</button>
      </div>

      <div className="chat-log" ref={scroller}>
        {messages.length === 0 ? (
          <p className="small muted center" style={{ padding: "18px 10px", margin: 0 }}>
            No messages yet. Agree a time and a spot — the handoff only counts once
            you both confirm in person.
          </p>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={`bubble-row ${m.mine ? "mine" : ""}`}>
              <div className="bubble">
                {m.body}
                <span className="stamp">
                  {new Date(m.created_at).toLocaleTimeString([], {
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            </div>
          ))
        )}
      </div>

      {error && <p className="small" style={{ color: "var(--danger)", margin: "8px 12px 0" }}>{error}</p>}

      {closed ? (
        <p className="small muted" style={{ padding: "10px 12px", margin: 0 }}>
          This conversation is closed.
        </p>
      ) : (
        <div className="chat-compose">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder={`Message ${them.username}…`}
            maxLength={1000}
            aria-label="Message"
          />
          <button className="btn sm" onClick={send} disabled={sending || !draft.trim()}>
            {sending ? "…" : "Send"}
          </button>
        </div>
      )}
    </div>
  );
}
