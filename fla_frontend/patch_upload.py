with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/Upload.jsx", "r") as f:
    content = f.read()

old_header = """<h1 className="text-3xl font-bold text-slate-900 mb-8">New Extraction</h1>"""
new_header = """<h1 className="text-4xl font-extrabold text-slate-900 mb-8 tracking-tight drop-shadow-sm">New Extraction</h1>"""
content = content.replace(old_header, new_header)

old_card = """<div className="bg-white rounded-xl border border-slate-200 p-8 shadow-sm">"""
new_card = """<div className="bg-white/80 backdrop-blur-md rounded-2xl border border-white/50 p-10 shadow-xl shadow-slate-200/50">"""
content = content.replace(old_card, new_card)

old_input = """className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-all\""""
new_input = """className="w-full px-5 py-3 bg-white/50 border border-slate-200 rounded-xl focus:ring-4 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white outline-none transition-all shadow-inner\""""
content = content.replace(old_input, new_input)

old_dropzone = """className="border-2 border-dashed border-slate-300 rounded-xl p-10 flex flex-col items-center justify-center bg-slate-50 hover:bg-slate-100 transition-colors cursor-pointer\""""
new_dropzone = """className="group relative border-2 border-dashed border-slate-300 rounded-2xl p-12 flex flex-col items-center justify-center bg-slate-50/50 hover:bg-primary-50 hover:border-primary-400 transition-all cursor-pointer overflow-hidden\""""
content = content.replace(old_dropzone, new_dropzone)

old_cloud = """<UploadCloud className="w-12 h-12 text-slate-400 mb-4" />"""
new_cloud = """<div className="absolute inset-0 bg-gradient-to-br from-primary-100/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
            <div className="bg-white p-4 rounded-full shadow-md mb-5 group-hover:scale-110 group-hover:shadow-lg transition-all z-10">
              <UploadCloud className="w-10 h-10 text-primary-500" />
            </div>"""
content = content.replace(old_cloud, new_cloud)

old_btn = """className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 disabled:bg-slate-300 text-white px-6 py-2.5 rounded-lg font-medium transition-colors\""""
new_btn = """className="flex items-center gap-2 bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600 disabled:from-slate-400 disabled:to-slate-400 text-white px-8 py-3.5 rounded-xl font-bold text-lg shadow-lg shadow-primary-500/30 hover:shadow-xl hover:shadow-primary-500/40 hover:-translate-y-0.5 transition-all\""""
content = content.replace(old_btn, new_btn)

with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/Upload.jsx", "w") as f:
    f.write(content)
