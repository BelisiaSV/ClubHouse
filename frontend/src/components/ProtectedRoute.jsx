import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function ProtectedRoute({ children }) {
  const { token, loading } = useAuth();

  if (loading) return <p className="text-gray-400 p-6">Laden…</p>;
  if (!token) return <Navigate to="/login" replace />;
  return children;
}
