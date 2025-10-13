import { createBrowserRouter } from "react-router-dom";
import Layout from "./layout";
import Login from "../pages/Login";
import PatientChoice from "../pages/PatientChoice";
import BasicInfo from "../pages/BasicInfo";
import PatientInfo from "../pages/PatientInfo";
import Simulation from "../pages/Simulation";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Login /> },
      { path: "choose", element: <PatientChoice /> },
      { path: "basic", element: <BasicInfo /> },
      { path: "info", element: <PatientInfo /> },
      { path: "simulate", element: <Simulation /> },
    ],
  },
]);
