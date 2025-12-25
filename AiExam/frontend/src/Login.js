import React, { useState } from "react";
import axios from "axios";

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    try {
      const res = await axios.post(
        "http://127.0.0.1:8000/api/students/login/",
        { email, password },
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      localStorage.setItem("token", res.data.token);
      localStorage.setItem("isStaff", res.data.is_staff ? "true" : "false");
      setMessage("Login erfolgreich!");
      setTimeout(() => {
        window.location.reload();
      }, 500);
    } catch (err) {
      setMessage(err.response?.data?.error || "Fehler beim Login");
    }
  };

  return (
    <div className="split">
      <div className="panel card">
        <div className="stack-lg">
          <div className="section-title">
            <span className="emoji">🔐</span>
            <h2 style={{ margin: 0 }}>Anmeldung</h2>
          </div>

          <form className="form" onSubmit={handleSubmit}>
            <div className="field">
              <label className="subtle">E-Mail</label>
              <input
                className="input"
                type="email"
                placeholder="name@uni.de"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label className="subtle">Passwort</label>
              <input
                className="input"
                type="password"
                placeholder="Passwort"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <div className="row">
              <button className="btn" type="submit">
                Anmelden
              </button>
            </div>
            {message && (
              <div className={`card ${message.includes("erfolgreich") ? "success-box" : "error-box"}`} style={{ marginTop: 12 }}>
                <p style={{ margin: 0 }}>{message}</p>
              </div>
            )}
          </form>
        </div>
      </div>
      <div className="muted-box card">
        <div className="stack">
          <div className="section-title">
            <span className="emoji">💡</span>
            <h3 style={{ margin: 0 }}>Hinweis</h3>
          </div>
          <p className="subtle" style={{ margin: 0 }}>
            Melde dich mit deiner Unimail an. Das System erkennt automatisch,
            ob du Student oder Professor bist.
          </p>
        </div>
      </div>
    </div>
  );
}

export default Login;
