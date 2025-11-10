import React, { useState } from "react";
import axios from "axios";

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
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

      console.log("Response:", res.data);
      localStorage.setItem("token", res.data.token);
      setMessage("Login erfolgreich!");
      window.location.reload(); // Seite neu laden -> JoinExam wird gezeigt
    } catch (err) {
      console.error("Login error:", err.response);
      setMessage("Fehler beim Login");
    }
  };

  return (
    <div>
      <h2>Studenten Login</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="E-Mail"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Passwort"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <button type="submit">Anmelden</button>
      </form>
      <p>{message}</p>
    </div>
  );
}

export default Login;

