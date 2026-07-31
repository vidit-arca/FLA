import React, { useState, useEffect } from 'react';
import { Loader2, FileText, CheckCircle, Info } from 'lucide-react';
import { idpClient } from '../api/idpClient';

export default function StructuredDocumentViewer({ pdfFile, onPairExtracted }) {
    const [structuredDoc, setStructuredDoc] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    
    // AI Cell Selection State
    const [pendingKeyNode, setPendingKeyNode] = useState(null);
    const [suggestedValueNode, setSuggestedValueNode] = useState(null);

    useEffect(() => {
        if (!pdfFile) {
            setStructuredDoc(null);
            return;
        }

        const fetchDoc = async () => {
            setIsLoading(true);
            setError(null);
            try {
                const doc = await idpClient.getStructuredDocument(pdfFile.name);
                setStructuredDoc(doc);
            } catch (err) {
                console.error("Failed to fetch structured document:", err);
                setError("Failed to load structured document. Ensure it has been processed.");
            } finally {
                setIsLoading(false);
            }
        };

        fetchDoc();
    }, [pdfFile]);

    // Keyboard Shortcuts
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                setPendingKeyNode(null);
                setSuggestedValueNode(null);
            } else if (e.key === 'Enter' && pendingKeyNode) {
                if (onPairExtracted) {
                    onPairExtracted(pdfFile, { 
                        key: pendingKeyNode.text, 
                        value: suggestedValueNode ? suggestedValueNode.text : "" 
                    });
                }
                setPendingKeyNode(null);
                setSuggestedValueNode(null);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [pendingKeyNode, suggestedValueNode, pdfFile, onPairExtracted]);

    const handleCellClick = (cellNode, rowNode) => {
        if (!pendingKeyNode) {
            // First click: Select Key
            setPendingKeyNode(cellNode);
            
            // AI Suggestion: Find numeric sibling
            if (rowNode && rowNode.children) {
                const cellIndex = rowNode.children.findIndex(c => c.id === cellNode.id);
                if (cellIndex !== -1) {
                    let suggestion = null;
                    for (let i = cellIndex + 1; i < rowNode.children.length; i++) {
                        const sibling = rowNode.children[i];
                        if (sibling.type === 'cell') {
                            const text = sibling.text || '';
                            const digitOnly = text.replace(/[^\d]/g, '');
                            // Ignore short numbers (like note references "14")
                            if (digitOnly.length >= 2) {
                                suggestion = sibling;
                                break;
                            }
                        }
                    }
                    setSuggestedValueNode(suggestion);
                }
            }
        } else if (pendingKeyNode.id === cellNode.id) {
            // Clicked same key again: Extract without value
            if (onPairExtracted) {
                onPairExtracted(pdfFile, { key: pendingKeyNode.text, value: "" });
            }
            setPendingKeyNode(null);
            setSuggestedValueNode(null);
        } else {
            // Second click on different cell: Explicit manual value selection
            if (onPairExtracted) {
                onPairExtracted(pdfFile, { key: pendingKeyNode.text, value: cellNode.text });
            }
            setPendingKeyNode(null);
            setSuggestedValueNode(null);
        }
    };

    const handleTextClick = (textNode, parentNode) => {
        const text = (textNode.text || '').trim();
        // Check if sentence/line has key-value delimiter like '2. PAN Number : AALCB0387K'
        if (text.includes(':') || text.includes(' - ')) {
            const delimiter = text.includes(':') ? ':' : ' - ';
            const parts = text.split(delimiter);
            let rawKey = parts[0].trim();
            let rawVal = parts.slice(1).join(delimiter).trim();
            // Clean up leading numbers like "2. PAN Number" -> "PAN Number"
            rawKey = rawKey.replace(/^[\d\.\-\s]+/, '').trim() || rawKey;
            
            if (onPairExtracted && rawKey && rawVal) {
                onPairExtracted(pdfFile, { key: rawKey, value: rawVal });
                setPendingKeyNode(null);
                setSuggestedValueNode(null);
                return;
            }
        }

        // Fallback to standard 2-click key-value selection
        handleCellClick(textNode, parentNode);
    };

    const renderNode = (node, parentNode = null) => {
        if (!node) return null;

        const isKey = pendingKeyNode?.id === node.id;
        const isSuggestion = suggestedValueNode?.id === node.id;

        switch (node.type) {
            case 'document':
            case 'section':
                return (
                    <div key={node.id} className="mb-6">
                        {node.children && node.children.map(child => renderNode(child, node))}
                    </div>
                );
            case 'heading':
                const HTag = `h${Math.min(Math.max(node.metadata?.level || 2, 1), 6)}`;
                return (
                    <HTag 
                        key={node.id} 
                        className={`text-xl font-bold mt-6 mb-4 cursor-pointer p-2 rounded transition-all duration-200 ${
                            isKey ? "bg-indigo-600 text-white" : "text-slate-800 dark:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/10"
                        }`}
                        onClick={(e) => {
                            e.stopPropagation();
                            handleTextClick(node, parentNode);
                        }}
                    >
                        {node.text}
                    </HTag>
                );
            case 'paragraph':
                return (
                    <p 
                        key={node.id} 
                        className={`mb-3 p-2.5 rounded-lg cursor-pointer font-mono text-sm border border-transparent transition-all duration-200 ${
                            isKey 
                                ? "bg-indigo-600 text-white shadow-md font-semibold" 
                                : "text-slate-700 dark:text-slate-200 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 hover:border-indigo-200 dark:hover:border-indigo-500/30"
                        }`}
                        onClick={(e) => {
                            e.stopPropagation();
                            handleTextClick(node, parentNode);
                        }}
                        title="Click to extract sentence or pair"
                    >
                        {node.text}
                    </p>
                );
            case 'table':
                return (
                    <div key={node.id} className="overflow-x-auto mb-6 bg-white dark:bg-[#1A2234] rounded-lg shadow-sm border border-slate-200 dark:border-white/10">
                        <table className="min-w-full text-sm text-left">
                            {node.children && node.children.map(child => renderNode(child, node))}
                        </table>
                    </div>
                );
            case 'header':
                return (
                    <thead key={node.id} className="text-xs uppercase bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
                        <tr>
                            {node.children && node.children.map(child => renderNode(child, node))}
                        </tr>
                    </thead>
                );
            case 'row':
                return (
                    <tr key={node.id} className="border-b last:border-b-0 border-slate-200 dark:border-white/10">
                        {node.children && node.children.map(child => renderNode(child, node))}
                    </tr>
                );
            case 'cell':
                let cellClass = "px-6 py-3 font-medium cursor-pointer transition-all duration-200 border-2 border-transparent ";
                if (isKey) {
                    cellClass += "bg-indigo-600 text-white dark:bg-indigo-500 shadow-md transform scale-[1.02] z-10 relative";
                } else if (isSuggestion) {
                    cellClass += "!border-dashed !border-green-500 bg-green-50/50 dark:bg-green-900/30 text-green-800 dark:text-green-300 transform scale-[1.02] z-10 relative";
                } else {
                    cellClass += "text-slate-900 dark:text-slate-100 hover:bg-slate-100 dark:hover:bg-white/10";
                }

                return (
                    <td 
                        key={node.id} 
                        className={cellClass}
                        onClick={(e) => {
                            e.stopPropagation();
                            handleCellClick(node, parentNode);
                        }}
                    >
                        {node.text}
                    </td>
                );
            case 'list':
                return (
                    <ul key={node.id} className="list-disc pl-5 mb-4 text-slate-600 dark:text-slate-300">
                        {node.children && node.children.map(child => renderNode(child, node))}
                    </ul>
                );
            case 'list_item':
                return (
                    <li 
                        key={node.id} 
                        className={`mb-1.5 p-2 rounded cursor-pointer transition-all duration-200 ${
                            isKey ? "bg-indigo-600 text-white" : "hover:bg-slate-100 dark:hover:bg-white/10"
                        }`}
                        onClick={(e) => {
                            e.stopPropagation();
                            handleTextClick(node, parentNode);
                        }}
                    >
                        {node.text}
                    </li>
                );
            default:
                return null;
        }
    };

    if (!pdfFile) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-4">
                <FileText className="w-12 h-12 text-slate-300 dark:text-slate-600" />
                <p>Upload a PDF to view the structured document</p>
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-3">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                <p>Loading structured document...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-red-500 gap-3 p-6 text-center">
                <p>{error}</p>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto p-6 bg-slate-50 dark:bg-[#0B0F19] relative">
            {pendingKeyNode && (
                <div className="sticky top-0 z-50 mb-4 bg-indigo-500 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2 animate-in slide-in-from-top-2">
                    <Info className="w-4 h-4" />
                    <span className="font-semibold">{pendingKeyNode.text}</span> selected as Key.
                    <span className="font-normal opacity-80">
                        Press <strong>Enter</strong> to accept suggestion, click a cell for Value, or press <strong>Esc</strong> to cancel.
                    </span>
                </div>
            )}
            
            <div className="max-w-4xl mx-auto">
                <div className="mb-6 flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-slate-800 dark:text-white flex items-center gap-2">
                        <FileText className="w-5 h-5 text-indigo-500" />
                        {pdfFile.name}
                    </h2>
                    <div className="text-sm text-slate-500">
                        Click any cell to set as Key
                    </div>
                </div>
                
                <div className="bg-white dark:bg-[#151B2B] rounded-xl shadow-sm border border-slate-200 dark:border-white/10 p-8 min-h-[600px]">
                    {structuredDoc ? renderNode(structuredDoc) : <p className="text-slate-500">No structured content found.</p>}
                </div>
            </div>
        </div>
    );
}
