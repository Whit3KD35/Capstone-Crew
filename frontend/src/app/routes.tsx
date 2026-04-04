import { createBrowserRouter } from "react-router-dom";
import Layout from "./layout";
import Login from "../pages/Login";
import PatientLogin from "../pages/PatientLogin";
import PatientChoice from "../pages/PatientChoice";
import BasicInfo from "../pages/BasicInfo";
import PatientInfo from "../pages/PatientInfo";
import Simulation from "../pages/Simulation";
import PatientSimulations from "../pages/PatientSimulations";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Login /> },
      { path: "login", element: <Login /> },
      { path: "patient-login", element: <PatientLogin /> },
      { path: "choose", element: <PatientChoice /> },
      { path: "basic", element: <BasicInfo /> },
      { path: "info", element: <PatientInfo /> },
      { path: "simulate", element: <Simulation /> },
      { path: "patient/simulations", element: <PatientSimulations /> },
    ],
  },
]);
