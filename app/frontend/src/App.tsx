import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Inbox from "./pages/Inbox";
import Working from "./pages/Working";
import CreationDetail from "./pages/working/CreationDetail";
import { SHELLS, ShellPage } from "./pages/Shells";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/inbox" replace />} />
        <Route path="inbox/*" element={<Inbox />} />
        <Route path="working" element={<Working />} />
        <Route path="working/:topic_id" element={<CreationDetail />} />
        {Object.entries(SHELLS).map(([path, spec]) => (
          <Route key={path} path={path} element={<ShellPage spec={spec} />} />
        ))}
        <Route path="*" element={<Navigate to="/inbox" replace />} />
      </Route>
    </Routes>
  );
}
