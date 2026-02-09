import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";

function CreateExam({ onCreated }) {
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [description, setDescription] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState("");
  const [createdExam, setCreatedExam] = useState(null);
  const [uploadingPdf, setUploadingPdf] = useState(false);
  const [uploadedPdfName, setUploadedPdfName] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState(null);
  const [saving, setSaving] = useState(false);
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
        { title, date, description, duration_minutes: durationMinutes },
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

  const handleUploadPdf = async (e) => {
    const file = e.target.files[0];
    if (!file || !createdExam) {
      alert("Bitte erstelle zuerst eine Prüfung.");
      return;
    }

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Bitte wähle eine PDF-Datei aus.");
      return;
    }

    setUploadingPdf(true);
    setMessage("");

    const formData = new FormData();
    formData.append("pdf_file", file);

    try {
      const res = await axios.post(
        `http://127.0.0.1:8000/api/students/exams/${createdExam.id}/upload-pdf/`,
        formData,
        {
          headers: {
            Authorization: `Token ${token}`,
            "Content-Type": "multipart/form-data",
          },
        }
      );
      setMessage(`✅ ${res.data.message} (${res.data.questions_count} Fragen generiert)`);
      setUploadedPdfName(file.name);
      if (createdExam) {
        setTimeout(() => {
          loadQuestions();
        }, 500);
      }
    } catch (err) {
      console.error("Error uploading PDF:", err);
      if (err.response?.status === 403) {
        setMessage("❌ Nur Staff-Mitglieder können PDFs hochladen.");
      } else if (err.response?.status === 400) {
        setMessage(`❌ ${err.response.data.error || "Fehler beim Verarbeiten der PDF."}`);
      } else {
        setMessage("❌ Fehler beim Hochladen der PDF.");
      }
    } finally {
      setUploadingPdf(false);
    }
  };

  const loadQuestions = useCallback(async () => {
    if (!createdExam) return;
    setLoadingQuestions(true);
    try {
      const res = await axios.get(
        `http://127.0.0.1:8000/api/students/exams/${createdExam.id}/questions/professor/`,
        { headers: { Authorization: `Token ${token}` } }
      );
      const loadedQuestions = res.data.questions || [];
      setQuestions(loadedQuestions);
      if (loadedQuestions.length === 0) {
        console.warn("Keine Fragen gefunden für Prüfung", createdExam.id);
      } else {
        console.log(`✅ ${loadedQuestions.length} Fragen geladen`);
      }
    } catch (err) {
      console.error("Error loading questions:", err);
      if (err.response?.status === 404) {
        console.warn("Prüfung nicht gefunden oder keine Fragen vorhanden");
      } else if (err.response?.status === 403) {
        console.warn("Keine Berechtigung zum Laden der Fragen");
      }
      setQuestions([]);
    } finally {
      setLoadingQuestions(false);
    }
  }, [createdExam, token]);

  useEffect(() => {
    if (createdExam?.id) {
      loadQuestions();
    }
  }, [createdExam?.id, loadQuestions]);

  const handleSaveQuestions = async () => {
    if (!createdExam) return;
    
    setSaving(true);
    try {
      const res = await axios.post(
        `http://127.0.0.1:8000/api/students/exams/${createdExam.id}/questions/save/`,
        { questions },
        { headers: { Authorization: `Token ${token}` } }
      );
      setMessage(`✅ ${res.data.message}`);
    } catch (err) {
      console.error("Error saving questions:", err);
      setMessage("❌ Fehler beim Speichern der Fragen.");
    } finally {
      setSaving(false);
    }
  };

  const handleEditQuestion = (index) => {
    setEditingQuestion(index);
  };

  const handleSaveQuestion = (index, updatedQuestion) => {
    const newQuestions = [...questions];
    newQuestions[index] = updatedQuestion;
    setQuestions(newQuestions);
    setEditingQuestion(null);
  };

  const handleDeleteQuestion = (index) => {
    if (window.confirm("Möchten Sie diese Frage wirklich löschen?")) {
      const newQuestions = questions.filter((_, i) => i !== index);
      setQuestions(newQuestions);
    }
  };

  const handleAddQuestion = () => {
    const newQuestion = {
      text: "Neue Frage?",
      options: ["Option 1", "Option 2", "Option 3", "Option 4"],
      answer: "Option 1"
    };
    setQuestions([...questions, newQuestion]);
    setEditingQuestion(questions.length);
  };

  const resetForm = () => {
    setTitle("");
    setDate("");
    setDescription("");
    setDurationMinutes(60);
    setCreatedExam(null);
    setMessage("");
    setQuestions([]);
    setEditingQuestion(null);
    setUploadedPdfName(null);
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
              <strong>Prüfungsdauer (Minuten) *</strong>
              <input
                type="number"
                className="input"
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(parseInt(e.target.value) || 60)}
                placeholder="60"
                min="1"
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
                <strong>📄 Vorlesungsfolien (PDF) hochladen</strong>
                <p className="subtle" style={{ marginTop: 4, fontSize: 13 }}>
                  Laden Sie eine PDF-Datei mit Vorlesungsfolien hoch. Das System extrahiert automatisch den Text und generiert Prüfungsfragen daraus.
                </p>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleUploadPdf}
                  disabled={uploadingPdf}
                  style={{ marginTop: 8 }}
                  id="pdf-upload-input"
                />
                {uploadedPdfName && (
                  <div className="card success-box" style={{ marginTop: 8, padding: 8 }}>
                    <span style={{ fontSize: 13 }}>✅ Hochgeladen: {uploadedPdfName}</span>
                  </div>
                )}
              </label>
              {uploadingPdf && <p style={{ marginTop: 8 }}>⏳ Verarbeite PDF-Folien und generiere Fragen...</p>}
            </div>

            {questions.length > 0 && (
              <div style={{ marginTop: 24 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <h3 style={{ margin: 0 }}>Generierte Fragen ({questions.length})</h3>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn" onClick={handleSaveQuestions} disabled={saving}>
                      {saving ? "Speichere..." : "💾 Fragen speichern"}
                    </button>
                    <button className="btn secondary" onClick={handleAddQuestion}>
                      ➕ Frage hinzufügen
                    </button>
                  </div>
                </div>
                
                {loadingQuestions ? (
                  <div className="card"><p>Lade Fragen...</p></div>
                ) : (
                  <div className="stack" style={{ gap: 12 }}>
                    {questions.map((q, idx) => (
                      <QuestionEditor
                        key={idx}
                        question={q}
                        index={idx}
                        isEditing={editingQuestion === idx}
                        onEdit={() => handleEditQuestion(idx)}
                        onSave={(updated) => handleSaveQuestion(idx, updated)}
                        onCancel={() => setEditingQuestion(null)}
                        onDelete={() => handleDeleteQuestion(idx)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

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

function QuestionEditor({ question, index, isEditing, onEdit, onSave, onCancel, onDelete }) {
  const [editedQuestion, setEditedQuestion] = useState(question);

  useEffect(() => {
    setEditedQuestion(question);
  }, [question]);

  if (!isEditing) {
    return (
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>
              Frage {index + 1}: {question.text}
            </div>
            {question.options && question.options.length > 0 && (
              <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                {question.options.map((opt, i) => (
                  <li key={i} style={{ marginBottom: 4, wordWrap: "break-word", maxWidth: "100%" }}>
                    {opt.length > 200 ? opt.substring(0, 200) + "..." : opt} {opt === question.answer && "✓"}
                  </li>
                ))}
              </ul>
            )}
            {question.answer && (
              <div className="subtle" style={{ marginTop: 8, fontSize: 13, maxWidth: "100%", wordWrap: "break-word" }}>
                <strong>Richtige Antwort:</strong> {question.answer.length > 150 ? question.answer.substring(0, 150) + "..." : question.answer}
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn secondary" onClick={onEdit} style={{ fontSize: 12, padding: "6px 12px" }}>
              ✏️ Bearbeiten
            </button>
            <button className="btn secondary" onClick={onDelete} style={{ fontSize: 12, padding: "6px 12px", color: "var(--danger)" }}>
              🗑️ Löschen
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ border: "2px solid var(--primary)" }}>
      <div className="stack">
        <label>
          <strong>Frage {index + 1} *</strong>
          <textarea
            className="input"
            value={editedQuestion.text || ""}
            onChange={(e) => setEditedQuestion({ ...editedQuestion, text: e.target.value })}
            rows={3}
            style={{ marginTop: 4 }}
          />
        </label>

        <label>
          <strong>Optionen (eine pro Zeile) *</strong>
          <textarea
            className="input"
            value={(editedQuestion.options || []).join("\n")}
            onChange={(e) => {
              const options = e.target.value.split("\n").filter(o => o.trim());
              setEditedQuestion({ ...editedQuestion, options });
            }}
            rows={4}
            placeholder="Option 1&#10;Option 2&#10;Option 3&#10;Option 4"
            style={{ marginTop: 4 }}
          />
        </label>

        <label>
          <strong>Richtige Antwort *</strong>
          <input
            className="input"
            type="text"
            value={editedQuestion.answer || ""}
            onChange={(e) => setEditedQuestion({ ...editedQuestion, answer: e.target.value })}
            placeholder="Muss genau einer der Optionen entsprechen"
            style={{ marginTop: 4 }}
          />
        </label>

        <div className="btn-group" style={{ marginTop: 8 }}>
          <button className="btn" onClick={() => onSave(editedQuestion)}>
            💾 Speichern
          </button>
          <button className="btn secondary" onClick={onCancel}>
            Abbrechen
          </button>
        </div>
      </div>
    </div>
  );
}

export default CreateExam;

