import React, { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";

function CreateExam({ onCreated }) {
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [description, setDescription] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState("");
  const [createdExam, setCreatedExam] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState(null);
  const [saving, setSaving] = useState(false);

  const [ragTopics, setRagTopics] = useState("");
  const [ragNPerTopic, setRagNPerTopic] = useState(1);
  const [ragGroqKey, setRagGroqKey] = useState("");
  const [ragGenerating, setRagGenerating] = useState(false);
  const [ragPdfName, setRagPdfName] = useState(null);
  const ragFileRef = useRef(null);

  const token = localStorage.getItem("token");

  const handleCreateExam = async (e) => {
    e.preventDefault();
    if (!title || !date) {
      setMessage("Title and date are required.");
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
      setMessage("✅ Exam created successfully!");
      if (onCreated) onCreated(res.data);
    } catch (err) {
      console.error("Error creating exam:", err);
      if (err.response?.status === 403) {
        setMessage("❌ Only staff members can create exams.");
      } else {
        setMessage("❌ Error creating the exam.");
      }
    } finally {
      setCreating(false);
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
        console.warn("No questions found for exam", createdExam.id);
      } else {
        console.log(`✅ ${loadedQuestions.length} questions loaded`);
      }
    } catch (err) {
      console.error("Error loading questions:", err);
      if (err.response?.status === 404) {
        console.warn("Exam not found or no questions available");
      } else if (err.response?.status === 403) {
        console.warn("No permission to load questions");
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
      setMessage("❌ Error saving questions.");
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
    if (window.confirm("Are you sure you want to delete this question?")) {
      const newQuestions = questions.filter((_, i) => i !== index);
      setQuestions(newQuestions);
    }
  };

  const handleAddQuestion = () => {
    const newQuestion = {
      text: "New question?",
      options: ["Option 1", "Option 2", "Option 3", "Option 4"],
      answer: "Option 1"
    };
    setQuestions([...questions, newQuestion]);
    setEditingQuestion(questions.length);
  };

  const handleRagGenerate = async () => {
    const file = ragFileRef.current?.files?.[0];
    if (!file) {
      setMessage("❌ Please select a PDF file for RAG generation.");
      return;
    }
    if (!ragTopics.trim()) {
      setMessage("❌ Please enter at least one topic.");
      return;
    }

    setRagGenerating(true);
    setMessage("");

    const formData = new FormData();
    formData.append("pdf_file", file);
    formData.append("topics", ragTopics);
    formData.append("n_per_topic", ragNPerTopic);
    if (ragGroqKey.trim()) {
      formData.append("groq_api_key", ragGroqKey.trim());
    }

    try {
      const res = await axios.post(
        `http://127.0.0.1:8000/api/students/exams/${createdExam.id}/rag-generate/`,
        formData,
        {
          headers: {
            Authorization: `Token ${token}`,
            "Content-Type": "multipart/form-data",
          },
        }
      );
      const newQs = res.data.questions || [];
      setQuestions(newQs);
      setRagPdfName(file.name);
      setMessage(`✅ ${res.data.message}`);
    } catch (err) {
      const errMsg = err.response?.data?.error || "Unknown error during RAG generation.";
      setMessage(`❌ ${errMsg}`);
    } finally {
      setRagGenerating(false);
    }
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
    setRagTopics("");
    setRagPdfName(null);
    setRagGroqKey("");
  };

  return (
    <div className="stack-lg">
      <div className="section-title">
        <span className="emoji">➕</span>
        <h2 style={{ margin: 0 }}>Create Exam</h2>
      </div>

      {!createdExam ? (
        <form onSubmit={handleCreateExam} className="card">
          <div className="stack">
            <label>
              <strong>Title *</strong>
              <input
                type="text"
                className="input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. ML Exam"
                required
              />
            </label>

            <label>
              <strong>Date & Time *</strong>
              <input
                type="datetime-local"
                className="input"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
              />
            </label>

            <label>
              <strong>Exam Duration (minutes) *</strong>
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
              <strong>Description</strong>
              <textarea
                className="input"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description of the exam"
                rows={3}
              />
            </label>

            <div className="btn-group">
              <button type="submit" className="btn" disabled={creating}>
                {creating ? "Creating..." : "Create Exam"}
              </button>
              <button type="button" className="btn secondary" onClick={resetForm}>
                Reset
              </button>
            </div>
          </div>
        </form>
      ) : (
        <div className="card success-box">
          <div className="stack">
            <h3 style={{ margin: 0 }}>✅ Exam created: {createdExam.title}</h3>
            <p className="subtle" style={{ margin: 0 }}>
              ID: {createdExam.id} | Date: {new Date(createdExam.date).toLocaleString("en-GB")}
            </p>

            <div className="card" style={{ marginTop: 16, padding: 16, background: "rgba(255,255,255,0.04)" }}>
              <p style={{ margin: "0 0 4px 0", fontWeight: 700, fontSize: 15 }}>🤖 Generate Questions with AI-RAG</p>
              <p className="subtle" style={{ fontSize: 13, marginBottom: 16 }}>
                Upload a PDF and specify topics – the system uses Retrieval-Augmented Generation with the Groq LLM
                to generate precise multiple-choice questions directly from the lecture slides.
              </p>

              <div className="stack" style={{ gap: 12 }}>
                <label>
                  <strong>📄 PDF File (Lecture Slides) *</strong>
                  <input
                    ref={ragFileRef}
                    type="file"
                    accept=".pdf"
                    disabled={ragGenerating}
                    style={{ marginTop: 6, display: "block" }}
                    onChange={(e) => setRagPdfName(e.target.files?.[0]?.name || null)}
                  />
                  {ragPdfName && (
                    <span className="subtle" style={{ fontSize: 12, marginTop: 4, display: "block" }}>
                      📎 {ragPdfName}
                    </span>
                  )}
                </label>

                <label>
                  <strong>📝 Topics (one topic per line) *</strong>
                  <p className="subtle" style={{ fontSize: 12, margin: "4px 0" }}>
                    e.g. "Deep Learning", "Gradient Descent", "Overfitting"
                  </p>
                  <textarea
                    className="input"
                    rows={5}
                    placeholder={"What is Deep Learning?\nGradient Descent Algorithm\nOverfitting and Regularization\nNeural Network Architecture"}
                    value={ragTopics}
                    onChange={(e) => setRagTopics(e.target.value)}
                    disabled={ragGenerating}
                    style={{ marginTop: 4, fontFamily: "monospace", fontSize: 13 }}
                  />
                </label>

                <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  <label style={{ flex: "1 1 140px" }}>
                    <strong>Questions per Topic</strong>
                    <input
                      type="number"
                      className="input"
                      min={1}
                      max={5}
                      value={ragNPerTopic}
                      onChange={(e) => setRagNPerTopic(Math.min(5, Math.max(1, parseInt(e.target.value) || 1)))}
                      disabled={ragGenerating}
                      style={{ marginTop: 4 }}
                    />
                  </label>

                  <label style={{ flex: "2 1 260px" }}>
                    <strong>Groq API Key</strong>
                    <p className="subtle" style={{ fontSize: 12, margin: "4px 0" }}>
                      If not set as an environment variable
                    </p>
                    <input
                      type="password"
                      className="input"
                      placeholder="gsk_..."
                      value={ragGroqKey}
                      onChange={(e) => setRagGroqKey(e.target.value)}
                      disabled={ragGenerating}
                      style={{ marginTop: 4 }}
                    />
                  </label>
                </div>

                <button
                  className="btn"
                  onClick={handleRagGenerate}
                  disabled={ragGenerating}
                  type="button"
                  style={{ alignSelf: "flex-start", marginTop: 4 }}
                >
                  {ragGenerating ? "⏳ RAG is generating questions..." : "🚀 Generate Questions with RAG"}
                </button>

                {ragGenerating && (
                  <div style={{ fontSize: 13, color: "var(--accent)" }}>
                    ⏳ Please wait – Embedding, Retrieval and LLM generation running...
                    <br />
                    <span className="subtle">This may take 30–90 seconds.</span>
                  </div>
                )}
              </div>
            </div>

            {questions.length > 0 && (
              <div style={{ marginTop: 24 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <h3 style={{ margin: 0 }}>Generated Questions ({questions.length})</h3>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn" onClick={handleSaveQuestions} disabled={saving}>
                      {saving ? "Saving..." : "💾 Save Questions"}
                    </button>
                    <button className="btn secondary" onClick={handleAddQuestion}>
                      ➕ Add Question
                    </button>
                  </div>
                </div>
                
                {loadingQuestions ? (
                  <div className="card"><p>Loading questions...</p></div>
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
                Create New Exam
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
              Question {index + 1}: {question.text}
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
                <strong>Correct Answer:</strong> {question.answer.length > 150 ? question.answer.substring(0, 150) + "..." : question.answer}
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn secondary" onClick={onEdit} style={{ fontSize: 12, padding: "6px 12px" }}>
              ✏️ Edit
            </button>
            <button className="btn secondary" onClick={onDelete} style={{ fontSize: 12, padding: "6px 12px", color: "var(--danger)" }}>
              🗑️ Delete
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
          <strong>Question {index + 1} *</strong>
          <textarea
            className="input"
            value={editedQuestion.text || ""}
            onChange={(e) => setEditedQuestion({ ...editedQuestion, text: e.target.value })}
            rows={3}
            style={{ marginTop: 4 }}
          />
        </label>

        <label>
          <strong>Options (one per line) *</strong>
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
          <strong>Correct Answer *</strong>
          <input
            className="input"
            type="text"
            value={editedQuestion.answer || ""}
            onChange={(e) => setEditedQuestion({ ...editedQuestion, answer: e.target.value })}
            placeholder="Must exactly match one of the options"
            style={{ marginTop: 4 }}
          />
        </label>

        <div className="btn-group" style={{ marginTop: 8 }}>
          <button className="btn" onClick={() => onSave(editedQuestion)}>
            💾 Save
          </button>
          <button className="btn secondary" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export default CreateExam;

