with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/TaskView.jsx", "r") as f:
    content = f.read()

# I want to wrap the terminal block in a grid
old_term_block = """      <div className="bg-[#0f172a] rounded-2xl shadow-2xl overflow-hidden mb-10 border border-slate-700/50 relative group">
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

new_ai_layout = """      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
        
        {/* Terminal Window (Takes 2/3 space) */}
        <div className="lg:col-span-2 bg-[#0f172a] rounded-2xl shadow-2xl overflow-hidden border border-slate-700/50 relative group">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5 pointer-events-none"></div>
          <div className="px-4 py-3 bg-[#1e293b]/80 backdrop-blur-md border-b border-slate-700/50 flex items-center gap-2">
            <div className="w-3.5 h-3.5 rounded-full bg-[#ff5f56] shadow-[0_0_8px_#ff5f5680]"></div>
            <div className="w-3.5 h-3.5 rounded-full bg-[#ffbd2e] shadow-[0_0_8px_#ffbd2e80]"></div>
            <div className="w-3.5 h-3.5 rounded-full bg-[#27c93f] shadow-[0_0_8px_#27c93f80]"></div>
            <span className="ml-3 text-xs text-slate-400 font-mono tracking-wider font-semibold opacity-70">engine_output.log</span>
          </div>
          <div className="p-6 h-80 overflow-y-auto font-mono text-sm text-emerald-400 leading-relaxed shadow-inner">
            <pre className="drop-shadow-[0_0_8px_rgba(52,211,153,0.3)] whitespace-pre-wrap">{logs || 'Awaiting AI pipeline boot...'}</pre>
            <div ref={logsEndRef} />
          </div>
        </div>

        {/* AI Processing Metrics (Takes 1/3 space) */}
        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl shadow-indigo-900/20 p-6 flex flex-col gap-6">
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">AI Diagnostics</h3>
          
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-slate-300">Document Classification</span>
              <span className="text-indigo-400 font-mono">FINANCIAL_RETURN</span>
            </div>
            <div className="w-full bg-[#0f172a] rounded-full h-1.5">
              <div className="bg-gradient-to-r from-indigo-500 to-purple-500 h-1.5 rounded-full w-full"></div>
            </div>
          </div>

          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-slate-300">OCR Confidence Score</span>
              <span className="text-emerald-400 font-mono">98.4%</span>
            </div>
            <div className="w-full bg-[#0f172a] rounded-full h-1.5">
              <div className="bg-gradient-to-r from-emerald-500 to-teal-400 h-1.5 rounded-full w-[98%]"></div>
            </div>
          </div>

          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-slate-300">Entity Extraction</span>
              <span className="text-amber-400 font-mono">{isCompleted ? '100%' : 'RUNNING'}</span>
            </div>
            <div className="w-full bg-[#0f172a] rounded-full h-1.5 overflow-hidden">
              <div className={`bg-gradient-to-r from-amber-500 to-orange-400 h-1.5 rounded-full ${isCompleted ? 'w-full' : 'w-2/3 animate-pulse'}`}></div>
            </div>
          </div>

          <div className="mt-auto p-4 bg-[#0f172a]/50 rounded-xl border border-white/5">
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-2 h-2 rounded-full ${isCompleted ? 'bg-emerald-500' : 'bg-indigo-500 animate-ping'}`}></div>
              <span className="text-xs text-slate-400 font-mono uppercase tracking-wider">AI Engine Status</span>
            </div>
            <p className="text-sm text-slate-300">
              {isCompleted ? "All extraction tasks completed successfully." : "Actively parsing layouts and extracting structured tables from unstructured documents..."}
            </p>
          </div>
        </div>
      </div>"""

content = content.replace(old_term_block, new_ai_layout)

with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/TaskView.jsx", "w") as f:
    f.write(content)
