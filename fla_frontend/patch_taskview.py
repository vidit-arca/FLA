with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/TaskView.jsx", "r") as f:
    content = f.read()

content = content.replace("import ReviewGrid from '../components/ReviewGrid';", "import ExcelViewer from '../components/ExcelViewer';")

old_review_block = """      {(isReview || isCompleted) && task.extracted_data && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden mb-8">
          <div className="px-6 py-5 border-b border-slate-200 flex justify-between items-center bg-slate-50">
            <div>
              <h2 className="text-lg font-bold text-slate-800">Data Review & Editing</h2>
              <p className="text-sm text-slate-500 mt-1">Review the extracted parameters. Edit any mistakes or fill in blanks to update the Excel return.</p>
            </div>
          </div>
          <ReviewGrid initialData={task.extracted_data} onExport={handleExport} />
        </div>
      )}"""

new_excel_block = """      {isCompleted && (
        <div className="mt-8 mb-8">
            <h2 className="text-xl font-bold text-slate-800 mb-4">Live Excel Editor</h2>
            <ExcelViewer taskId={taskId} />
        </div>
      )}"""

content = content.replace(old_review_block, new_excel_block)

with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/TaskView.jsx", "w") as f:
    f.write(content)
