with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/TaskView.jsx", "r") as f:
    content = f.read()

old_term = """<div className="bg-slate-900 rounded-xl shadow-inner overflow-hidden mb-8 border border-slate-800">
        <div className="px-4 py-2 bg-slate-800 border-b border-slate-700 flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500"></div>
          <div className="w-3 h-3 rounded-full bg-amber-500"></div>
          <div className="w-3 h-3 rounded-full bg-green-500"></div>
          <span className="ml-2 text-xs text-slate-400 font-mono">system_logs</span>
        </div>
        <div className="p-4 max-h-96 overflow-y-auto font-mono text-sm text-green-400 leading-relaxed">
          <pre>{logs || 'Awaiting logs...'}</pre>
          <div ref={logsEndRef} />
        </div>
      </div>"""

new_term = """<div className="bg-[#0f172a] rounded-2xl shadow-2xl overflow-hidden mb-10 border border-slate-700/50 relative group">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5 pointer-events-none"></div>
        <div className="px-4 py-3 bg-[#1e293b]/80 backdrop-blur-md border-b border-slate-700/50 flex items-center gap-2">
          <div className="w-3.5 h-3.5 rounded-full bg-[#ff5f56] shadow-[0_0_8px_#ff5f5680]"></div>
          <div className="w-3.5 h-3.5 rounded-full bg-[#ffbd2e] shadow-[0_0_8px_#ffbd2e80]"></div>
          <div className="w-3.5 h-3.5 rounded-full bg-[#27c93f] shadow-[0_0_8px_#27c93f80]"></div>
          <span className="ml-3 text-xs text-slate-400 font-mono tracking-wider font-semibold opacity-70">engine_output.log</span>
        </div>
        <div className="p-6 max-h-96 overflow-y-auto font-mono text-sm text-emerald-400 leading-relaxed shadow-inner">
          <pre className="drop-shadow-[0_0_8px_rgba(52,211,153,0.3)]">{logs || 'Awaiting AI pipeline boot...'}</pre>
          <div ref={logsEndRef} />
        </div>
      </div>"""
content = content.replace(old_term, new_term)

old_succ = """      {isCompleted && (
        <div className="bg-white rounded-xl border border-green-200 p-8 shadow-sm flex items-center justify-between mb-8">
          <div className="flex items-center gap-6">
            <CheckCircle className="w-16 h-16 text-green-500" />
            <div>
              <h2 className="text-2xl font-bold text-slate-900 mb-2">Excel Generated Successfully!</h2>
              <p className="text-slate-500">The FLA Return has been fully populated and validated.</p>
            </div>
          </div>
          <button 
            onClick={handleDownload}
            className="inline-flex items-center gap-3 bg-green-600 hover:bg-green-700 text-white px-8 py-4 rounded-xl font-bold text-lg shadow-lg hover:shadow-xl transition-all hover:-translate-y-0.5"
          >
            <FileSpreadsheet className="w-6 h-6" />
            Download Excel
          </button>
        </div>
      )}"""

new_succ = """      {isCompleted && (
        <div className="relative overflow-hidden bg-gradient-to-r from-emerald-50 to-teal-50 rounded-2xl border border-emerald-200 p-8 shadow-xl shadow-emerald-500/10 flex items-center justify-between mb-10 animate-fade-in">
          <div className="absolute -right-20 -top-20 w-64 h-64 bg-emerald-400/20 rounded-full blur-3xl"></div>
          <div className="flex items-center gap-6 relative z-10">
            <div className="bg-white p-3 rounded-full shadow-md">
              <CheckCircle className="w-12 h-12 text-emerald-500" />
            </div>
            <div>
              <h2 className="text-3xl font-extrabold text-slate-900 mb-2 tracking-tight">Excel Generated Successfully!</h2>
              <p className="text-slate-600 font-medium">The FLA Return has been fully populated and validated by the AI.</p>
            </div>
          </div>
          <button 
            onClick={handleDownload}
            className="relative z-10 inline-flex items-center gap-3 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white px-8 py-4 rounded-xl font-bold text-lg shadow-lg shadow-emerald-500/30 hover:shadow-xl hover:shadow-emerald-500/40 hover:-translate-y-1 transition-all duration-300"
          >
            <FileSpreadsheet className="w-6 h-6" />
            Download Excel
          </button>
        </div>
      )}"""
content = content.replace(old_succ, new_succ)

with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/TaskView.jsx", "w") as f:
    f.write(content)
