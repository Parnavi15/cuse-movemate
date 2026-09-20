import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api";
import { Nav, Spinner, VerifyNudge } from "./components";
import { useAuth } from "./store";

import Bookings from "./pages/Bookings";
import Browse from "./pages/Browse";
import Home from "./pages/Home";
import ListingDetail from "./pages/ListingDetail";
import Login from "./pages/Login";
import MyItems from "./pages/MyItems";
import NewListing from "./pages/NewListing";
import Profile from "./pages/Profile";
import Register from "./pages/Register";
import SmartMatch from "./pages/SmartMatch";
import Wallet from "./pages/Wallet";

function Private({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function BuildTag() {
  const [version, setVersion] = useState("");
  useEffect(() => {
    api.config().then((c) => setVersion(c.version || "")).catch(() => {});
  }, []);
  if (!version) return null;
  return (
    <div className="small muted center" style={{ padding: "22px 0 8px" }}>
      Cuse-MoveMate {version}
    </div>
  );
}

export default function App() {
  return (
    <>
      <Nav />
      <main className="wrap page">
        <VerifyNudge />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/browse" element={<Browse />} />
          <Route path="/match" element={<SmartMatch />} />
          <Route path="/listing/:id" element={<ListingDetail />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/new" element={<Private><NewListing /></Private>} />
          <Route path="/edit/:id" element={<Private><NewListing /></Private>} />
          <Route path="/items" element={<Private><MyItems /></Private>} />
          <Route path="/requests" element={<Private><Bookings /></Private>} />
          <Route path="/wallet" element={<Private><Wallet /></Private>} />
          <Route path="/profile" element={<Private><Profile /></Private>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <BuildTag />
      </main>
    </>
  );
}
