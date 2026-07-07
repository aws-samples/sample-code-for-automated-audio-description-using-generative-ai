import { useState, useEffect } from "react";
import NavBar from "./components/NavBar";
import ViewerPage from "./components/ViewerPage";
import TriggerPage from "./components/TriggerPage";
import CostPage from "./components/CostPage";
import LoginPage from "./components/LoginPage";
import { getSession, signOut, loadAuthConfig } from "./auth";

function App() {
  const [activePage, setActivePage] = useState<"viewer" | "trigger" | "cost">(
    "trigger",
  );
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    async function checkAuth() {
      try {
        await loadAuthConfig();
        const session = await getSession();
        setIsAuthenticated(session !== null);
      } catch {
        setIsAuthenticated(false);
      } finally {
        setAuthLoading(false);
      }
    }
    checkAuth();
  }, []);

  const handleLoginSuccess = () => {
    setIsAuthenticated(true);
  };

  const handleSignOut = async () => {
    await signOut();
    setIsAuthenticated(false);
  };

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-[var(--on-surface-muted)]">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="flex flex-col min-h-screen font-[var(--font-body)]">
      <header className="px-6 py-3 bg-[var(--surface-container-low)] flex items-center justify-between">
        <h1 className="text-xl font-semibold font-[var(--font-display)] text-[var(--on-surface)]">
          DVI Dashboard
        </h1>
        <button
          onClick={handleSignOut}
          className="text-sm text-[var(--on-surface-muted)] hover:text-[var(--on-surface)] transition-colors"
        >
          Sign Out
        </button>
      </header>
      <NavBar activePage={activePage} onNavigate={setActivePage} />
      <div style={{ display: activePage === "viewer" ? "contents" : "none" }}>
        <ViewerPage />
      </div>
      <div style={{ display: activePage === "trigger" ? "contents" : "none" }}>
        <TriggerPage />
      </div>
      <div style={{ display: activePage === "cost" ? "contents" : "none" }}>
        <CostPage />
      </div>
    </div>
  );
}

export default App;
