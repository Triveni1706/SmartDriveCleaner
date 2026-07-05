import { useEffect, useState, type ReactElement } from "react";
import { HashRouter, useLocation } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Overview from "./pages/Overview";
import FileExplorer from "./pages/FileExplorer";
import Duplicates from "./pages/Duplicates";
import PdfManager from "./pages/PdfManager";
import ImageManager from "./pages/ImageManager";
import Archives from "./pages/Archives";
import Recommendations from "./pages/Recommendations";
import Monitor from "./pages/Monitor";
import SmartSearch from "./pages/SmartSearch";
import Assistant from "./pages/Assistant";
import Trash from "./pages/Trash";
import Collections from "./pages/Collections";
import Organizer from "./pages/Organizer";

// Every page keeps its own in-progress state locally (scan stage/progress,
// checkbox selections, etc). react-router's <Routes> unmounts a page the
// instant you navigate away, which wipes that state — a scan in progress on
// Overview resets to idle, and selections made on Duplicates/FileExplorer/
// ImageManager vanish, the moment you switch tabs.
//
// Fix: instead of swapping pages in/out with <Routes>, keep every page you've
// visited mounted for the lifetime of the app and just hide the inactive
// ones with CSS. Their state (and any in-flight polling loop, like the scan
// job poller) stays alive untouched while you're on another tab.
const ROUTES: { path: string; element: ReactElement }[] = [
  { path: "/", element: <Overview /> },
  { path: "/files", element: <FileExplorer /> },
  { path: "/organize", element: <Organizer /> },
  { path: "/duplicates", element: <Duplicates /> },
  { path: "/pdfs", element: <PdfManager /> },
  { path: "/images", element: <ImageManager /> },
  { path: "/archives", element: <Archives /> },
  { path: "/recommendations", element: <Recommendations /> },
  { path: "/monitor", element: <Monitor /> },
  { path: "/search", element: <SmartSearch /> },
  { path: "/assistant", element: <Assistant /> },
  { path: "/trash", element: <Trash /> },
  { path: "/collections", element: <Collections /> },
];

function KeepAliveRoutes() {
  const location = useLocation();
  // Only mount a page once it's actually been visited (so we don't fire off
  // 12 pages' worth of initial API calls on first load); after that, keep it
  // mounted forever so its state survives switching away and back.
  const [visited, setVisited] = useState<Set<string>>(new Set([location.pathname]));

  useEffect(() => {
    setVisited((prev) => (prev.has(location.pathname) ? prev : new Set(prev).add(location.pathname)));
  }, [location.pathname]);

  return (
    <>
      {ROUTES.filter((r) => visited.has(r.path)).map((r) => (
        <div key={r.path} style={{ display: location.pathname === r.path ? "block" : "none" }}>
          {r.element}
        </div>
      ))}
    </>
  );
}

export default function App() {
  return (
    <HashRouter>
      <div className="hero-gradient-bg flex h-screen">
        <Sidebar />
        <main className="relative flex-1 overflow-y-auto px-8 py-6">
          <KeepAliveRoutes />
        </main>
      </div>
    </HashRouter>
  );
}
