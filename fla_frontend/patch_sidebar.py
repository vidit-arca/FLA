with open("/Users/apple/Desktop/FLA/fla_frontend/src/App.jsx", "r") as f:
    content = f.read()

# Replace imports
content = content.replace("import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';", "import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';")
content = content.replace("import { LayoutDashboard, UploadCloud } from 'lucide-react';", "import { LayoutDashboard, UploadCloud, Settings, User } from 'lucide-react';")

# Replace Sidebar block
old_sidebar = """        {/* Sidebar */}
        <div className="w-72 bg-[#131B2C]/60 backdrop-blur-2xl border-r border-white/5 flex flex-col shadow-[4px_0_24px_-12px_rgba(0,0,0,0.5)] z-10">
          <div className="p-8">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-primary-500/30 flex items-center justify-center text-white">
                <LayoutDashboard className="w-5 h-5" />
              </div>
              <h1 className="text-3xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-purple-400 tracking-tight">FLA AI</h1>
            </div>
            <p className="text-sm text-slate-400 font-medium ml-13">Extraction Platform</p>
          </div>
          
          <nav className="flex-1 px-4 space-y-2 mt-4">
            <Link to="/" className="flex items-center gap-3 px-4 py-3 text-slate-300 hover:text-indigo-400 hover:bg-indigo-500/10 rounded-xl transition-all duration-200 font-semibold group">
              <LayoutDashboard className="w-5 h-5 text-slate-400 group-hover:text-indigo-400 transition-colors" />
              Dashboard
            </Link>
            <Link to="/upload" className="flex items-center gap-3 px-4 py-3 text-slate-300 hover:text-indigo-400 hover:bg-indigo-500/10 rounded-xl transition-all duration-200 font-semibold group">
              <UploadCloud className="w-5 h-5 text-slate-400 group-hover:text-indigo-400 transition-colors" />
              New Extraction
            </Link>
          </nav>
        </div>"""

new_sidebar = """        {/* Sidebar */}
        <div className="w-72 bg-[#0F1523]/90 backdrop-blur-3xl border-r border-white/[0.05] flex flex-col z-20 shadow-2xl relative">
          
          {/* Brand Logo */}
          <div className="p-8 pb-6">
            <div className="flex items-center gap-3.5 mb-1">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 shadow-lg shadow-indigo-500/20 flex items-center justify-center border border-indigo-400/20">
                <LayoutDashboard className="w-5 h-5 text-white" />
              </div>
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
        </div>"""

content = content.replace(old_sidebar, new_sidebar)

with open("/Users/apple/Desktop/FLA/fla_frontend/src/App.jsx", "w") as f:
    f.write(content)
