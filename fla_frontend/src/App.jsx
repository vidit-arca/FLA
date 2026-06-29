import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import GenericHub from './pages/GenericHub';
import GenericUpload from './pages/GenericUpload';
import GenericTaskView from './pages/GenericTaskView';
import { MODULES_SCHEMA } from './config/modulesSchema';
import ComparisonPlatform from './pages/ComparisonPlatform';
import ReviewPage from './pages/ReviewPage';
import TaskReviewView from './pages/TaskReviewView';
import { LayoutDashboard, FileText, Settings, User, FileDiff, ClipboardCheck, ShieldAlert } from 'lucide-react';

const ICON_MAP = {
  FileText: FileText,
  ShieldAlert: ShieldAlert,
};

function App() {
  const isReviewMode = window.location.pathname.startsWith('/review/') && window.location.pathname !== '/review';

  if (isReviewMode) {
    return (
      <Router>
        <Routes>
          <Route path="/review/:taskId" element={<TaskReviewView />} />
        </Routes>
      </Router>
    );
  }

  return (
    <Router>
      <div className="min-h-screen bg-[#0B0F19] flex font-sans text-slate-200">
        {/* Sidebar */}
        <div className="w-72 h-screen sticky top-0 bg-[#0F1523]/90 backdrop-blur-3xl border-r border-white/[0.05] flex flex-col z-20 shadow-2xl shrink-0">

          {/* Brand Logo */}
          <div className="p-6 pb-4">
            <div className="flex items-center gap-3 mb-1">
              <img src="/akshayam_logo.png" alt="Akshayam Logo" className="w-9 h-9 object-contain rounded-xl shadow-lg shadow-black/20 bg-white p-1" />
              <div className="flex flex-col">
                <h1 className="text-lg font-extrabold text-white tracking-tight leading-none">AKSHAYAM</h1>
                <p className="text-[0.6rem] text-indigo-300/80 font-semibold uppercase tracking-wider mt-1">Extraction Platform</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-4 space-y-1 mt-1 overflow-y-auto hide-scrollbar">
            <div className="h-px bg-white/5 mb-4 mx-3" />
            <p className="px-3 text-[0.65rem] font-bold text-slate-500 uppercase tracking-wider mb-2">Main Menu</p>

            <NavLink
              to="/"
              end
              className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 font-medium text-sm ${isActive ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-inner' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'}`}
            >
              <LayoutDashboard className="w-4 h-4" />
              Platform Overview
            </NavLink>

            <NavLink
              to="/compare"
              className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 font-medium text-sm ${isActive ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-inner' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'}`}
            >
              <FileDiff className="w-4 h-4" />
              Comparison Manager
            </NavLink>

            <NavLink
              to="/review"
              className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 font-medium text-sm ${isActive ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-inner' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'}`}
            >
              <ClipboardCheck className="w-4 h-4" />
              Human Review
            </NavLink>

            <div className="h-px bg-white/5 my-4 mx-3" />
            <p className="px-3 text-[0.65rem] font-bold text-slate-500 uppercase tracking-wider mb-2">Installed Modules</p>

            {Object.values(MODULES_SCHEMA).map(mod => {
              const Icon = ICON_MAP[mod.icon] || FileText;
              return (
                <NavLink
                  key={mod.id}
                  to={`/m/${mod.id}`}
                  className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 font-medium text-sm ${isActive ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-inner' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'}`}
                >
                  <Icon className="w-4 h-4" />
                  {mod.name}
                </NavLink>
              );
            })}
            
            <div className="h-px bg-white/5 my-4 mx-3" />
            <p className="px-3 text-[0.65rem] font-bold text-slate-500 uppercase tracking-wider mb-2">System</p>

            <button className="w-full flex items-center gap-3 px-3 py-2.5 text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-xl transition-all duration-200 font-medium text-sm border border-transparent text-left">
              <Settings className="w-4 h-4" />
              Settings
            </button>
          </nav>

          {/* Bottom Settings / Profile */}
          <div className="p-4 mt-auto shrink-0">
            <div className="border-t border-white/5 pt-4 space-y-3">
              <div className="w-full flex items-center gap-3 px-3 py-2 bg-black/20 rounded-xl border border-white/5 cursor-pointer hover:bg-black/30 transition-colors">
                <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-slate-600 to-slate-400 flex items-center justify-center text-white border border-slate-500 shrink-0">
                  <User className="w-3.5 h-3.5" />
                </div>
                <div className="flex flex-col overflow-hidden">
                  <span className="text-[13px] font-semibold text-white truncate">Admin User</span>
                  <span className="text-[11px] text-slate-500 truncate">admin@akshayam.com</span>
                </div>
              </div>

              {/* Powered By Signature */}
              <div className="pt-1 pb-1 flex items-center justify-center">
                <p className="text-[9px] font-medium text-slate-500 tracking-widest uppercase flex items-center gap-1.5 opacity-80 hover:opacity-100 transition-opacity cursor-default">
                  Powered by <span className="text-indigo-400 font-bold bg-indigo-400/10 px-1.5 py-0.5 rounded border border-indigo-400/20">ARCA AI</span>
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <main className="flex-1 overflow-x-hidden overflow-y-auto relative">
          {/* Decorative background elements */}
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-600/20 blur-[100px] pointer-events-none" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/20 blur-[100px] pointer-events-none" />

          <div className="max-w-6xl mx-auto p-10 relative z-10 animate-fade-in">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/review" element={<ReviewPage />} />
              <Route path="/compare" element={<ComparisonPlatform />} />
              <Route path="/m/:moduleId" element={<GenericHub />} />
              <Route path="/m/:moduleId/upload" element={<GenericUpload />} />
              <Route path="/m/:moduleId/task/:taskId" element={<GenericTaskView />} />
            </Routes>
          </div>
        </main>
      </div>
    </Router>
  );
}

export default App;
