import React, { useState, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { UploadCloud, Wand2, Loader2, Target, CheckCircle2 } from 'lucide-react';

// Initialize pdf.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export default function PdfCanvas({ onDocumentUpload, onRegionSelect, isExtractingRegion }) {
  const [file, setFile] = useState(null);
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.0);
  
  // 2-Step Mapping State
  // 'idle' | 'anchor' | 'value'
  const [mappingStep, setMappingStep] = useState('idle');
  const [anchorRectSaved, setAnchorRectSaved] = useState(null);
  
  // Drawing State
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectionRect, setSelectionRect] = useState(null);
  const containerRef = useRef(null);

  const onFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      if (onDocumentUpload) {
          onDocumentUpload(selectedFile);
      }
    }
  };

  const onDocumentLoadSuccess = ({ numPages }) => {
    setNumPages(numPages);
  };
  
  const getPageRect = () => {
      if (!containerRef.current) return null;
      // Find the actual rendered PDF page canvas wrapper for perfect coordinate mapping
      const pageEl = containerRef.current.querySelector('.react-pdf__Page');
      return pageEl ? pageEl.getBoundingClientRect() : containerRef.current.getBoundingClientRect();
  };

  const handleMouseDown = (e) => {
      if (mappingStep === 'idle') return;
      const rect = getPageRect();
      if (!rect) return;
      
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      setIsSelecting(true);
      setSelectionRect({ startX: x, startY: y, currentX: x, currentY: y });
  };
  
  const handleMouseMove = (e) => {
      if (!isSelecting || mappingStep === 'idle') return;
      const rect = getPageRect();
      if (!rect) return;
      
      const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
      const y = Math.max(0, Math.min(e.clientY - rect.top, rect.height));
      setSelectionRect(prev => ({ ...prev, currentX: x, currentY: y }));
  };
  
  const handleMouseUp = () => {
      if (!isSelecting || mappingStep === 'idle' || !selectionRect) {
          setIsSelecting(false);
          return;
      }
      setIsSelecting(false);
      
      const rect = getPageRect();
      if (!rect) return;
      
      const left = Math.min(selectionRect.startX, selectionRect.currentX);
      const top = Math.min(selectionRect.startY, selectionRect.currentY);
      const width = Math.abs(selectionRect.startX - selectionRect.currentX);
      const height = Math.abs(selectionRect.startY - selectionRect.currentY);
      
      // Only extract if the box is reasonably sized (prevent accidental clicks)
      if (width > 10 && height > 10) {
          const normalizedBox = {
              x: left / rect.width,
              y: top / rect.height,
              w: width / rect.width,
              h: height / rect.height
          };
          
          if (mappingStep === 'anchor') {
              setAnchorRectSaved(normalizedBox);
              setMappingStep('value');
          } else if (mappingStep === 'value' && onRegionSelect) {
              const valueRect = normalizedBox;
              onRegionSelect(pageNumber, anchorRectSaved, valueRect);
              
              // Reset
              setMappingStep('idle');
              setAnchorRectSaved(null);
          }
      }
      setSelectionRect(null);
  };

  const handleCancelMapping = () => {
      setMappingStep('idle');
      setAnchorRectSaved(null);
      setSelectionRect(null);
  };

  if (!file) {
      return (
        <div className="w-full h-full bg-slate-100 dark:bg-slate-800/50 rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-700 flex items-center justify-center">
            <div className="text-center p-8 max-w-sm">
                <div className="w-16 h-16 bg-indigo-100 dark:bg-indigo-500/20 text-indigo-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <UploadCloud className="w-8 h-8" />
                </div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">Upload a Document</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">Upload a PDF to build deterministic spatial rules.</p>
                <label className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg cursor-pointer shadow-sm shadow-indigo-600/20 transition-all font-medium text-sm inline-block">
                    Browse Files
                    <input type="file" className="hidden" accept=".pdf" onChange={onFileChange} />
                </label>
            </div>
        </div>
      );
  }

  return (
    <div className="relative w-full h-full flex flex-col bg-slate-200/50 dark:bg-[#0B0F19] rounded-xl overflow-hidden border border-slate-200 dark:border-white/5">
      {/* Top Toolbar */}
      <div className="h-12 border-b border-slate-200 dark:border-white/10 bg-white dark:bg-[#1A2234] flex items-center px-4 justify-between shrink-0">
        <div className="flex items-center gap-4">
            <span className="text-xs font-semibold text-slate-500">Page {pageNumber} of {numPages || '?'}</span>
            <div className="flex gap-2">
                <button onClick={() => setPageNumber(p => Math.max(1, p - 1))} disabled={pageNumber <= 1 || mappingStep !== 'idle'} className="px-2 py-1 text-xs bg-slate-100 dark:bg-white/5 rounded hover:bg-slate-200 disabled:opacity-50 text-slate-700 dark:text-slate-300">Prev</button>
                <button onClick={() => setPageNumber(p => Math.min(numPages || 1, p + 1))} disabled={pageNumber >= (numPages || 1) || mappingStep !== 'idle'} className="px-2 py-1 text-xs bg-slate-100 dark:bg-white/5 rounded hover:bg-slate-200 disabled:opacity-50 text-slate-700 dark:text-slate-300">Next</button>
            </div>
            
            <div className="w-px h-4 bg-slate-300 dark:bg-slate-600 mx-2" />
            
            {mappingStep === 'idle' ? (
                <button 
                    onClick={() => {
                        setMappingStep('anchor');
                        setSelectionRect(null);
                        setAnchorRectSaved(null);
                    }}
                    disabled={isExtractingRegion}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-colors shadow-sm bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/30 hover:bg-indigo-100 dark:hover:bg-indigo-500/30`}
                >
                    {isExtractingRegion ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Target className="w-3.5 h-3.5" />}
                    {isExtractingRegion ? 'Extracting Rule...' : 'Start Spatial Mapping'}
                </button>
            ) : (
                <button 
                    onClick={handleCancelMapping}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-colors bg-rose-50 dark:bg-rose-500/20 text-rose-600 dark:text-rose-400 border border-rose-200 hover:bg-rose-100"
                >
                    Cancel Mapping
                </button>
            )}
        </div>
        
        <div className="flex items-center gap-4">
             <div className="flex gap-2 items-center text-xs">
                <span className="text-slate-500 font-medium">Zoom:</span>
                <button onClick={() => setScale(s => Math.max(0.5, s - 0.2))} className="w-6 h-6 rounded bg-slate-100 dark:bg-white/5 hover:bg-slate-200 flex items-center justify-center font-bold text-slate-700 dark:text-slate-300">-</button>
                <span className="w-10 text-center font-medium text-slate-700 dark:text-slate-300">{Math.round(scale * 100)}%</span>
                <button onClick={() => setScale(s => Math.min(3.0, s + 0.2))} className="w-6 h-6 rounded bg-slate-100 dark:bg-white/5 hover:bg-slate-200 flex items-center justify-center font-bold text-slate-700 dark:text-slate-300">+</button>
             </div>
             <button onClick={() => { setFile(null); if(onDocumentUpload) onDocumentUpload(null); }} className="text-xs text-red-500 font-medium hover:text-red-700">Remove PDF</button>
        </div>
      </div>

      {/* 2-Step Mapping Banner */}
      {mappingStep !== 'idle' && (
          <div className={`w-full py-2 px-4 flex items-center justify-center gap-2 text-sm font-bold shadow-md z-10 transition-colors ${
              mappingStep === 'anchor' ? 'bg-indigo-600 text-white' : 'bg-emerald-600 text-white'
          }`}>
              {mappingStep === 'anchor' ? (
                  <>
                    <Target className="w-4 h-4" /> Step 1: Draw a box around the Anchor Text (The Key)
                  </>
              ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" /> Step 2: Draw a box around the Target Value
                  </>
              )}
          </div>
      )}

      {/* PDF Canvas Area */}
      <div 
        className="flex-1 overflow-auto bg-slate-300/30 dark:bg-[#0B0F19] flex justify-center p-8"
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
          <div 
            ref={containerRef}
            className={`relative shadow-xl shadow-black/10 bg-white select-none ${mappingStep !== 'idle' ? 'cursor-crosshair' : 'cursor-default'}`} 
            style={{ width: "fit-content", height: "fit-content" }}
            onMouseDown={handleMouseDown}
          >
              <Document
                file={file}
                onLoadSuccess={onDocumentLoadSuccess}
                className={mappingStep !== 'idle' ? "pointer-events-none" : "select-text"}
              >
                <Page 
                    pageNumber={pageNumber} 
                    scale={scale} 
                    renderTextLayer={mappingStep === 'idle'}
                    renderAnnotationLayer={mappingStep === 'idle'}
                />
              </Document>
              
              {/* Saved Anchor Box Overlay */}
              {anchorRectSaved && (
                  <div 
                      className="absolute border-2 border-indigo-500 bg-indigo-500/20 flex items-center justify-center overflow-visible"
                      style={{
                          left: `${anchorRectSaved.x * 100}%`,
                          top: `${anchorRectSaved.y * 100}%`,
                          width: `${anchorRectSaved.w * 100}%`,
                          height: `${anchorRectSaved.h * 100}%`,
                          pointerEvents: 'none'
                      }}
                  >
                      <span className="absolute -top-6 left-0 bg-indigo-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded shadow">Anchor</span>
                  </div>
              )}

              {/* Active Selection Box Overlay */}
              {mappingStep !== 'idle' && selectionRect && (
                  <div 
                      className={`absolute border-2 ${mappingStep === 'anchor' ? 'border-indigo-500 bg-indigo-500/20' : 'border-emerald-500 bg-emerald-500/20'} backdrop-invert-[0.1]`}
                      style={{
                          left: Math.min(selectionRect.startX, selectionRect.currentX),
                          top: Math.min(selectionRect.startY, selectionRect.currentY),
                          width: Math.abs(selectionRect.startX - selectionRect.currentX),
                          height: Math.abs(selectionRect.startY - selectionRect.currentY),
                          pointerEvents: 'none'
                      }}
                  />
              )}
          </div>
      </div>
    </div>
  );
}
