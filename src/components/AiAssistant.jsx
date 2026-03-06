import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { Send, Mic, StopCircle, Bot, Sparkles, Loader2, X, RefreshCw, Volume2, TrendingUp, AlertTriangle, Users, BookOpen, Package, ShoppingCart, CheckCircle2, XCircle, Clock, Zap } from 'lucide-react';
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

// --- SIMPLE MARKDOWN RENDERER ---
const RenderMarkdown = ({ text }) => {
    const lines = text.split('\n');
    return lines.map((line, i) => {
        // Bold: **text**
        let processed = line.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-white">$1</strong>');
        // Bullet points
        const isBullet = line.trimStart().startsWith('-') || line.trimStart().startsWith('•');

        return (
            <p
                key={i}
                className={cn(
                    "min-h-[1.2em] leading-relaxed",
                    isBullet && "ml-3 text-slate-300"
                )}
                dangerouslySetInnerHTML={{ __html: processed }}
            />
        );
    });
};

const INITIAL_MESSAGE = { role: 'assistant', text: "Hello! I'm Nexus AI. I can analyze your database, predict sales, or manage inventory. How can I help?" };

const DisambiguationCard = ({ options, action, onSelect, onCancel, isLatest }) => {
    const [selectedIndex, setSelectedIndex] = useState(0);

    useEffect(() => {
        if (!isLatest) return;
        const handler = (e) => {
            if (e.key === 'Escape') { e.preventDefault(); onCancel(); }
            if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIndex(prev => Math.min(options.length - 1, prev + 1)); }
            if (e.key === 'ArrowUp') { e.preventDefault(); setSelectedIndex(prev => Math.max(0, prev - 1)); }
            if (e.key === 'Enter') { e.preventDefault(); onSelect(options[selectedIndex]); }
            const num = parseInt(e.key);
            if (!isNaN(num) && num > 0 && num <= options.length) {
                e.preventDefault();
                onSelect(options[num - 1]);
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [isLatest, options, selectedIndex, onSelect, onCancel]);

    return (
        <div className="flex flex-col gap-2 mt-3 animate-in fade-in slide-in-from-top-2 w-full min-w-[280px]">
            {options.map((opt, i) => (
                <button
                    key={i}
                    onClick={() => { if (isLatest) onSelect(opt); }}
                    className={cn(
                        "w-full text-left p-3 rounded-lg border flex items-center justify-between transition-all",
                        selectedIndex === i && isLatest ? "bg-blue-900/40 border-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.2)] shadow-inner" : "bg-slate-800/50 border-slate-700 hover:border-slate-500 hover:bg-slate-800 opacity-90"
                    )}
                    disabled={!isLatest}
                >
                    <span className="text-sm font-medium text-slate-200">{i + 1}. {opt}</span>
                    {selectedIndex === i && isLatest && <span className="text-[10px] text-blue-400 font-bold bg-blue-950 border border-blue-900 px-2 py-0.5 rounded shadow-sm">ENTER</span>}
                </button>
            ))}
            {isLatest && (
                <div className="flex justify-between items-center mt-2 px-1">
                    <Button size="sm" variant="ghost" onClick={onCancel} className="h-8 text-[11px] text-slate-400 hover:text-red-400 hover:bg-slate-800"><X size={12} className="mr-1" /> Cancel</Button>
                    <span className="text-[10px] text-slate-500 font-medium">Use ↑↓ or 1-{options.length}</span>
                </div>
            )}
        </div>
    );
};

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
    const confirmBtnRef = useRef(null);
    const inputRef = useRef(null);

    useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, isOpen, processingStep]);

    // --- KEYBOARD: Enter=Confirm, Escape=Cancel ---
    const lastMessage = messages[messages.length - 1];
    const showConfirmation = lastMessage?.role === 'assistant' && isConfirmationRequest(lastMessage?.text) && processingStep === 'idle';

    useEffect(() => {
        if (!showConfirmation) return;
        // Auto-focus confirm button
        setTimeout(() => confirmBtnRef.current?.focus(), 100);

        const handler = (e) => {
            if (e.key === 'Enter') { e.preventDefault(); handleConfirm(); }
            if (e.key === 'Escape') { e.preventDefault(); handleCancel(); }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [showConfirmation]);

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
        if (text.includes('Confirmation Required')) return 'confirmation';
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
        const newMessages = [...messages, { role: 'user', text: userText }];
        setMessages(newMessages);
        await processAiRequest(userText, newMessages);
    };

    const processAiRequest = async (text, currentMessages) => {
        setProcessingStep('thinking');
        try {
            const data = await window.api.askAI(text);
            if (data.error) throw new Error(data.error);

            if (data.type === 'disambiguation') {
                setMessages([...currentMessages, {
                    role: 'assistant',
                    type: 'disambiguation',
                    text: `⚠️ **${data.message || "Multiple matches found."}**`,
                    options: data.options,
                    action: data.original_action
                }]);
                setProcessingStep('idle');
            } else {
                const aiReply = data.answer || "Sorry, I couldn't process that.";
                const errorType = data.error_type || null;
                setMessages([...currentMessages, { role: 'assistant', text: aiReply, errorType }]);
                speakResponse(aiReply);
            }
        } catch (err) {
            const errMsg = err.message || "Connection failed";
            // Surface the actual error, not a generic message
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
            setMessages([...currentMessages, { role: 'assistant', text: friendlyMsg, errorType: 'error' }]);
            setProcessingStep('idle');
        }
    };

    const speakResponse = (text) => {
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
                const newMsgs = [...messages, { role: 'user', text: data.text }];
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

    const handleConfirm = useCallback(() => { processAiRequest('YES', [...messages, { role: 'user', text: 'YES' }]); }, [messages]);
    const handleCancel = useCallback(() => { processAiRequest('NO', [...messages, { role: 'user', text: 'NO' }]); }, [messages]);

    function isConfirmationRequest(text) {
        return text && (text.includes("Confirmation Required") || text.includes("Are you sure?"));
    }

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
                            {messages.map((msg, idx) => {
                                const msgType = msg.role === 'assistant' ? getMessageType(msg.text) : 'user';

                                return (
                                    <div key={idx} className={cn("flex flex-col max-w-[90%]", msg.role === 'user' ? "ml-auto items-end" : "mr-auto items-start")}>
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
                                                    msgType === 'confirmation' && "bg-slate-900 border border-cyan-800/40 text-slate-200",
                                                    msgType === 'normal' && "bg-slate-900 border border-slate-800 text-slate-200"
                                                )
                                        )}>
                                            {/* Status icon for special messages */}
                                            {msgType === 'rate_limit' && (
                                                <div className="flex items-center gap-2 mb-2 pb-2 border-b border-amber-800/30">
                                                    <Clock size={14} className="text-amber-400" />
                                                    <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Rate Limited</span>
                                                </div>
                                            )}
                                            {msgType === 'timeout' && (
                                                <div className="flex items-center gap-2 mb-2 pb-2 border-b border-amber-800/30">
                                                    <Clock size={14} className="text-amber-400" />
                                                    <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Timed Out</span>
                                                </div>
                                            )}
                                            {msgType === 'error' && (
                                                <div className="flex items-center gap-2 mb-2 pb-2 border-b border-red-800/30">
                                                    <XCircle size={14} className="text-red-400" />
                                                    <span className="text-[10px] font-bold uppercase tracking-wider text-red-400">Error</span>
                                                </div>
                                            )}

                                            <RenderMarkdown text={msg.text} />

                                            {msg.type === 'disambiguation' && (
                                                <DisambiguationCard
                                                    options={msg.options}
                                                    action={msg.action}
                                                    isLatest={idx === messages.length - 1 && processingStep === 'idle'}
                                                    onSelect={(selected) => {
                                                        const confirmText = `CONFIRMED: ${msg.action} — specifically '${selected}'`;
                                                        const newMsgs = [...messages, { role: 'user', text: confirmText }];
                                                        setMessages(newMsgs);
                                                        processAiRequest(confirmText, newMsgs);
                                                    }}
                                                    onCancel={() => {
                                                        const cancelMsg = "🚫 Action cancelled.";
                                                        setMessages([...messages, { role: 'assistant', text: cancelMsg, errorType: 'cancelled' }]);
                                                    }}
                                                />
                                            )}
                                        </div>

                                        {/* CONFIRMATION BUTTONS */}
                                        {msg.role === 'assistant' && idx === messages.length - 1 && isConfirmationRequest(msg.text) && processingStep === 'idle' && (
                                            <div className="flex gap-2 mt-3 animate-in fade-in slide-in-from-top-2">
                                                <Button
                                                    ref={confirmBtnRef}
                                                    size="sm"
                                                    className="bg-green-600 hover:bg-green-700 text-white h-9 gap-1.5 px-4 shadow-lg shadow-green-900/20"
                                                    onClick={handleConfirm}
                                                >
                                                    <CheckCircle2 size={14} /> Confirm
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    className="h-9 text-slate-400 border-slate-700 hover:bg-slate-800 hover:text-red-400 gap-1.5 px-4"
                                                    onClick={handleCancel}
                                                >
                                                    <XCircle size={14} /> Cancel
                                                </Button>
                                                <span className="text-[10px] text-slate-600 self-center ml-1">Enter / Esc</span>
                                            </div>
                                        )}
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