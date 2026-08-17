import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import ForgotPassword from "./pages/ForgotPassword.jsx";
import Login from "./pages/Login.jsx";
import Matches from "./pages/Matches.jsx";
import NextTraining from "./pages/NextTraining.jsx";
import Players from "./pages/Players.jsx";
import Register from "./pages/Register.jsx";
import ResetPassword from "./pages/ResetPassword.jsx";
import Rpe from "./pages/Rpe.jsx";
import Settings from "./pages/Settings.jsx";
import Wedstrijden from "./pages/Wedstrijden.jsx";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <NextTraining />
            </ProtectedRoute>
          }
        />
        <Route path="/next-training" element={<Navigate to="/" replace />} />
        <Route
          path="/wedstrijden"
          element={
            <ProtectedRoute>
              <Wedstrijden />
            </ProtectedRoute>
          }
        />
        <Route
          path="/players"
          element={
            <ProtectedRoute>
              <Players />
            </ProtectedRoute>
          }
        />
        <Route
          path="/matches"
          element={
            <ProtectedRoute>
              <Matches />
            </ProtectedRoute>
          }
        />
        <Route
          path="/rpe"
          element={
            <ProtectedRoute>
              <Rpe />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Settings />
            </ProtectedRoute>
          }
        />
      </Routes>
    </Layout>
  );
}
