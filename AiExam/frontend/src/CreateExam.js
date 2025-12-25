import React, { useState } from "react";
import axios from "axios";

function CreateExam({ onCreated }) {
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState("");
  const [createdExam, setCreatedExam] = useState(null);
  const [uploading, setUploading] = useState(false);
  const token = localStorage.getItem("token");

  const handleCreateExam = async (e) => {
    e.preventDefault();
    if (!title || !date) {
      setMessage("Titel und Datum sind erforderlich.");
      return;
    }

    setCreating(true);
    setMessage("");

    try {
      const res = await axios.post(
        "http://127.0.0.1:8000/api/students/exams/",
        { title, date, description },
        { headers: { Authorization: `Token ${token}` } }
      );
      setCreatedExam(res.data);
      setMessage("✅ Prüfung erfolgreich erstellt!");
      if (onCreated) onCreated(res.data);
    } catch (err) {
      console.error("Error creating exam:", err);
      if (err.response?.status === 403) {
        setMessage("❌ Nur Staff-Mitglieder können Prüfungen erstellen.");
      } else {
        setMessage("❌ Fehler beim Erstellen der Prüfung.");
      }
    } finally {
      setCreating(false);
    }
  };

  const handleUploadQuestions = async (e) => {
    const file = e.target.files[0];
    if (!file || !createdExam) {
      alert("Bitte erstelle zuerst eine Prüfung.");
      return;
    }

    if (!file.name.endsWith(".json")) {
      alert("Bitte wähle eine JSON-Datei aus.");
      return;
    }

    setUploading(true);
    setMessage("");

    const formData = new FormData();
    formData.append("exam_file", file);

    try {
      const res = await axios.post(
        `http://127.0.0.1:8000/api/students/exams/${createdExam.id}/upload-questions/`,
        formData,
        {
          headers: {
            Authorization: `Token ${token}`,
            "Content-Type": "multipart/form-data",
          },
        }
      );
      setMessage(`✅ Fragen erfolgreich hochgeladen! (${res.data.filename})`);
    } catch (err) {
      console.error("Error uploading questions:", err);
      if (err.response?.status === 403) {
        setMessage("❌ Nur Staff-Mitglieder können Fragen hochladen.");
      } else if (err.response?.status === 400) {
        setMessage(`❌ ${err.response.data.error || "Ungültige JSON-Datei."}`);
      } else {
        setMessage("❌ Fehler beim Hochladen der Fragen.");
      }
    } finally {
      setUploading(false);
      e.target.value = ""; // Reset file input
    }
  };

  const resetForm = () => {
    setTitle("");
    setDate("");
    setDescription("");
    setCreatedExam(null);
    setMessage("");
  };

  return (
    <div className="stack-lg">
      <div className="section-title">
        <span className="emoji">➕</span>
        <h2 style={{ margin: 0 }}>Prüfung erstellen</h2>
      </div>

      {!createdExam ? (
        <form onSubmit={handleCreateExam} className="card">
          <div className="stack">
            <label>
              <strong>Titel *</strong>
              <input
                type="text"
                className="input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="z.B. ML Exam"
                required
              />
            </label>

            <label>
              <strong>Datum & Uhrzeit *</strong>
              <input
                type="datetime-local"
                className="input"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
              />
            </label>

            <label>
              <strong>Beschreibung</strong>
              <textarea
                className="input"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optionale Beschreibung der Prüfung"
                rows={3}
              />
            </label>

            <div className="btn-group">
              <button type="submit" className="btn" disabled={creating}>
                {creating ? "Erstelle..." : "Prüfung erstellen"}
              </button>
              <button type="button" className="btn secondary" onClick={resetForm}>
                Zurücksetzen
              </button>
            </div>
          </div>
        </form>
      ) : (
        <div className="card success-box">
          <div className="stack">
            <h3 style={{ margin: 0 }}>✅ Prüfung erstellt: {createdExam.title}</h3>
            <p className="subtle" style={{ margin: 0 }}>
              ID: {createdExam.id} | Datum: {new Date(createdExam.date).toLocaleString("de-DE")}
            </p>

            <div style={{ marginTop: 16 }}>
              <label>
                <strong>Fragen hochladen (JSON-Datei)</strong>
                <div className="card muted-box" style={{ marginTop: 8, padding: 16 }}>
                  <p style={{ margin: "0 0 8px 0", fontSize: 14 }}>
                    <strong>Erwartetes Format:</strong>
                  </p>
                  <pre style={{ 
                    background: "#1a1a1a", 
                    padding: 12, 
                    borderRadius: 6, 
                    overflow: "auto",
                    fontSize: 12,
                    margin: 0
                  }}>
{`{
  "questions": [
    {
      "text": "Frage?",
      "options": ["Option 1", "Option 2", "Option 3"],
      "answer": "Option 1"
    }
  ]
}`}
                  </pre>
                </div>
                <input
                  type="file"
                  accept=".json"
                  onChange={handleUploadQuestions}
                  disabled={uploading}
                  style={{ marginTop: 8 }}
                />
              </label>
              {uploading && <p style={{ marginTop: 8 }}>⏳ Lade hoch...</p>}
            </div>

            <div className="btn-group" style={{ marginTop: 16 }}>
              <button className="btn secondary" onClick={resetForm}>
                Neue Prüfung erstellen
              </button>
            </div>
          </div>
        </div>
      )}

      {message && (
        <div className={`card ${message.startsWith("✅") ? "success-box" : "error-box"}`}>
          <p style={{ margin: 0 }}>{message}</p>
        </div>
      )}
    </div>
  );
}

export default CreateExam;

