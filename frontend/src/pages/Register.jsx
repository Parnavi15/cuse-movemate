import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { Banner } from "../components";
import LocationPicker from "../LocationPicker";
import { useAuth } from "../store";

const EMOJI = ["🧑‍🎓", "🎨", "🎧", "📗", "🛠️", "⚽", "🌱", "🍜"];

export default function Register() {
  const { signUp, refresh } = useAuth();
  const navigate = useNavigate();

  const [config, setConfig] = useState(null);
  const [step, setStep] = useState("details");
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    address_label: "Near campus",
    latitude: 43.0392,
    longitude: -76.1351,
    avatar_emoji: "🧑‍🎓",
  });
  const [code, setCode] = useState("");
  const [demoCode, setDemoCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.config().then(setConfig).catch(() => {});
  }, []);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const domains = config?.student_domains || ["syr.edu"];
  const domainText = config?.student_domains_display || "@syr.edu";
  const emailOk = domains.some((d) => {
    const at = form.email.toLowerCase().split("@")[1];
    return at && (at === d || at.endsWith("." + d));
  });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await signUp(form);
      if (result.demo_code) setDemoCode(result.demo_code);
      if (result.mail_error) setError("Couldn't send the email: " + result.mail_error);
      setStep("verify");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setBusy(true);
    setError("");
    try {
      await api.verifyConfirm({ code });
      await refresh();
      navigate("/wallet");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    setError("");
    try {
      const res = await api.verifyRequest({ campus_email: form.email });
      if (res.demo_code) setDemoCode(res.demo_code);
    } catch (err) {
      setError(err.message);
    }
  };

  if (step === "verify") {
    return (
      <div className="auth">
        <h1 className="center">Check your campus inbox</h1>
        <p className="center muted">
          We sent a 6-digit code to <b>{form.email}</b>. Confirming it proves you hold that
          mailbox, which is what makes every listing here a real student.
        </p>

        <div className="card pad mt">
          {error && <Banner kind="bad">{error}</Banner>}
          {demoCode ? (
            <Banner kind="soft">
              No mail server is configured, so the code is shown here instead: <b>{demoCode}</b>
            </Banner>
          ) : (
            <Banner kind="soft">
              Codes can take a minute to arrive, and Outlook sometimes files them
              under Junk or Other. Check there before asking for a new one.
            </Banner>
          )}
          <div className="field">
            <label htmlFor="code">6-digit code</label>
            <input
              id="code"
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              placeholder="000000"
              style={{ fontSize: 26, letterSpacing: 8, textAlign: "center", fontWeight: 900 }}
            />
          </div>
          <button className="btn full" onClick={verify} disabled={busy || code.length !== 6}>
            {busy ? "Checking…" : "Verify and start"}
          </button>
          <button className="btn quiet full mt" onClick={resend} disabled={busy}>
            Send a new code
          </button>
          <p className="center small muted mt" style={{ marginBottom: 0 }}>
            Verifying is worth 25 MovePoints on its own.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth">
      <h1 className="center">Join Cuse-MoveMate</h1>
      <p className="center muted">Students only. Sign up with your {domainText} address.</p>

      <form className="card pad mt" onSubmit={submit}>
        {error && <Banner kind="bad">{error}</Banner>}

        <div className="field">
          <label htmlFor="e">Campus email</label>
          <input
            id="e"
            type="email"
            required
            value={form.email}
            onChange={(e) => set("email", e.target.value)}
            placeholder={"you@" + domains[0]}
            autoComplete="email"
          />
          {form.email.includes("@") && !emailOk && (
            <p className="small" style={{ color: "var(--danger)", margin: "6px 0 0" }}>
              MoveMate is for students. Use your {domainText} address.
            </p>
          )}
        </div>

        <div className="field">
          <label htmlFor="u">Username</label>
          <input id="u" type="text" required value={form.username}
            onChange={(e) => set("username", e.target.value)} autoComplete="username" />
        </div>

        <div className="field">
          <label htmlFor="p">Password</label>
          <input id="p" type="password" required minLength={6} value={form.password}
            onChange={(e) => set("password", e.target.value)} autoComplete="new-password" />
        </div>

        <LocationPicker
          value={form}
          onChange={(loc) => setForm((f) => ({ ...f, ...loc }))}
        />

        <div className="field">
          <label>Pick an avatar</label>
          <div className="chips">
            {EMOJI.map((em) => (
              <button key={em} type="button"
                className={"chip " + (form.avatar_emoji === em ? "on" : "")}
                onClick={() => set("avatar_emoji", em)}>{em}</button>
            ))}
          </div>
        </div>

        <button className="btn full" type="submit" disabled={busy || !emailOk}>
          {busy ? "Creating…" : "Send me a verification code"}
        </button>
        <p className="center small muted mt" style={{ marginBottom: 0 }}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
