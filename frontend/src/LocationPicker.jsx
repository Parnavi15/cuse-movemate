import { useEffect, useRef, useState } from "react";
import { api } from "./api";

/**
 * Three ways to set a location, because students split on sharing GPS and
 * browsers deny the permission more often than you'd expect. All three end in
 * a coordinate pair, which is what the distance search actually runs on.
 */
export default function LocationPicker({ value, onChange, label = "Where do you live?" }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState("");
  const [problem, setProblem] = useState("");
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [manual, setManual] = useState(false);
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  const apply = (lat, lng, addressLabel) =>
    onChange({
      latitude: Number(lat),
      longitude: Number(lng),
      address_label: addressLabel || value.address_label || "Near campus",
    });

  const useGps = () => {
    setProblem("");
    if (!navigator.geolocation) {
      setProblem("This browser can't share location. Search for your street below.");
      return;
    }
    if (!window.isSecureContext && location.hostname !== "localhost") {
      setProblem("Location needs HTTPS. Search for your street below instead.");
      return;
    }
    setBusy(true);
    setStatus("Finding you…");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        try {
          const place = await api.geoReverse(latitude, longitude);
          apply(latitude, longitude, place.label);
          setStatus(`Set to ${place.label}`);
        } catch {
          apply(latitude, longitude, "");
          setStatus("Location saved, but the street name lookup failed.");
        } finally {
          setBusy(false);
        }
      },
      (err) => {
        setBusy(false);
        setStatus("");
        const reasons = {
          1: "You denied the location permission. Click the padlock in the address bar to allow it, or just search for your street below.",
          2: "Your device couldn't get a fix. Search for your street below.",
          3: "Location timed out. Search for your street below.",
        };
        setProblem(reasons[err.code] || "Couldn't get your location. Search below instead.");
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  };

  const onType = (text) => {
    setQuery(text);
    setStatus("");
    setProblem("");
    clearTimeout(timer.current);
    if (text.trim().length < 2) {
      setResults([]);
      setSearching(false);
      return;
    }
    // Debounced: geocoders rate-limit, and nobody needs a lookup per keystroke.
    setSearching(true);
    timer.current = setTimeout(async () => {
      try {
        const data = await api.geoSearch(text);
        setResults(data.results);
        if (data.results.length === 0) setProblem("No match. Try adding the city.");
      } catch {
        setResults([]);
        setProblem("Address lookup is unavailable. Enter coordinates manually below.");
      } finally {
        setSearching(false);
      }
    }, 450);
  };

  const pick = (r) => {
    apply(r.latitude, r.longitude, r.label);
    setQuery("");
    setResults([]);
    setStatus(`Set to ${r.label}`);
  };

  return (
    <div className="field">
      <label htmlFor="loc-search">{label}</label>

      <div className="card" style={{ padding: 14, boxShadow: "none" }}>
        <div className="spread" style={{ flexWrap: "wrap", gap: 10, marginBottom: 12 }}>
          <div>
            <b>📍 {value.address_label || "Not set"}</b>
            <div className="small muted">
              {Number(value.latitude).toFixed(4)}, {Number(value.longitude).toFixed(4)}
            </div>
          </div>
          <button type="button" className="btn ghost sm" onClick={useGps} disabled={busy}>
            {busy ? "Locating…" : "Use my current location"}
          </button>
        </div>

        <div style={{ position: "relative" }}>
          <input
            id="loc-search"
            type="text"
            value={query}
            onChange={(e) => onType(e.target.value)}
            placeholder="Search — South Campus, Euclid Ave, Ernie Davis…"
            autoComplete="off"
          />
          {results.length > 0 && (
            <div
              className="card"
              style={{ position: "absolute", top: "100%", left: 0, right: 0, zIndex: 30, marginTop: 4 }}
            >
              {results.map((r, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => pick(r)}
                  style={{
                    display: "block", width: "100%", textAlign: "left", background: "none",
                    border: 0, borderBottom: i < results.length - 1 ? "1px solid var(--line)" : "none",
                    padding: "10px 13px", cursor: "pointer", font: "inherit", color: "var(--ink)",
                  }}
                >
                  <b>
                    {r.label}
                    {r.campus && <span className="tag free" style={{ marginLeft: 7, fontSize: 11 }}>campus</span>}
                  </b>
                  <div className="small muted" style={{ lineHeight: 1.3 }}>{r.address}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="field" style={{ marginTop: 12, marginBottom: 0 }}>
          <label htmlFor="loc-name" className="small">What should this be called?</label>
          <input
            id="loc-name"
            type="text"
            value={value.address_label || ""}
            onChange={(e) => onChange({ ...value, address_label: e.target.value })}
            placeholder="Comstock Ave"
          />
        </div>

        {searching && (
          <p className="small muted" style={{ margin: "8px 0 0" }}>Searching…</p>
        )}
        {status && !searching && (
          <p className="small" style={{ color: "var(--moss)", margin: "10px 0 0" }}>{status}</p>
        )}
        {problem && <p className="small" style={{ color: "var(--danger)", margin: "10px 0 0" }}>{problem}</p>}

        <button
          type="button"
          className="btn quiet sm"
          style={{ marginTop: 10 }}
          onClick={() => setManual(!manual)}
        >
          {manual ? "Hide coordinates" : "Enter coordinates manually"}
        </button>

        {manual && (
          <div className="field-row" style={{ marginTop: 10 }}>
            <div>
              <label className="small" htmlFor="lat">Latitude</label>
              <input id="lat" type="number" step="0.0001" value={value.latitude}
                onChange={(e) => onChange({ ...value, latitude: Number(e.target.value) })} />
            </div>
            <div>
              <label className="small" htmlFor="lng">Longitude</label>
              <input id="lng" type="number" step="0.0001" value={value.longitude}
                onChange={(e) => onChange({ ...value, longitude: Number(e.target.value) })} />
            </div>
          </div>
        )}

        <p className="small muted" style={{ margin: "10px 0 0" }}>
          Other students only ever see the name and how far away you are, never an exact address.
        </p>
      </div>
    </div>
  );
}
