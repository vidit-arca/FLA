import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import TaskView from './pages/TaskView';
import ComparisonPlatform from './pages/ComparisonPlatform';
import { LayoutDashboard, UploadCloud, Settings, User, FileDiff } from 'lucide-react';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-[#0B0F19] flex font-sans text-slate-200">
        {/* Sidebar */}
        <div className="w-72 bg-[#0F1523]/90 backdrop-blur-3xl border-r border-white/[0.05] flex flex-col z-20 shadow-2xl relative">
          
          {/* Brand Logo */}
          <div className="p-8 pb-6">
            <div className="flex items-center gap-3.5 mb-1">
              <img src="/akshyam_logo.png" alt="Akshyam Logo" className="w-10 h-10 object-contain rounded-xl shadow-lg shadow-black/20 bg-white p-1" />
              <div className="flex flex-col">
                <h1 className="text-2xl font-extrabold text-white tracking-tight leading-none">FLA AI</h1>
                <p className="text-[0.7rem] text-indigo-300/80 font-semibold uppercase tracking-wider mt-1">Extraction Platform</p>
              </div>
            </div>
          </div>
          
          {/* Navigation */}
          <nav className="flex-1 px-4 space-y-1.5 mt-2">
            <p className="px-4 text-[0.65rem] font-bold text-slate-500 uppercase tracking-wider mb-2">Main Menu</p>
            
            <NavLink 
              to="/" 
              className={({isActive}) => `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 font-medium text-sm ${isActive ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-inner' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'}`}
            >
              <LayoutDashboard className="w-5 h-5" />
              Dashboard
            </NavLink>
            
            <NavLink 
              to="/upload" 
              className={({isActive}) => `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 font-medium text-sm ${isActive ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-inner' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'}`}
            >
              <UploadCloud className="w-5 h-5" />
              New Extraction
            </NavLink>

            <NavLink 
              to="/compare" 
              className={({isActive}) => `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 font-medium text-sm ${isActive ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-inner' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'}`}
            >
              <FileDiff className="w-5 h-5" />
              Comparison Platform
            </NavLink>
          </nav>

          {/* Bottom Settings / Profile */}
          <div className="p-4 mt-auto">
            <div className="border-t border-white/5 pt-4 space-y-1.5">
              <button className="w-full flex items-center gap-3 px-4 py-3 text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-xl transition-all duration-200 font-medium text-sm border border-transparent text-left">
                <Settings className="w-5 h-5" />
                Settings
              </button>
              
              <div className="w-full flex items-center gap-3 px-4 py-3 mt-2 bg-black/20 rounded-xl border border-white/5 cursor-pointer hover:bg-black/30 transition-colors">
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-slate-600 to-slate-400 flex items-center justify-center text-white border border-slate-500">
                  <User className="w-4 h-4" />
                </div>
                <div className="flex flex-col">
                  <span className="text-sm font-semibold text-white">Admin User</span>
                  <span className="text-xs text-slate-500">admin@fla-ai.com</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <main className="flex-1 overflow-auto relative">
          {/* Decorative background elements */}
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-600/20 blur-[100px] pointer-events-none" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/20 blur-[100px] pointer-events-none" />
          
          <div className="max-w-6xl mx-auto p-10 relative z-10 animate-fade-in">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/upload" element={<Upload />} />
              <Route path="/task/:taskId" element={<TaskView />} />
              <Route path="/compare" element={<ComparisonPlatform />} />
            </Routes>
          </div>
        </main>
      </div>
    </Router>
  );
}

export default App;
