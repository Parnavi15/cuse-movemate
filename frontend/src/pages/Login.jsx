import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Banner } from "../components";
import { useAuth } from "../store";

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await signIn(form);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const demo = async () => {
    setBusy(true);
    setError("");
    try {
      await signIn({ username: "demo", password: "movemate" });
      navigate("/wallet");
    } catch (err) {
      setError("Run `python manage.py seed --reset` to create the demo account.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <h1 className="center">Welcome back</h1>
      <p className="center muted">Students only — sign in with your campus account.</p>

      <form className="card pad mt" onSubmit={submit}>
        {error && <Banner kind="bad">{error}</Banner>}
        <div className="field">
          <label htmlFor="u">Campus email or username</label>
          <input id="u" type="text" required value={form.username}
            placeholder="you@syr.edu"
            autoComplete="username"
            onChange={(e) => setForm({ ...form, username: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="p">Password</label>
          <input id="p" type="password" required value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </div>
        <button className="btn full" type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <button className="btn ghost full mt" type="button" onClick={demo} disabled={busy}>
          Use the demo account
        </button>
        <p className="center small muted mt" style={{ marginBottom: 0 }}>
          New here? <Link to="/register">Create an account</Link>
        </p>
      </form>
    </div>
  );
}
