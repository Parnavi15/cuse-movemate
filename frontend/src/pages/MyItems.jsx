import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Empty, Spinner } from "../components";

export default function MyItems() {
  const [items, setItems] = useState(null);

  const load = () => api.myListings().then(setItems).catch(() => setItems([]));
  useEffect(() => { load(); }, []);

  const remove = async (item) => {
    if (!confirm(`Remove "${item.title}"?`)) return;
    await api.deleteListing(item.id);
    load();
  };

  if (!items) return <Spinner />;

  return (
    <>
      <div className="spread mb">
        <h1>My items</h1>
        <Link to="/new" className="btn">List an item</Link>
      </div>

      {items.length === 0 ? (
        <Empty icon="📦" title="Nothing listed yet">
          List three move-out items in one go and you pick up a 10-point bonus.
        </Empty>
      ) : (
        <div className="card">
          {items.map((item, i) => (
            <div key={item.id} className="spread pad"
              style={{ borderBottom: i < items.length - 1 ? "1px solid var(--line)" : "none", flexWrap: "wrap" }}>
              <div>
                <Link to={`/listing/${item.id}`}><b>{item.title}</b></Link>
                <div className="small muted">
                  {item.price_display} · {item.category.name} · {item.views} views
                  {item.open_requests > 0 && (
                    <span className="tag" style={{ marginLeft: 8 }}>
                      {item.open_requests} request{item.open_requests === 1 ? "" : "s"}
                    </span>
                  )}
                  {!item.is_point_eligible && (
                    <span className="tag grey" style={{ marginLeft: 8 }}>not point-eligible</span>
                  )}
                </div>
              </div>
              <div className="row">
                <span className={`tag state-${item.status === "active" ? "accepted" : "completed"}`}>
                  {item.status}
                </span>
                <Link to={`/edit/${item.id}`} className="btn ghost sm">Edit</Link>
                <button className="btn danger sm" onClick={() => remove(item)}>Remove</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
