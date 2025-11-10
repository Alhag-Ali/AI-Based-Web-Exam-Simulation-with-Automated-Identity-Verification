import React from "react";
import Login from "./Login";
import JoinExam from "./JoinExam";

function App() {
  const token = localStorage.getItem("token");
  return <div>{token ? <JoinExam /> : <Login />}</div>;
}

export default App;

