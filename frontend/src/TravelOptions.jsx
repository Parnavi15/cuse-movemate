import { useEffect, useState } from "react";
import { api } from "./api";
import Icon from "./Icon";

/**
 * How long it takes to actually go and get the item.
 *
 * "1.4 km" tells a student nothing useful. "17 min walk, 6 min drive" is what
 * decides whether they claim the desk, so that's what we show — with a link
 * that opens real turn-by-turn directions.
 */
export default function TravelOptions({ listingId }) {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api.travel(listingId).then(setData).catch(() => setFailed(true));
  }, [listingId]);

  if (failed || !data) return null;

  return (
    <div className="card pad mt">
      <div className="spread mb">
        <h3>Getting there</h3>
        <span className="small muted">
          <Icon name="pin" size={14} style={{ display: "inline-block", verticalAlign: "-2px" }} />{" "}
          {data.destination}
        </span>
      </div>

      <div className="travel-grid">
        {data.modes.map((m) => (
          <a
            key={m.key}
            href={m.url}
            target="_blank"
            rel="noreferrer"
            className="travel"
          >
            <Icon name={m.icon} size={24} />
            <b>{m.duration_text}</b>
            <span className="small muted">{m.label}</span>
            {m.distance_km != null && (
              <span className="small muted">{m.distance_km} km</span>
            )}
          </a>
        ))}
      </div>

      <p className="small muted" style={{ margin: "12px 0 0" }}>
        {data.source === "google"
          ? "Live times from Google Maps. Tap any option for directions."
          : "Estimated from distance. Tap any option for real directions in Google Maps."}
      </p>
    </div>
  );
}
