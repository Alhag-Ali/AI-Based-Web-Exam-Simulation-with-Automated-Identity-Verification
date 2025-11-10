import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import Webcam from "react-webcam";

function JoinExam() {
  const [exams, setExams] = useState([]);
  const [selectedExam, setSelectedExam] = useState(null);

  const [step, setStep] = useState(1);
  const [faceDataUrl, setFaceDataUrl] = useState(null);
  const [idDataUrl, setIdDataUrl] = useState(null);

  const [verifying, setVerifying] = useState(false);
  const [verified, setVerified] = useState(false);
  const [message, setMessage] = useState("");
  const [details, setDetails] = useState(null);
  const [joining, setJoining] = useState(false);
  const webcamRef = useRef(null);
  const token = localStorage.getItem("token");

  // 📘 Prüfungen laden
  useEffect(() => {
    axios
      .get("http://127.0.0.1:8000/api/students/exams/", {
        headers: { Authorization: `Token ${token}` },
      })
      .then((res) => setExams(res.data))
      .catch((err) => console.error("Exams laden fehlgeschlagen:", err));
  }, [token]);

  // Helper: DataURL -> Blob
  const dataUrlToBlob = async (dataUrl) => {
    const res = await fetch(dataUrl);
    return await res.blob();
  };

  // 📷 Gesicht aufnehmen
  const captureFace = () => {
    const shot = webcamRef.current?.getScreenshot();
    if (!shot) return;
    setFaceDataUrl(shot);
    setVerified(false);
    setMessage("");
    setDetails(null);
    setStep(2);
  };

  // 🪪 Ausweis aufnehmen
  const captureId = () => {
    const shot = webcamRef.current?.getScreenshot();
    if (!shot) return;
    setIdDataUrl(shot);
    setVerified(false);
    setMessage("");
    setDetails(null);
    setStep(3);
  };

  // 🔄 Schritte zurücksetzen
  const resetFace = () => {
    setFaceDataUrl(null);
    setVerified(false);
    setMessage("");
    setDetails(null);
    setStep(1);
  };

  const resetId = () => {
    setIdDataUrl(null);
    setVerified(false);
    setMessage("");
    setDetails(null);
    setStep(2);
  };

  // 🧠 Verifikation starten
  const verifyNow = async () => {
    if (!faceDataUrl || !idDataUrl) return;
    setVerifying(true);
    setVerified(false);
    setMessage("Überprüfung läuft …");
    setDetails(null);

    try {
      const faceBlob = await dataUrlToBlob(faceDataUrl);
      const idBlob = await dataUrlToBlob(idDataUrl);

      const formData = new FormData();
      formData.append("live_image", faceBlob, "live.jpg");
      formData.append("id_image", idBlob, "id.jpg");

      const res = await axios.post(
        "http://127.0.0.1:8000/api/students/verify-identity/",
        formData,
        {
          headers: {
            Authorization: `Token ${token}`,
            "Content-Type": "multipart/form-data",
          },
        }
      );

      console.log("verify response:", res.data);
      setVerified(res.data.verified);
      setMessage(res.data.message || "");
      setDetails(res.data);
    } catch (err) {
      console.error(err);
      setVerified(false);
      setMessage(err.response?.data?.message || "Fehler bei der Verifikation.");
      setDetails(err.response?.data || null);
    } finally {
      setVerifying(false);
    }
  };

  // 🧾 Prüfung beitreten
  const joinExam = async (examId) => {
    if (!verified) return;
    setJoining(true);
    try {
      const res = await axios.post(
        `http://127.0.0.1:8000/api/students/exams/${examId}/join/`,
        {},
        { headers: { Authorization: `Token ${token}` } }
      );
      alert(res.data.message || "Erfolgreich der Prüfung beigetreten!");
      // Reset
      setSelectedExam(null);
      setStep(1);
      setFaceDataUrl(null);
      setIdDataUrl(null);
      setVerified(false);
      setMessage("");
      setDetails(null);
    } catch (err) {
      console.error(err);
      alert("Fehler beim Beitritt zur Prüfung.");
    } finally {
      setJoining(false);
    }
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>📋 Prüfungen</h2>
      <ul>
        {exams.map((exam) => (
          <li key={exam.id} style={{ marginBottom: 10 }}>
            {exam.title} — {exam.date}
            <button
              style={{ marginLeft: 10 }}
              onClick={() => {
                setSelectedExam(exam);
                resetFace();
                resetId();
              }}
            >
              Beitreten
            </button>
          </li>
        ))}
      </ul>

      {selectedExam && (
        <div style={{ marginTop: 28 }}>
          <h3>🧾 Identitätsprüfung für {selectedExam.title}</h3>
          <p style={{ marginBottom: 14 }}>
            Schritt 1️⃣ <b>Gesicht aufnehmen</b> → Schritt 2️⃣{" "}
            <b>Ausweis aufnehmen</b> → Schritt 3️⃣ <b>Vergleichen</b>
          </p>

          <Webcam
            ref={webcamRef}
            audio={false}
            screenshotFormat="image/jpeg"
            width={480}
            height={360}
            videoConstraints={{ facingMode: "user" }}
          />

          {/* Steuerung */}
          <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
            {step === 1 && <button onClick={captureFace}>📷 Gesicht aufnehmen</button>}
            {step >= 2 && <button onClick={resetFace}>↩ Gesicht neu aufnehmen</button>}
            {step === 2 && <button onClick={captureId}>🪪 Ausweis aufnehmen</button>}
            {step >= 3 && <button onClick={resetId}>↩ Ausweis neu aufnehmen</button>}
            <button
              onClick={verifyNow}
              disabled={!faceDataUrl || !idDataUrl || verifying}
            >
              🔍 Vergleichen
            </button>
            <button
              onClick={() => joinExam(selectedExam.id)}
              disabled={!verified || joining}
            >
              ✅ Prüfung beitreten
            </button>
          </div>

          {/* Vorschau */}
          <div style={{ marginTop: 16, display: "flex", gap: 16, flexWrap: "wrap" }}>
            <Preview title="Gesicht" dataUrl={faceDataUrl} />
            <Preview title="Ausweis" dataUrl={idDataUrl} />
          </div>

          {/* Ergebnis */}
          <div style={{ marginTop: 16 }}>
            {verifying && <p>⏳ Überprüfung läuft …</p>}
            {message && (
              <p
                style={{
                  color: verified ? "green" : "crimson",
                  fontWeight: 600,
                  marginBottom: 8,
                }}
              >
                {message}
              </p>
            )}

            {details && (
              <div
                style={{
                  background: "#f9fafb",
                  border: "1px solid #e5e7eb",
                  borderRadius: 8,
                  padding: 10,
                  fontSize: 13,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    flexWrap: "wrap",
                    marginBottom: 8,
                  }}
                >
                  <Pill label="Gesicht erkannt" ok={details.face_detected_live} />
                  <Pill label="Ausweisfoto erkannt" ok={details.face_detected_id} />
                  <Pill label="Gesichter matchen" ok={details.verified} />
                </div>
                {details.distance !== undefined && (
                  <p style={{ margin: 0, color: "#374151" }}>
                    Distanz: <b>{details.distance?.toFixed(2)}</b> (Schwelle: {details.threshold})
                  </p>
                )}
                {details.hints?.length > 0 ? (
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {details.hints.map((h, i) => (
                      <li key={i}>💡 {h}</li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ margin: 0, color: "#6b7280" }}>
                    Tipps erscheinen hier, wenn etwas fehlt (Beleuchtung, Schärfe, Position …)
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Preview({ title, dataUrl }) {
  return (
    <div style={{ width: 220 }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{title}</div>
      <div
        style={{
          width: 220,
          height: 160,
          background: "#f3f4f6",
          border: "1px solid #e5e7eb",
          borderRadius: 8,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
        }}
      >
        {dataUrl ? (
          <img src={dataUrl} alt={title} style={{ width: "100%" }} />
        ) : (
          <span style={{ color: "#6b7280" }}>noch kein Bild</span>
        )}
      </div>
    </div>
  );
}

function Pill({ label, ok }) {
  return (
    <span
      style={{
        padding: "4px 10px",
        borderRadius: 999,
        background: ok ? "#dcfce7" : "#fee2e2",
        border: "1px solid #d1d5db",
        fontSize: 12.5,
      }}
    >
      {label}: {ok ? "✅" : "❌"}
    </span>
  );
}

export default JoinExam;

