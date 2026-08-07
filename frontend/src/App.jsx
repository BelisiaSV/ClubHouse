import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar.jsx";
import Compensation from "./pages/Compensation.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Wellness from "./pages/Wellness.jsx";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-950">
      <Navbar />
      <main className="p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/compensation" element={<Compensation />} />
          <Route path="/wellness" element={<Wellness />} />
        </Routes>
      </main>
    </div>
  );
}
