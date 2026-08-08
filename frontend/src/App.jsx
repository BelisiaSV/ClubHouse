import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar.jsx";
import Compensation from "./pages/Compensation.jsx";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-950">
      <Navbar />
      <main className="p-6">
        <Routes>
          <Route path="/" element={<Compensation />} />
        </Routes>
      </main>
    </div>
  );
}
