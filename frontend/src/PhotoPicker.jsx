import { useRef, useState } from "react";
import { getToken } from "./api";

/**
 * Take a photo or pick one from the camera roll. Uploads immediately so the
 * student sees the picture before they finish the rest of the form — a listing
 * with no photo isn't point-eligible, so it's worth making obvious and easy.
 */
export default function PhotoPicker({ value, onChange }) {
  const input = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("photo", file);
      const res = await fetch("/api/uploads/photo/", {
        method: "POST",
        headers: { Authorization: `Token ${getToken()}` },
        body, // no Content-Type: the browser sets the multipart boundary
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "Upload failed.");
      onChange(data.url);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="field">
      <label>Photo</label>

      {value ? (
        <div className="card" style={{ overflow: "hidden", boxShadow: "none" }}>
          <img
            src={value}
            alt="Your listing"
            style={{ width: "100%", height: 200, objectFit: "contain", display: "block", background: "#fff" }}
          />
          <div className="spread pad" style={{ padding: 12 }}>
            <span className="small muted">Looks good?</span>
            <div className="row">
              <button type="button" className="btn ghost sm" onClick={() => input.current?.click()}>
                Replace
              </button>
              <button type="button" className="btn danger sm" onClick={() => onChange("")}>
                Remove
              </button>
            </div>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => input.current?.click()}
          disabled={busy}
          style={{
            width: "100%", padding: "28px 16px", borderRadius: 12,
            border: "2px dashed var(--o-line)", background: "var(--o-tint)",
            cursor: "pointer", font: "inherit", color: "var(--o-deep)", fontWeight: 700,
          }}
        >
          {busy ? "Uploading…" : "📷  Take a photo or choose one"}
          <div className="small muted" style={{ fontWeight: 400, marginTop: 4 }}>
            JPG, PNG, WebP or GIF · up to 5 MB
          </div>
        </button>
      )}

      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        style={{ display: "none" }}
        onChange={(e) => {
          upload(e.target.files?.[0]);
          e.target.value = "";
        }}
      />

      {error && <p className="small" style={{ color: "var(--danger)", margin: "8px 0 0" }}>{error}</p>}

      <details style={{ marginTop: 10 }}>
        <summary className="small muted" style={{ cursor: "pointer" }}>
          Or paste a photo URL
        </summary>
        <input
          type="text"
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder="https://…"
          style={{ marginTop: 8 }}
        />
      </details>
    </div>
  );
}
