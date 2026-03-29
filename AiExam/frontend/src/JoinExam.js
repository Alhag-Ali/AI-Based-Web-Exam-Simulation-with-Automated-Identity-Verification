import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import Webcam from "react-webcam";

function JoinExam({ onJoined }) {
  const [exams, setExams] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [selectedExam, setSelectedExam] = useState(null);

  const [step, setStep] = useState(1);
  const [faceDataUrl, setFaceDataUrl] = useState(null);
  const [idDataUrl, setIdDataUrl] = useState(null);

  const [verifying, setVerifying] = useState(false);
  const [verified, setVerified] = useState(false);
  const [message, setMessage] = useState("");
  const [details, setDetails] = useState(null);
  const [joining, setJoining] = useState(false);
  const [enrollError, setEnrollError] = useState(null);
  const webcamRef = useRef(null);
  const token = localStorage.getItem("token");

  useEffect(() => {
    setLoadError(null);
    axios
      .get("http://127.0.0.1:8000/api/students/exams/", {
        headers: { Authorization: `Token ${token}` },
      })
      .then((res) => setExams(res.data))
      .catch((err) => {
        console.error("Failed to load exams:", err);
        const msg =
          err?.response?.status === 401
            ? "Unauthorized – please sign in again."
            : "Error loading exams.";
        setLoadError(msg);
      });
  }, [token]);

  const dataUrlToBlob = async (dataUrl) => {
    const res = await fetch(dataUrl);
    return await res.blob();
  };

  const captureFace = () => {
    const shot = webcamRef.current?.getScreenshot();
    if (!shot) return;
    setFaceDataUrl(shot);
    setVerified(false);
    setMessage("");
    setDetails(null);
    setStep(2);
  };

  const captureId = () => {
    const shot = webcamRef.current?.getScreenshot();
    if (!shot) return;
    setIdDataUrl(shot);
    setVerified(false);
    setMessage("");
    setDetails(null);
    setStep(3);
  };

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

  const verifyNow = async () => {
    if (!faceDataUrl || !idDataUrl) return;
    setVerifying(true);
    setVerified(false);
    setMessage("Verification in progress …");
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
      setMessage(err.response?.data?.message || "Verification failed.");
      setDetails(err.response?.data || null);
    } finally {
      setVerifying(false);
    }
  };

  const requestHelp = async () => {
    if (!selectedExam) {
      alert("Please select an exam first.");
      return;
    }
    try {
      const res = await axios.post(
        "http://127.0.0.1:8000/api/students/help-request/",
        {
          exam_id: selectedExam.id,
          message:
            "Verification failed or problematic. Please check manually.",
        },
        { headers: { Authorization: `Token ${token}` } }
      );
      alert(res.data?.message || "The provider has been notified.");
    } catch (err) {
      console.error(err);
      alert("Could not send help request.");
    }
  };

  const joinExam = async (examId) => {
    if (!verified) return;
    setJoining(true);
    try {
      const res = await axios.post(
        `http://127.0.0.1:8000/api/students/exams/${examId}/join/`,
        {},
        { headers: { Authorization: `Token ${token}` } }
      );
      const joinedMessage = res.data.message || "Successfully joined the exam!";
      console.log(joinedMessage);
      const exam = exams.find((e) => e.id === examId) || selectedExam;
      if (onJoined && exam) {
        onJoined(exam);
        return;
      }
      setSelectedExam(null);
      setStep(1);
      setFaceDataUrl(null);
      setIdDataUrl(null);
      setVerified(false);
      setMessage("");
      setDetails(null);
    } catch (err) {
      console.error(err);
      const errData = err.response?.data;
      if (errData?.error === "not_enrolled") {
        setEnrollError(errData.message || "You are not authorized for this exam.");
      } else {
        alert(errData?.message || "Error joining the exam.");
      }
    } finally {
      setJoining(false);
    }
  };

  return (
    <div className="stack-lg">
      <div className="section-title">
        <span className="emoji">📝</span>
        <h2 style={{ margin: 0 }}>Exams</h2>
      </div>
      {loadError && <div className="card" style={{ borderColor: "rgba(239,68,68,.35)" }}>
        <p style={{ margin: 0, color: "#fecaca" }}>{loadError}</p>
      </div>}
      {!loadError && exams.length === 0 && (
        <div className="card muted-box"><p style={{ margin: 0 }} className="subtle">No exams found.</p></div>
      )}
      <ul className="list stack">
        {exams.map((exam) => (
          <li key={exam.id} className="list-item card">
            <div className="stack">
              <div style={{ fontWeight: 700 }}>{exam.title}</div>
              <div className="subtle">{exam.date}</div>
            </div>
            <button
              className="btn secondary"
              onClick={() => {
                setSelectedExam(exam);
                setEnrollError(null);
                resetFace();
                resetId();
              }}
            >
              Join
            </button>
          </li>
        ))}
      </ul>

      {selectedExam && (
        <div className="panel" style={{ padding: 16, marginTop: 8 }}>
          <div className="stack">
            <h3 style={{ margin: 0 }}>🧾 Identity Verification for {selectedExam.title}</h3>
            <p className="subtle" style={{ margin: 0 }}>
              Step 1️⃣ <b>Capture face</b> → Step 2️⃣ <b>Capture ID</b> → Step 3️⃣ <b>Compare</b>
            </p>
          </div>

          {enrollError && (
            <div className="card" style={{ borderColor: "rgba(239,68,68,.4)", background: "rgba(239,68,68,.08)", marginTop: 12 }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                <span style={{ fontSize: 22 }}>🚫</span>
                <div>
                  <div style={{ fontWeight: 700, color: "#fca5a5", marginBottom: 4 }}>Not authorized</div>
                  <div style={{ color: "#fecaca", fontSize: 14 }}>{enrollError}</div>
                </div>
              </div>
            </div>
          )}

          <Webcam
            ref={webcamRef}
            audio={false}
            screenshotFormat="image/jpeg"
            width={480}
            height={360}
            videoConstraints={{ facingMode: "user" }}
            style={{ borderRadius: 12, border: "1px solid rgba(255,255,255,0.14)", marginTop: 12, width: "100%", maxWidth: 560 }}
          />

          <div className="btn-group" style={{ marginTop: 12 }}>
            {step === 1 && <button className="btn" onClick={captureFace}>📷 Capture Face</button>}
            {step >= 2 && <button className="btn secondary" onClick={resetFace}>↩ Retake Face</button>}
            {step === 2 && <button className="btn" onClick={captureId}>🪪 Capture ID</button>}
            {step >= 3 && <button className="btn secondary" onClick={resetId}>↩ Retake ID</button>}
            <button
              className="btn warning"
              onClick={verifyNow}
              disabled={!faceDataUrl || !idDataUrl || verifying}
            >
              🔍 Compare
            </button>
            <button className="btn secondary" onClick={requestHelp} title="Request manual check from provider">
              🆘 Request Help
            </button>
            <button
              className={verified ? "btn success" : "btn secondary"}
              onClick={() => joinExam(selectedExam.id)}
              disabled={!verified || joining}
              title={verified ? "Ready – identity confirmed" : "Enabled after successful verification"}
            >
              <span className="row" style={{ alignItems: "center" }}>
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 999,
                    marginRight: 8,
                    background: verified ? "#16a34a" : "rgba(255,255,255,.25)",
                    boxShadow: verified ? "0 0 0 6px rgba(22,163,74,.18)" : "none"
                  }}
                />
                {verified ? "✅ Join Exam" : "Join Exam"}
              </span>
            </button>
          </div>

          <div className="row" style={{ marginTop: 16 }}>
            <Preview title="Face" dataUrl={faceDataUrl} />
            <Preview title="ID" dataUrl={idDataUrl} />
          </div>

          <div style={{ marginTop: 16 }}>
            {verifying && <p className="subtle">⏳ Verification in progress …</p>}
            {message && (
              <div className="card" style={{ borderColor: verified ? "rgba(34,197,94,.35)" : "rgba(239,68,68,.35)" }}>
                <div className="row" style={{ alignItems: "center" }}>
                  <span
                    style={{
                      width: 12,
                      height: 12,
                      borderRadius: 999,
                      background: verified ? "#22c55e" : "#ef4444",
                      boxShadow: verified ? "0 0 0 6px rgba(34,197,94,.15)" : "0 0 0 6px rgba(239,68,68,.15)"
                    }}
                  />
                  <span style={{ fontWeight: 700, color: verified ? "#22c55e" : "#ef4444" }}>
                    {message}
                  </span>
                </div>
              </div>
            )}

            {details && (
              <div className="card" style={{ fontSize: 13 }}>
                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    flexWrap: "wrap",
                    marginBottom: 8,
                  }}
                >
                  <Pill label="Face detected" ok={details.face_detected_live} />
                  <Pill label="ID photo detected" ok={details.face_detected_id} />
                  <Pill label="Faces match" ok={details.verified} />
                </div>
                {details.distance !== undefined && (
                  <p style={{ margin: 0 }} className="subtle">
                    Distance: <b>{details.distance?.toFixed(2)}</b> (Threshold: {details.threshold})
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
                    Tips appear here if something is missing (lighting, sharpness, position …)
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
          background: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.14)",
          borderRadius: 10,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
        }}
      >
        {dataUrl ? (
          <img src={dataUrl} alt={title} style={{ width: "100%" }} />
        ) : (
          <span style={{ color: "var(--muted)" }}>no image yet</span>
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
        border: ok ? "1px solid #bbf7d0" : "1px solid #fecaca",
        fontSize: 12.5,
        color: ok ? "#166534" : "#991b1b",
        fontWeight: 600,
        boxShadow: ok
          ? "0 4px 12px rgba(34,197,94,.18)"
          : "0 4px 12px rgba(239,68,68,.18)",
      }}
    >
      {label}: {ok ? "✅" : "❌"}
    </span>
  );
}

export default JoinExam;

