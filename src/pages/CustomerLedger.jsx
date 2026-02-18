import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Virtuoso } from 'react-virtuoso'; 
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import { Search, Download, Edit2, Trash2, Loader2, Save, Calendar, ChevronRight } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

const PAGE_SIZE = 50; 

export default function CustomerLedger() {
    // RENAME/UPDATE STATE
    const [customers, setCustomers] = useState([]);
    const [loading, setLoading] = useState(true);
    
    // --- ADD PAGINATION STATE ---
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    
    // --- DEBOUNCE STATE SPLIT ---
    const [inputValue, setInputValue] = useState(""); // What the user types (Instant)
    const [searchQuery, setSearchQuery] = useState(""); // What filters the list (Lagged)
    
    // --- KEYBOARD NAV STATE ---
    const [highlightedIndex, setHighlightedIndex] = useState(0);
    const listRef = useRef(null);
    const searchInputRef = useRef(null);
    const navigate = useNavigate();
    // ----------------------------

    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");
    const [editOpen, setEditOpen] = useState(false);
    const [deleteOpen, setDeleteOpen] = useState(false);
    const [selectedCustomer, setSelectedCustomer] = useState(null);
    const [formData, setFormData] = useState({ name: "", mobile: "", address: "" });

    useEffect(() => { loadCustomers(); }, []);

    // --- DEBOUNCE LOGIC ---
    useEffect(() => {
        const handler = setTimeout(() => {
            // Trigger a fresh load (reset=true) when user types
            loadCustomers(true);
        }, 300);

        return () => clearTimeout(handler);
    }, [inputValue]);
    // ----------------------

    // REPLACE existing loadCustomers with this:
    const loadCustomers = async (reset = false) => {
        // Prevent duplicate fetches
        if (!reset && (loadingMore || !hasMore)) return;

        if (reset) {
            setLoading(true);
            setPage(1);
            setHasMore(true);
            setHighlightedIndex(0);
        } else {
            setLoadingMore(true);
        }

        try {
            const offset = reset ? 0 : page * PAGE_SIZE;
            
            // Use the search query directly in the API call
            const res = await window.api.getCustomersPaginated(PAGE_SIZE, offset, inputValue);
            
            // Handle different response structures safely
            const data = (res?.data && Array.isArray(res.data)) ? res.data : (Array.isArray(res) ? res : []);

            if (reset) {
                setCustomers(data);
                setLoading(false);
            } else {
                setCustomers(prev => [...prev, ...data]);
                setLoadingMore(false);
            }

            // Check if we reached the end
            if (data.length < PAGE_SIZE) {
                setHasMore(false);
            } else {
                setPage(prev => (reset ? 1 : prev + 1));
            }
        } catch (error) {
            toast.error("Failed to load customers");
            setLoading(false);
            setLoadingMore(false);
        } 
    };

    

    // --- KEYBOARD HANDLER ---
    const handleKeyDown = (e) => {
        if (customers.length === 0) return;

        if (e.key === "ArrowDown") {
            e.preventDefault();
            setHighlightedIndex(prev => {
                const next = Math.min(prev + 1, customers.length - 1);
                listRef.current?.scrollIntoView({ index: next, behavior: 'auto' });
                return next;
            });
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setHighlightedIndex(prev => {
                const next = Math.max(prev - 1, 0);
                listRef.current?.scrollIntoView({ index: next, behavior: 'auto' });
                return next;
            });
        } else if (e.key === "Enter") {
            e.preventDefault();
            const selected = customers[highlightedIndex];
            if (selected) {
                navigate(`/customer/${selected.id}`);
            }
        }
    };

    const handleDownload = async () => {
        const toastId = toast.loading("Exporting Ledger...");
        try {
            const result = await window.api.exportLedger(dateFrom, dateTo);
            if (result.canceled) { toast.dismiss(toastId); return; }
            if (result.error) throw new Error(result.error);
            toast.update(toastId, { render: "Export Saved!", type: "success", isLoading: false, autoClose: 3000 });
        } catch (e) { toast.update(toastId, { render: "Export failed", type: "error", isLoading: false, autoClose: 3000 }); }
    };

    const openEdit = (c, e) => { e.stopPropagation(); setSelectedCustomer(c); setFormData({ name: c.name, mobile: c.mobile || "", address: c.address || "" }); setEditOpen(true); };
    const openDelete = (c, e) => { e.stopPropagation(); setSelectedCustomer(c); setDeleteOpen(true); };
    
    const handleUpdate = async () => { 
        if (!formData.name) return toast.warning("Name required");
        try {
            await window.api.updateCustomer({ id: selectedCustomer.id, ...formData });
            toast.success("Updated"); 
            setEditOpen(false); 
            setCustomers(prev => prev.map(c => c.id === selectedCustomer.id ? { ...c, ...formData } : c));
        } catch(e) { toast.error("Update failed"); }
    };
    
    const handleDelete = async () => {
        try {
            await window.api.deleteCustomer(selectedCustomer.id);
            toast.success("Deleted"); 
            setDeleteOpen(false); 
            setCustomers(prev => prev.filter(c => c.id !== selectedCustomer.id));
        } catch(e) { toast.error("Delete failed"); }
    };

    // --- ROW RENDERER (Standardized) ---
    const rowContent = (index, c) => {
        const isHighlighted = index === highlightedIndex;
        
        return (
            <div 
                onClick={() => navigate(`/customer/${c.id}`)}
                className={`
                    flex items-center justify-between px-6 py-3 border-b border-border cursor-pointer transition-colors
                    ${isHighlighted ? 'bg-accent text-accent-foreground' : 'hover:bg-muted/50'}
                `}
            >
                <div className="w-[80px] font-mono text-xs text-muted-foreground">#{c.id}</div>
                <div className="flex-1 pr-4 min-w-0">
                    <span className="font-medium text-sm text-foreground truncate block">
                        {c.name}
                    </span>
                </div>
                <div className="flex-1 flex flex-col justify-center min-w-0">
                    <span className="text-foreground text-sm truncate">{c.mobile || "—"}</span>
                    <span className="text-muted-foreground text-xs truncate max-w-[200px]">{c.address}</span>
                </div>
                <div className="w-[120px] text-right">
                    {c.balance > 0 ? ( 
                        <Badge variant="outline" className="text-destructive border-destructive/50 bg-destructive/10">Due: ₹{Number(c.balance).toFixed(2)}</Badge> 
                    ) : c.balance < 0 ? (
                        <Badge variant="outline" className="text-emerald-700 border-emerald-200 bg-emerald-50">Adv: ₹{Math.abs(Number(c.balance)).toFixed(2)}</Badge>
                    ) : ( 
                        <span className="text-muted-foreground text-sm">₹0.00</span> 
                    )}
                </div>
                <div className="w-[120px] flex justify-end gap-1 items-center">
                     <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:text-primary" onClick={(e) => openEdit(c, e)}><Edit2 size={14} /></Button>
                     <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:text-destructive" onClick={(e) => openDelete(c, e)}><Trash2 size={14} /></Button>
                     {isHighlighted && <ChevronRight size={16} className="text-muted-foreground ml-1 animate-in fade-in"/>}
                </div>
            </div>
        );
    };

    return (
        <div className="max-w-[1600px] mx-auto space-y-6 animate-in fade-in duration-500 pb-10 h-[calc(100vh-40px)] flex flex-col p-6">
            
            {/* Header (Unboxed) */}
            <div className="flex flex-col md:flex-row justify-between items-end gap-4 flex-shrink-0">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground">Customer Ledger</h1>
                    <p className="text-muted-foreground mt-1">Directory of all {customers.length} customers.</p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                    {/* Date Picker Group */}
                    <div className="flex items-center gap-2 bg-background p-1 rounded-md border border-input shadow-sm">
                        <Calendar size={14} className="ml-2 text-muted-foreground"/>
                        <input 
                            type="date" 
                            className="bg-transparent text-sm p-1 outline-none text-foreground h-8" 
                            value={dateFrom} 
                            onChange={e => setDateFrom(e.target.value)} 
                        />
                        <span className="text-muted-foreground">-</span>
                        <input 
                            type="date" 
                            className="bg-transparent text-sm p-1 outline-none text-foreground h-8" 
                            value={dateTo} 
                            onChange={e => setDateTo(e.target.value)} 
                        />
                    </div>
                    <Button variant="outline" onClick={handleDownload} className="h-10 gap-2">
                        <Download size={16}/> Export Full DB
                    </Button>
                </div>
            </div>

            {/* Search Bar */}
            <div className="relative max-w-md flex-shrink-0">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
                <Input 
                    ref={searchInputRef}
                    placeholder="Search by name or mobile... (Use Arrow Keys)" 
                    className="pl-10 h-10 shadow-sm" 
                    value={inputValue} 
                    onChange={e => setInputValue(e.target.value)} 
                    onKeyDown={handleKeyDown}
                    autoFocus
                />
            </div>

            {/* List */}
            <div className="flex-1 border border-border rounded-md overflow-hidden shadow-sm bg-background flex flex-col min-h-[400px]">
                {/* List Header */}
                <div className="flex items-center justify-between px-6 py-3 bg-muted/30 text-xs font-medium text-muted-foreground border-b border-border flex-shrink-0">
                    <div className="w-[80px]">ID</div>
                    <div className="flex-1">Customer Name</div>
                    <div className="flex-1">Contact</div>
                    <div className="w-[120px] text-right">Balance</div>
                    <div className="w-[120px] text-right">Actions</div>
                </div>
                
                <div className="flex-1 w-full h-full bg-background">
                    {loading && customers.length === 0 ? (
                        <div className="flex justify-center items-center h-full gap-2 text-muted-foreground">
                            <Loader2 className="animate-spin" size={24}/> Loading directory...
                        </div>
                    ) : customers.length === 0 ? (
                        <div className="flex justify-center items-center h-full text-muted-foreground">No customers found.</div>
                    ) : (
                        <Virtuoso 
                            ref={listRef}
                            style={{ height: '100%' }} 
                            data={customers} 
                            itemContent={rowContent}

                            endReached={() => loadCustomers(false)}
                            components={{
                                Footer: () => loadingMore ? (
                                    <div className="py-4 flex justify-center text-sm text-muted-foreground border-t">
                                        <Loader2 className="animate-spin mr-2 h-4 w-4" /> Loading more...
                                    </div>
                                ) : null
                            }}
                        />
                    )}
                </div>
            </div>

            {/* Edit Dialog */}
            <Dialog open={editOpen} onOpenChange={setEditOpen}>
                <DialogContent>
                    <DialogHeader><DialogTitle>Edit Customer</DialogTitle></DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid gap-2"><Label>Full Name</Label><Input value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} /></div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="grid gap-2"><Label>Mobile</Label><Input value={formData.mobile} onChange={e => setFormData({...formData, mobile: e.target.value})} /></div>
                            <div className="grid gap-2"><Label>Address</Label><Input value={formData.address} onChange={e => setFormData({...formData, address: e.target.value})} /></div>
                        </div>
                    </div>
                    <DialogFooter><Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button><Button onClick={handleUpdate}><Save size={16} className="mr-2"/> Save Changes</Button></DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Dialog */}
            <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
                <DialogContent>
                    <DialogHeader><DialogTitle className="text-destructive flex items-center gap-2"><Trash2 size={16}/> Delete Customer?</DialogTitle><DialogDescription>Are you sure? This removes all history.</DialogDescription></DialogHeader>
                    <DialogFooter><Button variant="outline" onClick={() => setDeleteOpen(false)}>Cancel</Button><Button variant="destructive" onClick={handleDelete}>Delete Customer</Button></DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}