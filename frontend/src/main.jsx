import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { CityProvider } from "./context/CityContext";
import "./styles/index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <CityProvider>
        <App />
      </CityProvider>
    </BrowserRouter>
  </React.StrictMode>
);
