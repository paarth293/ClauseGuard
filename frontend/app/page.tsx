'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, CheckCircle, AlertCircle, Loader2, ShieldCheck, ChevronRight, DollarSign, ShieldAlert, Copyright, Briefcase, FileWarning, AlertTriangle, Sparkles, Copy, Check, MessageSquare, X, Send, Download } from 'lucide-react';

export interface Finding {
  clause_ref: string;
  quote: string;
  category: string;
  severity: string;
  explanation: string;
  confidence: number;
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [report, setReport] = useState<string | null>(null);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [score, setScore] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // "Fix it for me" State
  const [loadingAlternatives, setLoadingAlternatives] = useState<Record<number, boolean>>({});
  const [safeClauses, setSafeClauses] = useState<Record<number, string>>({});
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  // Chatbot State
  const [contractText, setContractText] = useState<string | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<{role: 'user'|'bot', content: string}[]>([
    { role: 'bot', content: 'Hi! I have read your contract. What would you like to know?' }
  ]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chatMessages]);

  // Auto-scroll to report when it's generated
  const reportRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (report && reportRef.current) {
      reportRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [report]);

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'payment_terms': return <DollarSign className="w-4 h-4 mr-1" />;
      case 'liability_cap': return <ShieldAlert className="w-4 h-4 mr-1" />;
      case 'ip_ownership': return <Copyright className="w-4 h-4 mr-1" />;
      case 'kill_fee': return <Briefcase className="w-4 h-4 mr-1" />;
      case 'indemnification': return <FileWarning className="w-4 h-4 mr-1" />;
      default: return <AlertTriangle className="w-4 h-4 mr-1" />;
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFileSelection(e.target.files[0]);
    }
  };

  const handleFileSelection = (selectedFile: File) => {
    setFile(selectedFile);
    setError(null);
    setReport(null);
    setFindings(null);
    setScore(null);
    setSafeClauses({});
    setContractText(null);
    setChatMessages([{ role: 'bot', content: 'Hi! I have read your contract. What would you like to know?' }]);
  };

  const onButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file first.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setReport(null);
    setFindings(null);
    setScore(null);
    setSafeClauses({});
    setContractText(null);
    setChatMessages([{ role: 'bot', content: 'Hi! I have read your contract. What would you like to know?' }]);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:8000/analyze', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      if (data.report) {
        setReport(data.report);
        if (data.findings) setFindings(data.findings);
        if (data.score !== undefined) setScore(data.score);
        if (data.contract_text) setContractText(data.contract_text);
      } else {
        throw new Error("Invalid response format from server.");
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "An unexpected error occurred during analysis.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateAlternative = async (idx: number, finding: Finding) => {
    setLoadingAlternatives(prev => ({ ...prev, [idx]: true }));
    try {
      const response = await fetch('http://localhost:8000/generate-alternative', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          risky_clause: finding.quote,
          category: finding.category,
          explanation: finding.explanation
        })
      });

      if (!response.ok) throw new Error("Failed to generate alternative");
      
      const data = await response.json();
      setSafeClauses(prev => ({ ...prev, [idx]: data.safe_clause }));
    } catch (err) {
      console.error(err);
      setSafeClauses(prev => ({ ...prev, [idx]: "Error generating alternative clause. Please try again." }));
    } finally {
      setLoadingAlternatives(prev => ({ ...prev, [idx]: false }));
    }
  };

  const handleCopy = (idx: number, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !contractText) return;

    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsChatLoading(true);

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contract_text: contractText, question: userMsg })
      });
      if (!response.ok) throw new Error("Chat failed");
      
      const data = await response.json();
      setChatMessages(prev => [...prev, { role: 'bot', content: data.answer }]);
    } catch (err) {
      setChatMessages(prev => [...prev, { role: 'bot', content: "Sorry, I couldn't process that question right now." }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-black text-slate-50 overflow-hidden relative selection:bg-white/20 print:bg-white print:text-black font-sans">
      
      {/* Dynamic Background Elements - Minimal & Professional */}
      <div className="fixed inset-0 z-0 pointer-events-none print:hidden overflow-hidden flex justify-center">
        {/* Spotlight effect from top */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[80vw] h-[500px] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/20 via-blue-900/5 to-transparent opacity-60"></div>
        
        {/* Very subtle noise texture for premium feel */}
        <div className="absolute inset-0 opacity-[0.03] mix-blend-overlay bg-[url('https://grainy-gradients.vercel.app/noise.svg')]"></div>
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-12 md:py-20 flex flex-col items-center min-h-screen">
        
        {/* Header Section */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="text-center mb-16 w-full print:hidden relative z-10 pt-10"
        >
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="inline-flex items-center justify-center space-x-2 mb-8 bg-white/5 backdrop-blur-xl border border-white/10 px-4 py-1.5 rounded-full hover:bg-white/10 transition-colors cursor-default"
          >
            <Sparkles className="w-4 h-4 text-blue-400" />
            <span className="text-xs font-medium tracking-wide text-slate-300">Introducing ClauseGuard AI</span>
          </motion.div>
          
          <h2 className="text-5xl md:text-7xl font-bold mb-6 leading-tight tracking-tighter text-white">
            Contract analysis, <br/>
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-slate-300 via-white to-slate-400">perfected by AI.</span>
          </h2>
          
          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed font-light">
            Upload any freelance contract. Our advanced pipeline identifies hidden risks, scope creep, and payment vulnerabilities in seconds.
          </p>
        </motion.div>

        {/* Main Content Area */}
        <div className="w-full max-w-3xl flex flex-col items-center">
          
          {/* Upload Component */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.4, ease: "easeOut" }}
            className="w-full mb-12 print:hidden relative group"
          >
            <div 
              className={`relative z-10 rounded-2xl border transition-all duration-300 overflow-hidden ${
                dragActive ? 'border-blue-500/50 bg-blue-500/5 scale-[1.01]' : 'border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <div className="absolute inset-0 backdrop-blur-3xl -z-10"></div>
              
              <div className="flex flex-col items-center justify-center text-center py-16 px-8">
                
                <div className="relative mb-6">
                  <div className={`p-4 rounded-2xl border transition-colors duration-300 ${
                    file ? 'bg-white/10 border-white/20 text-white' : 'bg-white/5 border-white/10 text-slate-400 group-hover:text-white'
                  }`}>
                    {file ? (
                      <FileText className="w-8 h-8" />
                    ) : (
                      <Upload className="w-8 h-8" />
                    )}
                  </div>
                </div>
                
                <h3 className="text-xl font-medium mb-2 text-white">
                  {file ? 'File ready for analysis' : 'Upload document'}
                </h3>
                
                <p className="text-slate-400 mb-8 max-w-sm text-sm">
                  {file 
                    ? <span className="text-slate-300 bg-white/10 px-2 py-1 rounded">{file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
                    : 'Drag and drop your .txt, .pdf, or .docx file here, or click to browse files from your computer.'}
                </p>

                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept=".txt,.pdf,.docx,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={handleChange}
                />
                
                <div className="flex flex-col sm:flex-row space-y-3 sm:space-y-0 sm:space-x-4 w-full sm:w-auto">
                  <button
                    onClick={onButtonClick}
                    className="px-6 py-2.5 rounded-lg text-sm font-medium bg-white/5 hover:bg-white/10 border border-white/10 text-white transition-all w-full sm:w-auto focus:ring-2 focus:ring-white/20"
                  >
                    {file ? 'Change file' : 'Browse files'}
                  </button>
                  
                  {file && (
                    <button
                      onClick={handleUpload}
                      disabled={isLoading}
                      className="px-6 py-2.5 rounded-lg text-sm font-medium bg-white text-black hover:bg-slate-200 transition-all flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed w-full sm:w-auto"
                    >
                      {isLoading ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Analyzing
                        </>
                      ) : (
                        <>
                          Analyze document
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Loading State / Progress Indicator */}
          <AnimatePresence>
            {isLoading && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="w-full mb-10 overflow-hidden"
              >
                <div className="glass-panel rounded-xl p-6 flex flex-col items-center">
                  <div className="flex items-center space-x-4 mb-4">
                    <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                    <h3 className="text-lg font-medium">Processing Contract...</h3>
                  </div>
                  <div className="w-full max-w-md h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full w-1/2 bg-gradient-to-r from-blue-500 via-purple-500 to-blue-500 rounded-full animate-pulse"></div>
                  </div>
                  <p className="text-sm text-slate-400 mt-4 text-center">
                    Running multi-step pipeline (Ingestion <ChevronRight className="inline w-3 h-3"/> Analysis <ChevronRight className="inline w-3 h-3"/> Verification <ChevronRight className="inline w-3 h-3"/> Synthesis)
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Error State */}
          <AnimatePresence>
            {error && !isLoading && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="w-full mb-10 glass-panel rounded-xl p-6 border-red-500/30 bg-red-500/5 flex items-start space-x-4"
              >
                <AlertCircle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-red-400 font-medium mb-1">Analysis Failed</h3>
                  <p className="text-slate-300 text-sm">{error}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Results Component */}
          <AnimatePresence>
            {report && !isLoading && (
              <motion.div
                ref={reportRef}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, type: "spring" }}
                className="w-full mb-20 print:m-0"
              >
                <div className="flex items-center justify-between mb-6 ml-2 print:hidden">
                  <div className="flex items-center space-x-2">
                    <CheckCircle className="w-6 h-6 text-green-400" />
                    <h2 className="text-2xl font-bold">Analysis Complete</h2>
                  </div>
                  <button 
                    onClick={() => window.print()}
                    className="flex items-center space-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors border border-slate-700 hover:border-slate-600"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download PDF</span>
                  </button>
                </div>

                {/* Risk Score Component */}
                {score !== null && (
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="glass-panel rounded-2xl p-6 md:p-8 mb-8 border-l-4" 
                    style={{
                      borderColor: score >= 80 ? '#22c55e' : score >= 50 ? '#eab308' : '#ef4444'
                    }}
                  >
                    <div className="flex flex-col md:flex-row items-center justify-between">
                      <div className="mb-6 md:mb-0 text-center md:text-left">
                        <h3 className="text-xl font-bold mb-2 print:text-black">Contract Safety Score</h3>
                        <p className="text-slate-400 text-sm max-w-sm print:text-slate-700">
                          {score >= 80 ? 'This contract is highly favorable and safe. Minor issues only.' 
                            : score >= 50 ? 'Proceed with caution. Some terms are risky and need negotiation.' 
                            : 'High risk! Major red flags detected. Do not sign without revisions.'}
                        </p>
                      </div>
                      
                      <div className="relative w-32 h-32 flex items-center justify-center shrink-0">
                        <svg className="w-full h-full transform -rotate-90">
                          <circle cx="64" cy="64" r="56" fill="transparent" stroke="#1e293b" strokeWidth="12" />
                          <motion.circle 
                            cx="64" cy="64" r="56" fill="transparent" 
                            stroke={score >= 80 ? '#22c55e' : score >= 50 ? '#eab308' : '#ef4444'} 
                            strokeWidth="12"
                            strokeDasharray="351.85"
                            initial={{ strokeDashoffset: 351.85 }}
                            animate={{ strokeDashoffset: 351.85 - (351.85 * score) / 100 }}
                            transition={{ duration: 1.5, ease: "easeOut", delay: 0.4 }}
                            strokeLinecap="round"
                          />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center flex-col">
                          <span className="text-3xl font-bold tracking-tighter" style={{
                            color: score >= 80 ? '#4ade80' : score >= 50 ? '#facc15' : '#f87171'
                          }}>
                            {score}
                          </span>
                          <span className="text-xs text-slate-400 font-medium -mt-1 print:text-slate-600">/ 100</span>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
                
                {/* Findings UI Cards */}
                {findings && findings.length > 0 ? (
                  <div className="space-y-6">
                    <h3 className="text-xl font-bold mb-4 flex items-center print:text-black">
                      <AlertCircle className="w-5 h-5 mr-2 text-blue-400" />
                      Detailed Findings ({findings.length})
                    </h3>
                    
                    {findings.map((finding, idx) => (
                      <motion.div 
                        key={idx}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: 0.1 * idx }}
                        className={`glass-panel rounded-xl p-6 border-l-4 transition-colors ${
                          finding.severity === 'must_raise' 
                          ? 'border-l-red-500 hover:border-l-red-400' 
                          : 'border-l-yellow-500 hover:border-l-yellow-400'
                        }`}
                      >
                        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700 uppercase tracking-wider print:bg-slate-100 print:text-slate-800 print:border-slate-300">
                              {getCategoryIcon(finding.category)}
                              {finding.category.replace('_', ' ')}
                            </span>
                            <span className={`px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider border ${
                              finding.severity === 'must_raise'
                              ? 'bg-red-500/10 text-red-400 border-red-500/30'
                              : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'
                            }`}>
                              {finding.severity.replace('_', ' ')}
                            </span>
                          </div>
                          <span className="text-xs text-slate-400 font-medium bg-slate-900/50 px-2 py-1 rounded print:bg-slate-200 print:text-slate-800">
                            Ref: {finding.clause_ref}
                          </span>
                        </div>
                        
                        <div className="bg-slate-900/50 rounded-lg p-4 mb-4 border border-slate-800/80 print:bg-slate-50 print:border-slate-300">
                          <p className="text-slate-300 italic font-serif text-sm print:text-slate-900 print:not-italic print:font-sans print:text-base">"{finding.quote}"</p>
                        </div>
                        
                        <div>
                          <h4 className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide print:text-slate-700">Risk Explanation</h4>
                          <p className="text-slate-200 leading-relaxed text-sm mb-4 print:text-black print:text-base">{finding.explanation}</p>
                          
                          {!safeClauses[idx] && (
                            <button
                              onClick={() => handleGenerateAlternative(idx, finding)}
                              disabled={loadingAlternatives[idx]}
                              className="inline-flex items-center px-4 py-2 bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 text-sm font-medium rounded-lg transition-colors border border-blue-500/30 disabled:opacity-50 disabled:cursor-not-allowed print:hidden"
                            >
                              {loadingAlternatives[idx] ? (
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              ) : (
                                <Sparkles className="w-4 h-4 mr-2" />
                              )}
                              Fix it for me
                            </button>
                          )}

                          {safeClauses[idx] && (
                            <motion.div 
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              className="mt-4 p-4 rounded-lg bg-blue-900/20 border border-blue-500/30 relative"
                            >
                              <div className="flex justify-between items-center mb-3">
                                <h4 className="text-xs font-semibold text-blue-400 uppercase tracking-wide flex items-center">
                                  <Sparkles className="w-3 h-3 mr-1" />
                                  Suggested Safe Clause
                                </h4>
                                <button 
                                  onClick={() => handleCopy(idx, safeClauses[idx])}
                                  className="text-slate-400 hover:text-white transition-colors print:hidden"
                                  title="Copy to clipboard"
                                >
                                  {copiedIdx === idx ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                                </button>
                              </div>
                              <p className="text-sm text-slate-200 font-serif leading-relaxed whitespace-pre-wrap print:text-black">
                                {safeClauses[idx]}
                              </p>
                            </motion.div>
                          )}
                        </div>
                      </motion.div>
                    ))}
                  </div>
                ) : (
                  <div className="glass-panel rounded-2xl p-6 md:p-10 border-t-4 border-t-blue-500 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/5 rounded-full blur-[80px] -translate-y-1/2 translate-x-1/4 pointer-events-none"></div>
                    <div className="markdown-content relative z-10">
                      {report ? <ReactMarkdown>{report}</ReactMarkdown> : <p>No risks identified!</p>}
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

        </div>
      </div>

      {/* Floating Chat UI */}
      <AnimatePresence>
        {contractText && (
          <motion.div 
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            className="fixed bottom-6 right-6 z-50 flex flex-col items-end print:hidden"
          >
            {/* Chat Window */}
            <AnimatePresence>
              {isChatOpen && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9, y: 20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.9, y: 20 }}
                  className="bg-slate-900 border border-slate-700 shadow-2xl rounded-2xl w-80 sm:w-96 h-[500px] mb-4 flex flex-col overflow-hidden"
                >
                  {/* Header */}
                  <div className="bg-slate-800 p-4 border-b border-slate-700 flex justify-between items-center">
                    <div className="flex items-center space-x-2">
                      <ShieldCheck className="w-5 h-5 text-blue-400" />
                      <h3 className="font-bold text-slate-200">ClauseGuard Assistant</h3>
                    </div>
                    <button onClick={() => setIsChatOpen(false)} className="text-slate-400 hover:text-white transition">
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                  
                  {/* Messages */}
                  <div ref={chatScrollRef} className="flex-1 p-4 overflow-y-auto flex flex-col space-y-4">
                    {chatMessages.map((msg, i) => (
                      <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] rounded-xl p-3 text-sm leading-relaxed ${
                          msg.role === 'user' ? 'bg-blue-600 text-white rounded-br-none' : 'bg-slate-800 text-slate-200 border border-slate-700 rounded-bl-none'
                        }`}>
                          <div className="prose prose-invert prose-sm max-w-none">
                            <ReactMarkdown>{msg.content}</ReactMarkdown>
                          </div>
                        </div>
                      </div>
                    ))}
                    {isChatLoading && (
                      <div className="flex justify-start">
                        <div className="bg-slate-800 border border-slate-700 rounded-xl rounded-bl-none p-4 flex space-x-2 items-center">
                          <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce delay-100"></div>
                          <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce delay-200"></div>
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* Input */}
                  <form onSubmit={handleSendMessage} className="p-3 bg-slate-800 border-t border-slate-700 flex items-center space-x-2">
                    <input 
                      type="text" 
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      placeholder="Ask about your contract..." 
                      className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 text-white"
                      disabled={isChatLoading}
                    />
                    <button 
                      type="submit" 
                      disabled={!chatInput.trim() || isChatLoading}
                      className="p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </form>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Chat Toggle Button */}
            {!isChatOpen && (
              <button 
                onClick={() => setIsChatOpen(true)}
                className="bg-blue-600 hover:bg-blue-500 text-white p-4 rounded-full shadow-[0_0_20px_rgba(37,99,235,0.4)] hover:shadow-[0_0_25px_rgba(37,99,235,0.6)] transition-all flex items-center justify-center group"
              >
                <MessageSquare className="w-6 h-6 group-hover:scale-110 transition-transform" />
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>

    </main>
  );
}
