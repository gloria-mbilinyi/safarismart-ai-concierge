import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { BookingPage } from "./pages/BookingPage";
import { DestinationsPage } from "./pages/DestinationsPage";
import { HomePage } from "./pages/HomePage";
import { OperatorDashboardPage } from "./pages/OperatorDashboardPage";
import { OperatorLoginPage } from "./pages/OperatorLoginPage";
import { PlannerPage } from "./pages/PlannerPage";

export function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/destinations" element={<DestinationsPage />} />
        <Route path="/planner" element={<PlannerPage />} />
        <Route path="/booking" element={<BookingPage />} />
        <Route path="/operator/login" element={<OperatorLoginPage />} />
        <Route path="/operator" element={<OperatorDashboardPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
