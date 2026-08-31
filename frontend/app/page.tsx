'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, CheckCircle, AlertCircle, Loader2, ShieldCheck, ChevronRight } from 'lucide-react';

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

  // Auto-scroll to report when it's generated
  const reportRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (report && reportRef.current) {
      reportRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [report]);

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

  return (
    <main className="min-h-screen bg-[#0f172a] text-slate-50 overflow-hidden relative selection:bg-blue-500/30">
      
      {/* Dynamic Background Elements */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-blue-600/20 blur-[120px] mix-blend-screen animate-pulse-glow" style={{ animationDuration: '4s' }}></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-purple-600/20 blur-[120px] mix-blend-screen animate-pulse-glow" style={{ animationDuration: '6s', animationDelay: '1s' }}></div>
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 py-12 md:py-20 flex flex-col items-center min-h-screen">
        
        {/* Header Section */}
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16 w-full"
        >
          <div className="inline-flex items-center justify-center space-x-3 mb-6 bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 px-5 py-2 rounded-full shadow-lg">
            <ShieldCheck className="w-6 h-6 text-blue-400" />
            <h1 className="text-xl font-medium tracking-wide">ClauseGuard</h1>
          </div>
          
          <h2 className="text-4xl md:text-6xl font-bold mb-6 leading-tight">
            Protect your <span className="text-gradient">Freelance Contracts</span><br/> with AI Precision
          </h2>
          
          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Upload your contract and our multi-step AI pipeline will analyze it for risks, scope creep, and payment terms in seconds.
          </p>
        </motion.div>

        {/* Main Content Area */}
        <div className="w-full max-w-3xl flex flex-col items-center">
          
          {/* Upload Component */}
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="w-full mb-10"
          >
            <div 
              className={`glass-panel rounded-2xl p-8 transition-all duration-300 border-2 ${
                dragActive ? 'border-blue-500 bg-slate-800/80 shadow-[0_0_30px_rgba(59,130,246,0.3)]' : 'border-slate-700/50 hover:border-slate-600/80'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <div className="flex flex-col items-center justify-center text-center py-6">
                <div className={`p-4 rounded-full mb-6 transition-colors duration-300 ${file ? 'bg-green-500/10' : 'bg-blue-500/10'}`}>
                  {file ? (
                    <FileText className="w-10 h-10 text-green-400 animate-float" />
                  ) : (
                    <Upload className="w-10 h-10 text-blue-400 animate-float" />
                  )}
                </div>
                
                <h3 className="text-xl font-semibold mb-2">
                  {file ? 'File ready for analysis' : 'Upload your contract'}
                </h3>
                
                <p className="text-slate-400 mb-8 max-w-md">
                  {file 
                    ? <span className="text-slate-300 font-medium">{file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
                    : 'Drag and drop your .txt, .pdf, or .docx file here, or click to browse.'}
                </p>

                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept=".txt,.pdf,.docx,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={handleChange}
                />
                
                <div className="flex space-x-4">
                  <button
                    onClick={onButtonClick}
                    className="px-6 py-3 rounded-lg font-medium bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500"
                  >
                    {file ? 'Change File' : 'Select File'}
                  </button>
                  
                  {file && (
                    <button
                      onClick={handleUpload}
                      disabled={isLoading}
                      className="px-8 py-3 rounded-lg font-medium bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20 transition-all flex items-center group disabled:opacity-70 disabled:cursor-not-allowed disabled:hover:bg-blue-600"
                    >
                      {isLoading ? (
                        <>
                          <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                          Analyzing...
                        </>
                      ) : (
                        <>
                          Analyze Contract
                          <ChevronRight className="w-5 h-5 ml-1 group-hover:translate-x-1 transition-transform" />
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
                className="w-full mb-20"
              >
                <div className="flex items-center space-x-2 mb-6 ml-2">
                  <CheckCircle className="w-6 h-6 text-green-400" />
                  <h2 className="text-2xl font-bold">Analysis Complete</h2>
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
                        <h3 className="text-xl font-bold mb-2">Contract Safety Score</h3>
                        <p className="text-slate-400 text-sm max-w-sm">
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
                          <span className="text-xs text-slate-400 font-medium -mt-1">/ 100</span>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
                
                {/* Findings UI Cards */}
                {findings && findings.length > 0 ? (
                  <div className="space-y-6">
                    <h3 className="text-xl font-bold mb-4 flex items-center">
                      <AlertCircle className="w-5 h-5 mr-2 text-blue-400" />
                      Detailed Findings ({findings.length})
                    </h3>
                    
                    {findings.map((finding, idx) => (
                      <motion.div 
                        key={idx}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: 0.1 * idx }}
                        className="glass-panel rounded-xl p-6 border-l-4 border-slate-600 hover:border-blue-500 transition-colors"
                      >
                        <div className="flex justify-between items-start mb-4">
                          <div className="flex items-center space-x-3">
                            <span className="px-3 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700 uppercase tracking-wider">
                              {finding.category.replace('_', ' ')}
                            </span>
                            <span className="text-sm text-slate-400 font-medium">
                              Ref: {finding.clause_ref}
                            </span>
                          </div>
                        </div>
                        
                        <div className="bg-slate-900/50 rounded-lg p-4 mb-4 border border-slate-800/80">
                          <p className="text-slate-300 italic font-serif text-sm">"{finding.quote}"</p>
                        </div>
                        
                        <div>
                          <h4 className="text-sm font-semibold text-slate-400 mb-1 uppercase tracking-wide">Risk Explanation</h4>
                          <p className="text-slate-200 leading-relaxed">{finding.explanation}</p>
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
    </main>
  );
}
