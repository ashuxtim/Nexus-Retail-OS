import React, { useState, useEffect, useRef, useMemo } from "react";
import { toast } from "react-toastify";
import { 
  UserPlus, 
  Wallet, 
  ArrowRight, 
  Loader2, 
  Search, 
  X, 
  Check, 
  Users,
  CreditCard 
} from "lucide-react";

// --- SHADCN IMPORTS ---
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

// --- Safer Polyfill for Electron/Toastify ---
if (typeof window !== 'undefined') {
    if (!("dragEvent" in window)) {
        Object.defineProperty(window, "dragEvent", { get: () => undefined });
    }
}

const FETCH_LIMIT = 20000;

// --- Refined Smart Search (Standardized) ---
function SmartCustomerSearch({ onSelect, selectedName, data }) {
    const [query, setQuery] = useState("");
    const [isOpen, setIsOpen] = useState(false);
    const [highlightedIndex, setHighlightedIndex] = useState(0);
    const wrapperRef = useRef(null);
    const listRef = useRef(null); 

    useEffect(() => {
        function handleClickOutside(event) {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target)) setIsOpen(false);
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const results = useMemo(() => {
        if (!query) return [];
        const lowerQuery = query.toLowerCase();

        const matches = data.filter(c => {
            const name = c.name?.toLowerCase() || "";
            const mobile = c.mobile?.toString() || "";
            return name.includes(lowerQuery) || mobile.includes(lowerQuery);
        });

        return matches.sort((a, b) => {
            const aName = a.name.toLowerCase();
            const bName = b.name.toLowerCase();
            if (aName.startsWith(lowerQuery) && !bName.startsWith(lowerQuery)) return -1; 
            if (!aName.startsWith(lowerQuery) && bName.startsWith(lowerQuery)) return 1;  
            return aName.localeCompare(bName);  
        }).slice(0, 10);
    }, [data, query]);

    useEffect(() => { setHighlightedIndex(0); }, [results]);

    useEffect(() => {
        if (isOpen && listRef.current && listRef.current.children[highlightedIndex]) {
            listRef.current.children[highlightedIndex].scrollIntoView({ block: 'nearest' });
        }
    }, [highlightedIndex, isOpen]);

    const handleSelect = (c) => {
        onSelect(c);
        setIsOpen(false);
        setQuery("");
    };

    const handleKeyDown = (e) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setHighlightedIndex(prev => (prev + 1) % results.length);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setHighlightedIndex(prev => (prev - 1 + results.length) % results.length);
        } else if (e.key === 'Enter' && isOpen && results.length > 0) {
            e.preventDefault();
            handleSelect(results[highlightedIndex]);
        } else if (e.key === 'Escape') {
            setIsOpen(false);
        }
    };

    return (
        <div className="relative" ref={wrapperRef}>
            <div className="relative">
                {/* Visual Update: Neutral Enterprise Style */}
                <Input 
                    placeholder={selectedName || "Search by Name or Mobile..."} 
                    value={query} 
                    onChange={e => { setQuery(e.target.value); setIsOpen(true); }}
                    onFocus={() => { if(query) setIsOpen(true); }}
                    onKeyDown={handleKeyDown}
                    className={cn(
                        "pl-9 h-10 shadow-sm transition-colors",
                        selectedName ? "font-medium" : "bg-background"
                    )}
                />
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                {selectedName && (
                    <button onClick={() => onSelect(null)} className="absolute right-3 top-2.5 text-muted-foreground hover:text-destructive">
                        <X size={16}/>
                    </button>
                )}
            </div>
            {isOpen && results.length > 0 && (
                <div ref={listRef} className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-lg shadow-xl max-h-48 overflow-auto animate-in fade-in zoom-in-95">
                    {results.map((c, i) => (
                        <div 
                            key={c.id} 
                            className={cn(
                                "p-3 text-sm cursor-pointer border-b border-border last:border-0 flex justify-between group transition-colors",
                                i === highlightedIndex ? "bg-accent text-accent-foreground" : "hover:bg-muted/50"
                            )}
                            onClick={() => handleSelect(c)}
                        >
                            <span className={cn("font-medium", i === highlightedIndex ? "text-foreground" : "text-muted-foreground")}>
                                {c.name}
                            </span>
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground">{c.mobile}</span>
                                {i === highlightedIndex && <Check size={14} className="text-primary"/>}
                            </div>
                        </div>
                    ))}
                </div>
            )}
            {isOpen && query && results.length === 0 && (
                 <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-lg shadow-xl p-3 text-center text-xs text-muted-foreground">
                     No matching customers found.
                 </div>
            )}
        </div>
    );
}

