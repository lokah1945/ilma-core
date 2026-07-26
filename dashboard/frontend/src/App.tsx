import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import OverviewPage from './pages/OverviewPage';
import ProvidersPage from './pages/ProvidersPage';
import ModelsPage from './pages/ModelsPage';
import ModelDetailPage from './pages/ModelDetailPage';
import BenchmarksPage from './pages/BenchmarksPage';
import PipelinesPage from './pages/PipelinesPage';
import UsagePage from './pages/UsagePage';
import RoutingPage from './pages/RoutingPage';
import WorkflowsPage from './pages/WorkflowsPage';
import EvidencePage from './pages/EvidencePage';
import CapabilitiesPage from './pages/CapabilitiesPage';
import SystemHealthPage from './pages/SystemHealthPage';

const navItems = [
  { path: '/', label: 'Overview' },
  { path: '/providers', label: 'Providers' },
  { path: '/models', label: 'Models' },
  { path: '/benchmarks', label: 'Benchmarks' },
  { path: '/pipelines', label: 'Pipelines' },
  { path: '/usage', label: 'Usage' },
  { path: '/routing', label: 'Routing' },
  { path: '/workflows', label: 'Workflows' },
  { path: '/evidence', label: 'Evidence' },
  { path: '/capabilities', label: 'Capabilities' },
  { path: '/health', label: 'Health' },
];

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-gray-950 text-gray-100">
        {/* Sidebar */}
        <nav className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
          <div className="p-4 border-b border-gray-800">
            <h1 className="text-lg font-bold text-white">ILMA Dashboard</h1>
            <p className="text-xs text-gray-500 mt-1">v1.0.0 — Observability</p>
          </div>
          <div className="flex-1 overflow-y-auto py-2">
            {navItems.map(item => (
              <NavLink key={item.path} to={item.path}>{item.label}</NavLink>
            ))}
          </div>
          <div className="p-3 border-t border-gray-800 text-xs text-gray-600">
            ILMA © 2026
          </div>
        </nav>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/providers" element={<ProvidersPage />} />
            <Route path="/models" element={<ModelsPage />} />
            <Route path="/models/:id" element={<ModelDetailPage />} />
            <Route path="/benchmarks" element={<BenchmarksPage />} />
            <Route path="/pipelines" element={<PipelinesPage />} />
            <Route path="/usage" element={<UsagePage />} />
            <Route path="/routing" element={<RoutingPage />} />
            <Route path="/workflows" element={<WorkflowsPage />} />
            <Route path="/evidence" element={<EvidencePage />} />
            <Route path="/capabilities" element={<CapabilitiesPage />} />
            <Route path="/health" element={<SystemHealthPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const location = useLocation();
  const isActive = location.pathname === to || (to !== '/' && location.pathname.startsWith(to));
  return (
    <Link
      to={to}
      className={`block px-4 py-2 text-sm ${
        isActive
          ? 'bg-blue-900 text-blue-300 border-r-2 border-blue-400'
          : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
      }`}
    >
      {children}
    </Link>
  );
}