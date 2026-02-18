import React, { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom'; 
import { Send, Mic, StopCircle, Bot, Sparkles, Loader2, X, RefreshCw, Volume2, TrendingUp, AlertTriangle, Users, BookOpen, Package, ShoppingCart } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"; 
import { cn } from "@/lib/utils";

// --- CONTEXT AWARE SUGGESTIONS ---
const getSuggestions = (pathname) => {
    switch (pathname) {
        case '/sales':
            return [
                { label: "Suggest Upsell", icon: ShoppingCart, query: "What usually sells well with Milk?" },
                { label: "Check Customer Credit", icon: Users, query: "Does this customer have pending dues?" }
            ];
        case '/products':
            return [
                { label: "Analyze Stock", icon: Package, query: "Which items are overstocked?" },
                { label: "Identify Low Stock", icon: AlertTriangle, query: "Show me items running low" }
            ];
        case '/customers':
        case '/ledger':
            return [
                { label: "Top Debtors", icon: BookOpen, query: "Who owes the most money?" },
                { label: "Draft Reminder", icon: Send, query: "Draft a payment reminder message" }
            ];
        default: 
            return [
                { label: "Forecast Sales", icon: TrendingUp, query: "Forecast sales for next month" },
                { label: "Business Health", icon: Sparkles, query: "How is my business doing overall?" },
                { label: "Check Churn", icon: Users, query: "Check churn risk" }
            ];
    }
};

const INITIAL_MESSAGE = { role: 'assistant', text: "Hello! I'm Nexus AI. I can analyze your database, predict sales, or manage inventory. How can I help?" };

export default function AiAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([INITIAL_MESSAGE]);
  const [processingStep, setProcessingStep] = useState('idle'); 
  
  const location = useLocation(); 
  const suggestions = getSuggestions(location.pathname); 

  const messagesEndRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, isOpen, processingStep]);

  // --- LOGIC: CLOSE & RESET ---
  const handleClose = (open) => {
    setIsOpen(open);
    if (!open) {
        window.speechSynthesis.cancel();
        if (mediaRecorderRef.current && processingStep === 'listening') {
            mediaRecorderRef.current.stop();
        }
        setTimeout(() => setProcessingStep('idle'), 300);
    }
  };

  const handleReset = () => {
      window.speechSynthesis.cancel();
      setMessages([INITIAL_MESSAGE]);
      setProcessingStep('idle');
  };

  // --- LOGIC: PROCESSING ---
  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!query.trim()) return; 
    const userText = query;
    setQuery(''); 
    const newMessages = [...messages, { role: 'user', text: userText }];
    setMessages(newMessages);
    await processAiRequest(userText, newMessages);
  };

  const processAiRequest = async (text, currentMessages) => {
    setProcessingStep('thinking');
    try {
        const data = await window.api.askAI(text);
        if(data.error) throw new Error(data.error);

        const aiReply = data.answer || "Sorry, I couldn't process that.";
        setMessages([...currentMessages, { role: 'assistant', text: aiReply }]);
        speakResponse(aiReply);
    } catch (err) {
        setMessages([...currentMessages, { role: 'assistant', text: "❌ Connection Error. Is the AI service running?" }]);
        setProcessingStep('idle');
    }
  };

  const speakResponse = (text) => {
    /*if (!window.speechSynthesis) {
        setProcessingStep('idle');
        return;
    }
    const cleanText = text.replace(/[*#]/g, '').replace(/❌|✅|⚠️/g, '');
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    setProcessingStep('speaking');
    
    utterance.onend = () => setProcessingStep('idle');
    utterance.onerror = () => setProcessingStep('idle');
    
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  };*/
    setProcessingStep('idle');
  };

  // --- LOGIC: VOICE ---
  const toggleListening = async () => {
    if (processingStep === 'listening') {
        if (mediaRecorderRef.current) {
            mediaRecorderRef.current.stop(); 
            setProcessingStep('transcribing');
        }
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' }); 
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) audioChunksRef.current.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
            const arrayBuffer = await audioBlob.arrayBuffer();
            await handleAudioUpload(arrayBuffer);
            stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorder.start();
        setProcessingStep('listening');
    } catch (err) {
        console.error("Mic Error:", err);
        setProcessingStep('idle');
    }
  };

  const handleAudioUpload = async (buffer) => {
      try {
          const data = await window.api.transcribeAudio(buffer);
          if (data.text) {
              setQuery(data.text);
              const newMsgs = [...messages, { role: 'user', text: data.text }];
              setMessages(newMsgs);
              await processAiRequest(data.text, newMsgs);
          } else {
              setProcessingStep('idle');
          }
      } catch (error) {
          console.error("Transcription Error", error);
          setProcessingStep('idle');
      }
  };

  const handleConfirm = () => { processAiRequest('YES', [...messages, {role: 'user', text: 'YES'}]); };
  const handleCancel = () => { processAiRequest('NO', [...messages, {role: 'user', text: 'NO'}]); };
  const isConfirmationRequest = (text) => text && (text.includes("Confirmation Required") || text.includes("Are you sure?"));

  // --- RENDER ---
  return (
    <>
        {/* TRIGGER BUTTON (Header) */}
        <Button 
            onClick={() => setIsOpen(true)}
            // Changed variant logic to force custom classes
            className={cn(
                "h-10 px-4 rounded-full transition-all gap-2 shadow-sm border", 
                isOpen 
                    ? "bg-slate-900 text-white border-slate-700"  // Active (Midnight Theme match)
                    : "bg-blue-600 hover:bg-blue-700 text-white border-transparent shadow-blue-200" // Inactive (High Visibility Blue)
            )}
        >
            <Sparkles size={18} className={cn(isOpen ? "text-cyan-400" : "text-blue-100 animate-pulse")} />
            <span className="hidden lg:inline text-sm font-bold">AI Assistant</span>
        </Button>

        {/* SLIDE-OVER SHEET (Midnight Theme) */}
        <Sheet open={isOpen} onOpenChange={handleClose}>
            <SheetContent className="w-[400px] sm:w-[450px] p-0 border-l border-slate-800 bg-slate-950 text-slate-100 flex flex-col shadow-2xl">
                
                {/* HEADER */}
                <SheetHeader className="p-4 border-b border-slate-800 bg-slate-950 sticky top-0 z-10">
                    <div className="flex justify-between items-center">
                        <div className="flex items-center gap-3">
                            <div className="h-10 w-10 rounded-full bg-slate-900 border border-slate-700 flex items-center justify-center shadow-[0_0_15px_rgba(34,211,238,0.2)]">
                                <Bot className="text-cyan-400" size={20} />
                            </div>
                            <div>
                                <SheetTitle className="text-slate-100 text-base">Nexus AI</SheetTitle>
                                <SheetDescription className="text-xs text-slate-400 flex items-center gap-2">
                                    {processingStep === 'idle' ? (
                                        <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_5px_rgba(34,197,94,0.5)]"/> Active</span>
                                    ) : (
                                        <span className="text-cyan-400 flex items-center gap-1.5 animate-pulse">
                                            {processingStep === 'listening' && <><Mic size={10}/> Listening...</>}
                                            {processingStep === 'transcribing' && <><Loader2 size={10} className="animate-spin"/> Transcribing...</>}
                                            {processingStep === 'thinking' && <><Sparkles size={10}/> Thinking...</>}
                                            {processingStep === 'speaking' && <><Volume2 size={10}/> Speaking...</>}
                                        </span>
                                    )}
                                </SheetDescription>
                            </div>
                        </div>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-500 hover:text-white hover:bg-slate-800" onClick={handleReset} title="Clear Chat">
                            <RefreshCw size={16} />
                        </Button>
                    </div>
                </SheetHeader>

                {/* CHAT AREA */}
                <ScrollArea className="flex-1 p-4 bg-slate-950/50">
                    <div className="space-y-6 pb-4">
                        {messages.map((msg, idx) => (
                            <div key={idx} className={cn("flex flex-col max-w-[90%]", msg.role === 'user' ? "ml-auto items-end" : "mr-auto items-start")}>
                                <div className={cn(
                                    "px-4 py-3 text-sm shadow-md backdrop-blur-sm", 
                                    msg.role === 'user' 
                                        ? "bg-blue-600 text-white rounded-2xl rounded-tr-none shadow-blue-900/20" 
                                        : "bg-slate-900 border border-slate-800 text-slate-200 rounded-2xl rounded-tl-none"
                                )}>
                                    {msg.text.split('\n').map((line, i) => <p key={i} className={cn("min-h-[1.2em] leading-relaxed", line.startsWith('-') && "ml-2 text-slate-300")}>{line}</p>)}
                                </div>
                                
                                {msg.role === 'assistant' && idx === messages.length - 1 && isConfirmationRequest(msg.text) && (
                                    <div className="flex gap-2 mt-3 animate-in fade-in slide-in-from-top-2">
                                        <Button size="sm" className="bg-green-600 hover:bg-green-700 text-white h-8 gap-1" onClick={handleConfirm}>Confirm</Button>
                                        <Button size="sm" variant="outline" className="h-8 text-slate-400 border-slate-700 hover:bg-slate-800 hover:text-red-400 gap-1" onClick={handleCancel}>Cancel</Button>
                                    </div>
                                )}
                            </div>
                        ))}
                        <div ref={messagesEndRef} />
                    </div>
                    
                    {/* CONTEXT SUGGESTIONS */}
                    {messages.length === 1 && (
                        <div className="grid grid-cols-1 gap-2 mt-6">
                            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-1 mb-1">Suggested Actions</p>
                            {suggestions.map((s, i) => (
                                <button key={i} onClick={() => { const newMsgs = [...messages, { role: 'user', text: s.query }]; setMessages(newMsgs); processAiRequest(s.query, newMsgs); }} className="p-3 flex items-center gap-3 text-left bg-slate-900/50 border border-slate-800 hover:border-blue-500/50 hover:bg-slate-800 rounded-xl transition-all group">
                                    <div className="h-8 w-8 rounded-full bg-slate-800 flex items-center justify-center group-hover:bg-blue-900/30 transition-colors border border-slate-700"><s.icon size={16} className="text-slate-400 group-hover:text-blue-400" /></div>
                                    <p className="text-xs font-medium text-slate-300 group-hover:text-blue-200">{s.label}</p>
                                </button>
                            ))}
                        </div>
                    )}
                </ScrollArea>

                {/* INPUT AREA */}
                <div className="p-4 bg-slate-950 border-t border-slate-800">
                    <form onSubmit={handleSearch} className="relative flex items-center gap-2">
                        <Button type="button" size="icon" variant="ghost" onClick={toggleListening} className={cn("h-10 w-10 shrink-0 rounded-full transition-all border", processingStep === 'listening' ? "bg-red-900/20 border-red-900 text-red-500 animate-pulse" : "border-transparent text-slate-500 hover:bg-slate-800 hover:text-slate-300")} title={processingStep === 'listening' ? "Stop Listening" : "Start Voice Input"}>
                            {processingStep === 'listening' ? <StopCircle size={20} /> : <Mic size={20} />}
                        </Button>
                        <Input 
                            value={query} 
                            onChange={(e) => setQuery(e.target.value)} 
                            placeholder={processingStep === 'listening' ? "Listening..." : "Ask AI..."} 
                            className="flex-1 h-10 bg-slate-900 border-slate-800 text-slate-200 placeholder:text-slate-600 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all rounded-full px-4 text-sm" 
                            disabled={processingStep === 'listening' || processingStep === 'thinking'} 
                        />
                        <Button type="submit" size="icon" disabled={!query.trim() || processingStep !== 'idle'} className="h-10 w-10 rounded-full bg-blue-600 hover:bg-blue-500 text-white shrink-0 shadow-lg shadow-blue-900/20 disabled:opacity-30 disabled:shadow-none"><Send size={18} /></Button>
                    </form>
                </div>
            </SheetContent>
        </Sheet>
    </>
  );
}