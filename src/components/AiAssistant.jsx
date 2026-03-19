import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useLocation } from 'react-router-dom';
import { Send, Mic, StopCircle, Bot, Sparkles, Loader2, RefreshCw, Volume2, TrendingUp, AlertTriangle, Users, Package, ShoppingCart, Zap, BarChart3, Search } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

// --- CONTEXT AWARE SUGGESTIONS (analytics-only) ---
const getSuggestions = (pathname) => {
    switch (pathname) {
        case '/':
            return [
                { label: "Today's Sales Summary", icon: BarChart3, query: "Today's sales" },
                { label: "Low Stock Alert", icon: AlertTriangle, query: "Low stock items" },
                { label: "Check Churn Risk", icon: Users, query: "Check churn risk" }
            ];
        case '/sales':
            return [
                { label: "Today's Revenue", icon: TrendingUp, query: "Today's sales" },
                { label: "Top 5 Customers", icon: Users, query: "Top 5 customers" },
                { label: "Recent Sales", icon: ShoppingCart, query: "Recent sales" }
            ];
        case '/products':
            return [
                { label: "Low Stock Items", icon: AlertTriangle, query: "Low stock items" },
                { label: "Out of Stock", icon: Package, query: "Out of stock" },
                { label: "Top Selling Products", icon: TrendingUp, query: "Top 5 products" }
            ];
        case '/customers':
        case '/ledger':
            return [
                { label: "All Customers", icon: Search, query: "All customers" },
                { label: "Top Customers", icon: Users, query: "Top customers" },
                { label: "Recent Sales", icon: ShoppingCart, query: "Recent sales" }
            ];
        default:
            return [
                { label: "Quick Summary", icon: Zap, query: "Quick summary" },
                { label: "Market Basket Insights", icon: ShoppingCart, query: "Market basket insights" },
                { label: "Monthly Revenue", icon: TrendingUp, query: "Monthly revenue" }
            ];
    }
};

// --- RICH MARKDOWN RENDERER (react-markdown + remark-gfm) ---
const RenderMarkdown = ({ text }) => {
    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
                h1: ({ children }) => <h2 className="text-base font-bold text-white mt-3 mb-1.5 pb-1 border-b border-white/10">{children}</h2>,
                h2: ({ children }) => <h3 className="text-sm font-bold text-white mt-3 mb-1">{children}</h3>,
                h3: ({ children }) => <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mt-2.5 mb-1">{children}</h4>,
                p: ({ children }) => <p className="text-slate-300 text-[13px] leading-relaxed mb-1.5">{children}</p>,
                strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                em: ({ children }) => <em className="text-slate-400 italic">{children}</em>,
                ul: ({ children }) => <ul className="space-y-0.5 ml-1 my-1">{children}</ul>,
                ol: ({ children }) => <ol className="space-y-0.5 ml-1 my-1 list-none">{children}</ol>,
                li: ({ children, ordered, index }) => (
                    <li className="flex gap-2 py-0.5">
                        <span className={cn(
                            "mt-0.5 min-w-[14px] text-xs font-bold flex-shrink-0",
                            ordered ? "text-emerald-400" : "text-slate-500 text-[6px] mt-1.5"
                        )}>
                            {ordered ? `${(index ?? 0) + 1}.` : "●"}
                        </span>
                        <span className="text-slate-300 text-[13px] leading-relaxed flex-1">{children}</span>
                    </li>
                ),
                code: ({ inline, children }) => inline ? (
                    <code className="px-1 py-0.5 rounded bg-white/10 text-emerald-300 text-[11px] font-mono">{children}</code>
                ) : (
                    <pre className="bg-black/30 rounded-md p-2.5 my-1.5 overflow-x-auto border border-white/5">
                        <code className="text-emerald-300 text-[11px] font-mono leading-relaxed">{children}</code>
                    </pre>
                ),
                hr: () => <hr className="border-white/10 my-2.5" />,
                a: ({ href, children }) => <a href={href} className="text-blue-400 hover:text-blue-300 underline underline-offset-2" target="_blank" rel="noopener noreferrer">{children}</a>,
                table: ({ children }) => (
                    <div className="overflow-x-auto my-2 rounded-md border border-white/10">
                        <table className="w-full text-[11px]">{children}</table>
                    </div>
                ),
                thead: ({ children }) => <thead className="bg-white/5">{children}</thead>,
                th: ({ children }) => <th className="px-2 py-1.5 text-left text-xs font-semibold text-slate-300 border-b border-white/10">{children}</th>,
                td: ({ children }) => <td className="px-2 py-1 text-slate-400 border-b border-white/5">{children}</td>,
                tr: ({ children }) => <tr className="hover:bg-white/5 transition-colors">{children}</tr>,
                blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-emerald-500/50 pl-3 my-1.5 text-slate-400 italic">{children}</blockquote>
                ),
            }}
        >
            {text}
        </ReactMarkdown>
    );
};