export default function CustomerPage() {
    const [allCustomers, setAllCustomers] = useState([]);
    const [loadingData, setLoadingData] = useState(true);

    const [newName, setNewName] = useState("");
    const [newMobile, setNewMobile] = useState("");
    const [newAddress, setNewAddress] = useState("");
    const [isAdding, setIsAdding] = useState(false);

    const [selectedCustomer, setSelectedCustomer] = useState(null);
    const [payAmount, setPayAmount] = useState("");
    const [isPaying, setIsPaying] = useState(false);

    useEffect(() => {
        const fetchAll = async () => {
            setLoadingData(true);
            try {
                const res = await window.api.getCustomersPaginated(FETCH_LIMIT, 0, "");
                let data = (res?.data && Array.isArray(res.data)) ? res.data : (Array.isArray(res) ? res : []);
                setAllCustomers(data.sort((a,b) => a.name.localeCompare(b.name)));
            } catch (e) {
                console.error(e);
                toast.error("Failed to load customer directory.");
            } finally {
                setLoadingData(false);
            }
        };
        fetchAll();
    }, []);

    const handleAdd = async () => {
        if (!newName) return toast.warning("Name required");
        setIsAdding(true);
        try {
            const res = await window.api.createCustomer({ name: newName, mobile: newMobile, address: newAddress });
            if (res.error) throw new Error(res.error);
            toast.success("Customer Created!");
            setAllCustomers(prev => [...prev, res].sort((a,b) => a.name.localeCompare(b.name)));
            setNewName(""); setNewMobile(""); setNewAddress("");
        } catch (e) { toast.error(e.message); }
        finally { setIsAdding(false); }
    };

    const handlePay = async () => {
        if (!selectedCustomer || !payAmount) return;
        setIsPaying(true);
        try {
            await window.api.createPayment({ customerId: Number(selectedCustomer.id), amount: Number(payAmount) });
            toast.success("Payment Recorded!");
            const newBalance = (selectedCustomer.balance || 0) - Number(payAmount);
            setSelectedCustomer(prev => ({ ...prev, balance: newBalance }));
            setAllCustomers(prev => prev.map(c => c.id === selectedCustomer.id ? { ...c, balance: newBalance } : c));
            setPayAmount(""); 
        } catch (e) { toast.error(e.message); }
        finally { setIsPaying(false); }
    };

    if (loadingData) return <div className="h-[calc(100vh-4rem)] flex flex-col items-center justify-center space-y-4"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /><p className="text-muted-foreground font-medium">Loading Customer Directory...</p></div>;

    return (
        <div className="max-w-[1600px] mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500 p-6 pb-20">
            
            {/* --- HEADER (UNBOXED) --- */}
            <div className="flex flex-col md:flex-row justify-between items-end gap-4 flex-shrink-0">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground">Customer Actions</h1>
                    <p className="text-muted-foreground mt-1">Register new customers or record balance payments.</p>
                </div>
                <Button variant="outline" asChild className="gap-2 shadow-sm h-9">
                    <Link to="/ledger">
                        <Users size={16}/> View Full Ledger <ArrowRight size={16}/>
                    </Link>
                </Button>
            </div>

            {/* --- 2-COLUMN GRID --- */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                
                {/* 1. New Customer Card */}
                <Card className="shadow-sm border-border flex flex-col">
                    <CardHeader className="pb-3 border-b border-border">
                        <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
                            <UserPlus size={16} className="text-muted-foreground"/>
                            New Customer
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4 pt-6 flex-1">
                        <div className="space-y-2">
                            <Label className="text-xs font-medium text-muted-foreground">Full Name</Label>
                            <Input 
                                className="h-10 shadow-sm"
                                placeholder="e.g. Rahul Kumar" 
                                value={newName} 
                                onChange={e => setNewName(e.target.value)} 
                            />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label className="text-xs font-medium text-muted-foreground">Mobile</Label>
                                <Input 
                                    className="h-10 shadow-sm"
                                    placeholder="10 digits" 
                                    value={newMobile} 
                                    onChange={e => setNewMobile(e.target.value)} 
                                />
                            </div>
                            <div className="space-y-2">
                                <Label className="text-xs font-medium text-muted-foreground">Address</Label>
                                <Input 
                                    className="h-10 shadow-sm"
                                    placeholder="Area/City" 
                                    value={newAddress} 
                                    onChange={e => setNewAddress(e.target.value)} 
                                />
                            </div>
                        </div>
                        <div className="pt-2">
                            <Button 
                                className="w-full h-10 shadow-sm" 
                                disabled={isAdding} 
                                onClick={handleAdd}
                            >
                                {isAdding ? <Loader2 className="animate-spin mr-2" size={16}/> : "Create Customer Profile"}
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* 2. Record Payment Card */}
                <Card className="shadow-sm border-border flex flex-col">
                    <CardHeader className="pb-3 border-b border-border">
                        <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
                            <Wallet size={16} className="text-muted-foreground"/>
                            Record Payment
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4 pt-6 flex-1">
                        <div className="space-y-2">
                            <Label className="text-xs font-medium text-muted-foreground">Select Customer</Label>
                            <SmartCustomerSearch 
                                data={allCustomers} 
                                selectedName={selectedCustomer?.name} 
                                onSelect={setSelectedCustomer}
                            />
                        </div>
                        
                        <div className="p-4 bg-muted/20 rounded-lg border border-border flex justify-between items-center">
                            <span className="text-sm font-medium text-muted-foreground">Current Balance</span>
                            {selectedCustomer ? (
                                <Badge 
                                    variant="outline" 
                                    className={cn(
                                        "text-base px-3 py-1 bg-background",
                                        (selectedCustomer.balance||0) > 0 
                                            ? "text-destructive border-destructive/50" 
                                            : "text-emerald-600 border-emerald-200"
                                    )}
                                >
                                    ₹{(selectedCustomer.balance || 0).toFixed(2)}
                                </Badge>
                            ) : (
                                <span className="text-muted-foreground font-mono">--</span>
                            )}
                        </div>

                        <div className="space-y-2">
                            <Label className="text-xs font-medium text-muted-foreground">Amount Received (₹)</Label>
                            <div className="relative">
                                <CreditCard className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground"/>
                                <Input 
                                    type="number" 
                                    className="pl-10 font-bold text-lg h-12 shadow-sm" 
                                    placeholder="0.00" 
                                    value={payAmount} 
                                    onChange={e => setPayAmount(e.target.value)}
                                />
                            </div>
                        </div>

                        <div className="pt-2">
                            <Button 
                                className="w-full h-10 shadow-sm" 
                                disabled={isPaying || !selectedCustomer} 
                                onClick={handlePay}
                            >
                                {isPaying ? <Loader2 className="animate-spin mr-2" size={16}/> : "Save Payment Entry"}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}