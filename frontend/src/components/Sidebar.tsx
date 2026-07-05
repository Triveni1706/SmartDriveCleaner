import { useState } from "react";
import { NavLink } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutGrid,
  Copy,
  FolderTree,
  HardDrive,
  FileText,
  Image,
  Archive,
  Sparkles,
  Eye,
  Search,
  Bot,
  Trash2,
  FolderKanban,
  ChevronsLeft,
  ChevronsRight,
  FolderCog,
} from "lucide-react";

const links = [
  { to: "/", label: "Overview", icon: LayoutGrid, end: true },
  { to: "/files", label: "File Explorer", icon: FolderTree },
  { to: "/organize", label: "Organize Files", icon: FolderCog },
  { to: "/duplicates", label: "Duplicates", icon: Copy },
  { to: "/pdfs", label: "PDF Manager", icon: FileText },
  { to: "/images", label: "Image Manager", icon: Image },
  { to: "/archives", label: "Archives", icon: Archive },
  { to: "/collections", label: "Collections", icon: FolderKanban },
  { to: "/recommendations", label: "Recommendations", icon: Sparkles },
  { to: "/trash", label: "Recovery Center", icon: Trash2 },
  { to: "/monitor", label: "Monitor", icon: Eye },
  { to: "/search", label: "Smart Search", icon: Search },
  { to: "/assistant", label: "Assistant", icon: Bot },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <motion.aside
      animate={{ width: collapsed ? 76 : 232 }}
      transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
      className="relative flex flex-col shrink-0 m-3 mr-0 rounded-2xl overflow-hidden"
      style={{
        background: "var(--panel)",
        border: "1px solid var(--panel-border)",
        backdropFilter: "var(--blur-glass)",
        WebkitBackdropFilter: "var(--blur-glass)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      {/* Brand */}
      <div className={`flex items-center gap-2.5 px-4 pt-5 pb-6 ${collapsed ? "justify-center px-0" : ""}`}>
        <div
          className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-glow-purple)" }}
        >
          <HardDrive size={16} color="#fff" strokeWidth={2} />
        </div>
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.span
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              transition={{ duration: 0.15 }}
              className="heading font-bold tracking-tight text-[15px] whitespace-nowrap overflow-hidden"
            >
              Drive Cleaner
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1 px-2.5 flex-1 overflow-y-auto">
        {links.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-xl text-[13.5px] font-medium transition-colors duration-150 ${
                collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2.5"
              } ${isActive ? "text-[var(--text)]" : "text-[var(--text-dim)] hover:text-[var(--text)]"}`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active"
                    transition={{ type: "spring", stiffness: 400, damping: 32 }}
                    className="absolute inset-0 rounded-xl"
                    style={{
                      background: "linear-gradient(135deg, rgba(124,58,237,0.22), rgba(168,85,247,0.10))",
                      border: "1px solid rgba(168,85,247,0.28)",
                    }}
                  />
                )}
                {isActive && !collapsed && (
                  <span
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 rounded-full"
                    style={{ background: "var(--gradient-brand)" }}
                  />
                )}
                <Icon size={17} strokeWidth={1.9} className="relative shrink-0" />
                <AnimatePresence initial={false}>
                  {!collapsed && (
                    <motion.span
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      transition={{ duration: 0.12 }}
                      className="relative whitespace-nowrap overflow-hidden"
                    >
                      {label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer / collapse toggle */}
      <div className="px-2.5 pb-3 pt-2 border-t" style={{ borderColor: "var(--panel-border)" }}>
        <button
          onClick={() => setCollapsed((c) => !c)}
          className={`flex items-center gap-2 w-full rounded-xl px-3 py-2 text-[12px] transition-colors hover:text-[var(--text)] ${
            collapsed ? "justify-center px-0" : ""
          }`}
          style={{ color: "var(--text-dim)" }}
        >
          {collapsed ? <ChevronsRight size={15} /> : <ChevronsLeft size={15} />}
          {!collapsed && <span>Collapse</span>}
        </button>
        {!collapsed && (
          <div className="mono text-[10.5px] mt-2 px-3" style={{ color: "var(--text-faint)" }}>
            v0.2.0 · local scan
          </div>
        )}
      </div>
    </motion.aside>
  );
}