const INITIAL_MESSAGE = { id: 'init', role: 'assistant', text: "👋 Hey! I'm your **Nexus Business AI**. Here's what I can do:\n\n📊 **Sales & Revenue** — Trends, comparisons, top sellers\n👥 **Customer Intel** — Segments, churn risk, loyalty\n📦 **Inventory** — Stock velocity, restocking alerts, dead stock\n🛒 **Growth Strategy** — Market basket, cross-sell opportunities\n\nTry asking: *\"How can I increase my sales?\"* or *\"What should I restock?\"*" };

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
    const inputRef = useRef(null);

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

    // --- LOGIC: CLASSIFY MESSAGE TYPE ---
    const getMessageType = (text) => {
        if (!text) return 'normal';
        if (text.includes('⏳') || text.includes('rate limit')) return 'rate_limit';
        if (text.includes('⏱️') || text.includes('timed out')) return 'timeout';
        if (text.startsWith('❌') || text.includes('Error:')) return 'error';
        if (text.startsWith('✅')) return 'success';
        if (text.startsWith('🚫')) return 'cancelled';
        return 'normal';
    };

    // --- LOGIC: PROCESSING ---
    const handleSearch = async (e) => {
        if (e) e.preventDefault();
        if (!query.trim()) return;
        const userText = query;
        setQuery('');
        const newMessages = [...messages, { id: crypto.randomUUID(), role: 'user', text: userText }];
        setMessages(newMessages);
        await processAiRequest(userText, newMessages);
    };

    const processAiRequest = async (text, currentMessages) => {
        setProcessingStep('thinking');
        try {
            const data = await window.api.askAI(text);
            if (data.error) throw new Error(data.error);

            const aiReply = data.answer || "Sorry, I couldn't process that.";
            const errorType = data.error_type || null;
            setMessages([...currentMessages, { id: crypto.randomUUID(), role: 'assistant', text: aiReply, errorType }]);
            setProcessingStep('idle');
        } catch (err) {
            const errMsg = err.message || "Connection failed";
            let friendlyMsg;
            if (errMsg.includes('rate limit') || errMsg.includes('429')) {
                friendlyMsg = "⏳ API rate limit reached. Please wait about a minute.";
            } else if (errMsg.includes('timed out') || errMsg.includes('timeout')) {
                friendlyMsg = "⏱️ Request timed out. Please try again.";
            } else if (errMsg.includes('AI not configured')) {
                friendlyMsg = "⚙️ AI not configured. Please set your Groq API key in Settings.";
            } else {
                friendlyMsg = `❌ ${errMsg}`;
            }
            setMessages([...currentMessages, { id: crypto.randomUUID(), role: 'assistant', text: friendlyMsg, errorType: 'error' }]);
            setProcessingStep('idle');
        }
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
                const newMsgs = [...messages, { id: crypto.randomUUID(), role: 'user', text: data.text }];
                setMessages(newMsgs);
                setQuery('');
                await processAiRequest(data.text, newMsgs);
            } else {
                setProcessingStep('idle');
            }
        } catch (error) {
            console.error("Transcription Error", error);
            setProcessingStep('idle');
        }
    };

    // --- RENDER ---
    return (
        <>
            {/* TRIGGER BUTTON (Header) */}
            <Button
                onClick={() => setIsOpen(true)}
                className={cn(
                    "h-10 px-4 rounded-full transition-all gap-2 shadow-sm border",
                    isOpen
                        ? "bg-slate-900 text-white border-slate-700"
                        : "bg-blue-600 hover:bg-blue-700 text-white border-transparent shadow-blue-200"
                )}
            >
                <Sparkles size={18} className={cn(isOpen ? "text-cyan-400" : "text-blue-100 animate-pulse")} />
                <span className="hidden lg:inline text-sm font-bold">AI Assistant</span>
            </Button>

            {/* SLIDE-OVER SHEET (Midnight Theme) */}
            <Sheet open={isOpen} onOpenChange={handleClose}>
                <SheetContent className="w-[440px] sm:w-[500px] p-0 border-l border-slate-800 bg-slate-950 text-slate-100 flex flex-col shadow-2xl">

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
                                            <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_5px_rgba(34,197,94,0.5)]" /> Active</span>
                                        ) : (
                                            <span className="text-cyan-400 flex items-center gap-1.5 animate-pulse">
                                                {processingStep === 'listening' && <><Mic size={10} /> Listening...</>}
                                                {processingStep === 'transcribing' && <><Loader2 size={10} className="animate-spin" /> Transcribing...</>}
                                                {processingStep === 'thinking' && <><Sparkles size={10} /> Thinking...</>}
                                                {processingStep === 'speaking' && <><Volume2 size={10} /> Speaking...</>}
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
                            {messages.map((msg) => {
                                const msgType = msg.role === 'assistant' ? getMessageType(msg.text) : 'user';

                                return (
                                    <div key={msg.id} className={cn("flex flex-col max-w-[90%]", msg.role === 'user' ? "ml-auto items-end" : "mr-auto items-start")}>
                                        <div className={cn(
                                            "px-4 py-3 text-sm shadow-md backdrop-blur-sm",
                                            msg.role === 'user'
                                                ? "bg-blue-600 text-white rounded-2xl rounded-tr-none shadow-blue-900/20"
                                                : cn(
                                                    "rounded-2xl rounded-tl-none",
                                                    msgType === 'rate_limit' && "bg-amber-950/50 border border-amber-800/50 text-amber-200",
                                                    msgType === 'timeout' && "bg-amber-950/50 border border-amber-800/50 text-amber-200",
                                                    msgType === 'error' && "bg-red-950/50 border border-red-800/50 text-red-200",
                                                    msgType === 'success' && "bg-emerald-950/50 border border-emerald-800/50 text-emerald-200",
                                                    msgType === 'cancelled' && "bg-slate-900 border border-slate-700 text-slate-400",
                                                    msgType === 'normal' && "bg-slate-900 border border-slate-800 text-slate-200"
                                                )
                                        )}>
                                            <RenderMarkdown text={msg.text} />
                                        </div>
                                    </div>
                                )
                            })}

                            {/* THINKING INDICATOR */}
                            {processingStep === 'thinking' && (
                                <div className="flex items-start gap-3 mr-auto max-w-[90%] animate-in fade-in">
                                    <div className="px-4 py-3 rounded-2xl rounded-tl-none bg-slate-900 border border-slate-800">
                                        <div className="flex items-center gap-2">
                                            <div className="flex gap-1">
                                                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                                                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                                                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                                            </div>
                                            <span className="text-xs text-slate-500 ml-1">Thinking...</span>
                                        </div>
                                    </div>
                                </div>
                            )}

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
                                ref={inputRef}
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