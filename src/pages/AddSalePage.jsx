import React, { useState, useEffect, useRef, useMemo } from 'react';
import { toast } from 'react-toastify';
import {
    Plus, Save, Trash2, Printer, Search, X, User, Package,
    History, Loader2, Calendar, Check, RefreshCw, AlertTriangle,
    UserPlus, ShoppingCart, CreditCard
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";

// --- Polyfill ---
if (typeof window !== 'undefined') {
    if (!("dragEvent" in window)) {
        Object.defineProperty(window, "dragEvent", { get: () => undefined });
    }
}

const FETCH_LIMIT = 20000;

// --- PRINT CONTENT (UNCHANGED) ---
const PrintReceiptContent = React.forwardRef(({ data, storeConfig }, ref) => {
    if (!data) return null;
    return (
        <div ref={ref} className="p-8 font-mono text-black bg-white w-full max-w-[800px] mx-auto">
            <div className="text-center mb-4 border-b pb-2 border-black">
                <h1 className="text-xl font-bold">{storeConfig?.name || "NEXUS RETAIL OS"}</h1>
                {storeConfig?.address && <p className="text-xs">{storeConfig.address}</p>}
                {storeConfig?.phone && <p className="text-xs">Ph: {storeConfig.phone}</p>}
                {storeConfig?.gst && <p className="text-xs">GST: {storeConfig.gst}</p>}
                <p className="text-sm mt-1">Sales Receipt</p>
            </div>
            <div className="flex justify-between text-xs mb-4">
                <span>Date: {data.date}</span>
                <span>ID: {data.id}</span>
            </div>
            <div className="mb-4 text-sm font-bold border-b border-black pb-2">
                Cust: {data.customerName}
            </div>
            <table className="w-full text-xs mb-4">
                <thead>
                    <tr className="border-b border-black text-left">
                        <th className="py-1">Item</th>
                        <th className="text-right">Qty</th>
                        <th className="text-right">Price</th>
                        <th className="text-right">Amt</th>
                    </tr>
                </thead>
                <tbody>
                    {data.items.map((item, i) => (
                        <tr key={i}>
                            <td className="py-1">{item.name}</td>
                            <td className="text-right">{item.qty}</td>
                            <td className="text-right">{Number(item.price).toFixed(2)}</td>
                            <td className="text-right">{Number(item.qty * item.price).toFixed(2)}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
            <div className="flex justify-between font-bold text-sm border-t-2 border-black pt-2">
                <span>TOTAL</span>
                <span>₹{Number(data.total || 0).toFixed(2)}</span>
            </div>
            <div className="text-center mt-8 text-xs">{storeConfig?.footerMessage || "Thank You!"}</div>
        </div>
    );
});

// --- Smart Search Select (UPDATED FOR LOADING STATE) ---
function SmartSearchSelect({
    placeholder, data, onSelect, valueDisplay, labelKey, subLabelKey,
    nextRef, allowCreate = false, onCreate, isLoading
}) {
    const [query, setQuery] = useState("");
    const [isOpen, setIsOpen] = useState(false);
    const [highlightedIndex, setHighlightedIndex] = useState(0);
    const wrapperRef = useRef(null);
    const inputRef = useRef(null);
    const listRef = useRef(null);

    useEffect(() => {
        function handleClickOutside(event) { if (wrapperRef.current && !wrapperRef.current.contains(event.target)) setIsOpen(false); }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const results = useMemo(() => {
        if (!query) return [];
        const lowerQuery = query.toLowerCase();

        const matches = data.filter(item => {
            const mainLabel = item[labelKey]?.toString().toLowerCase() || "";
            const subLabel = item[subLabelKey]?.toString().toLowerCase() || "";
            return mainLabel.includes(lowerQuery) || subLabel.includes(lowerQuery);
        });

        const sorted = matches.sort((a, b) => {
            const aLabel = a[labelKey]?.toString().toLowerCase() || "";
            const bLabel = b[labelKey]?.toString().toLowerCase() || "";
            if (aLabel.startsWith(lowerQuery) && !bLabel.startsWith(lowerQuery)) return -1;
            if (!aLabel.startsWith(lowerQuery) && bLabel.startsWith(lowerQuery)) return 1;
            return aLabel.localeCompare(bLabel);
        }).slice(0, 50);

        if (allowCreate && query.trim().length > 0) {
            sorted.push({ _special: 'create', [labelKey]: `+ Add New: "${query}"`, [subLabelKey]: "Create and select this customer", rawQuery: query });
        }

        return sorted;
    }, [data, query, labelKey, subLabelKey, allowCreate]);

    useEffect(() => { setHighlightedIndex(0); }, [results]);

    useEffect(() => {
        if (isOpen && listRef.current && listRef.current.children[highlightedIndex]) {
            listRef.current.children[highlightedIndex].scrollIntoView({ block: 'nearest' });
        }
    }, [highlightedIndex, isOpen]);

    const handleSelect = (item) => {
        if (item._special === 'create') { onCreate(item.rawQuery); setIsOpen(false); setQuery(""); }
        else { onSelect(item); setIsOpen(false); setQuery(""); if (nextRef && nextRef.current) setTimeout(() => nextRef.current.focus(), 50); }
    };

    const handleKeyDown = (e) => {
        if (e.key === "ArrowDown") { e.preventDefault(); setHighlightedIndex(prev => (prev + 1) % results.length); }
        else if (e.key === "ArrowUp") { e.preventDefault(); setHighlightedIndex(prev => (prev - 1 + results.length) % results.length); }
        else if (e.key === "Enter" && isOpen && results.length > 0) { e.preventDefault(); handleSelect(results[highlightedIndex]); }
        else if (e.key === "Escape") { setIsOpen(false); }
    };

    return (
        <div className="relative" ref={wrapperRef}>
            <div className="relative">
                <Input
                    ref={inputRef}
                    placeholder={valueDisplay || placeholder}
                    value={query}
                    onChange={e => { setQuery(e.target.value); setIsOpen(true); }}
                    onFocus={() => { if (query || data.length > 0) setIsOpen(true); }}
                    onKeyDown={handleKeyDown}
                    className={`pl-9 shadow-sm ${valueDisplay ? "font-medium" : ""}`}
                    disabled={isLoading}
                />

                {/* CONDITIONAL ICON: Spinner if loading, Search if ready */}
                {isLoading ? (
                    <Loader2 className="absolute left-3 top-2.5 h-4 w-4 animate-spin text-muted-foreground" />
                ) : (
                    <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                )}

                {valueDisplay && <button onClick={() => { onSelect(null); setTimeout(() => inputRef.current?.focus(), 50); }} className="absolute right-3 top-2.5 text-muted-foreground hover:text-destructive transition-colors"><X size={16} /></button>}
            </div>
            {isOpen && results.length > 0 && (
                <div ref={listRef} className="absolute z-50 w-full mt-1 bg-popover border rounded-md shadow-md max-h-60 overflow-auto animate-in fade-in zoom-in-95">
                    {results.map((item, i) => (
                        <div
                            key={i}
                            className={`p-3 text-sm cursor-pointer border-b border-border last:border-0 flex justify-between group transition-colors ${i === highlightedIndex ? 'bg-accent text-accent-foreground' : 'hover:bg-muted/50'
                                }`}
                            onClick={() => handleSelect(item)}
                        >
                            <div className="flex flex-col">
                                <span className={`font-medium ${item._special ? "text-primary flex items-center gap-2" : "text-foreground"}`}>
                                    {item._special && <UserPlus size={14} />} {item[labelKey]}
                                </span>
                                <span className="text-xs text-muted-foreground">{item[subLabelKey]}</span>
                            </div>
                            {item.price !== undefined && (
                                <div className="flex items-center gap-2">
                                    <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded flex items-center border border-border">₹{item.price}</span>
                                    {i === highlightedIndex && <Check size={14} className="text-primary" />}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

export default function AddSalePage() {
    const [loadingData, setLoadingData] = useState(true);
    const [allCustomers, setAllCustomers] = useState([]);
    const [allProducts, setAllProducts] = useState([]);

    // --- LAZY INITIALIZATION FROM STORAGE (Fixes 0.1s blocking) ---
    const [mode, setMode] = useState(() => {
        if (typeof window === 'undefined') return "existing";
        return localStorage.getItem('pos_mode') || "existing";
    });

    const [selectedCustomer, setSelectedCustomer] = useState(() => {
        if (typeof window === 'undefined') return null;
        try {
            const saved = localStorage.getItem('pos_customer');
            return saved ? JSON.parse(saved) : null;
        } catch (e) { return null; }
    });

    const [cart, setCart] = useState(() => {
        if (typeof window === 'undefined') return [];
        try {
            const saved = localStorage.getItem('pos_cart');
            return saved ? JSON.parse(saved) : [];
        } catch (e) { return []; }
    });
    // -------------------------------------------------------------

    const [newCustomer, setNewCustomer] = useState({ name: "", mobile: "", address: "" });
    const [selectedVariant, setSelectedVariant] = useState(null);
    const [qty, setQty] = useState(1);
    const [price, setPrice] = useState("");

    const [paidNow, setPaidNow] = useState("");
    const [promiseDate, setPromiseDate] = useState("");

    const [paymentMode, setPaymentMode] = useState("Cash");
    const [storeConfig, setStoreConfig] = useState(null);
    const [printData, setPrintData] = useState(null);
    const [isPreviewOpen, setIsPreviewOpen] = useState(false);

    const [isResetOpen, setIsResetOpen] = useState(false);

    const qtyRef = useRef(null);
    const priceRef = useRef(null);
    const addBtnRef = useRef(null);
    const mobileRef = useRef(null);

    useEffect(() => {
        const loadMasterData = async () => {
            setLoadingData(true);
            try {
                const custRes = await window.api.getCustomersPaginated(FETCH_LIMIT, 0, "");
                setAllCustomers((custRes?.data || []).sort((a, b) => a.name.localeCompare(b.name)));

                const prodRes = await window.api.getProducts({ page: 1, limit: FETCH_LIMIT, search: "" });
                const flatProducts = [];
                if (prodRes) prodRes.forEach(p => p.variants?.forEach(v => flatProducts.push({ ...v, full_name: `${p.name} - ${v.name}`, product_name: p.name, current_stock_label: `Stock: ${v.current_stock}` })));
                setAllProducts(flatProducts.sort((a, b) => a.full_name.localeCompare(b.full_name)));

                const settings = await window.api.getLocalSettings();
                if (settings) {
                    if (settings.store_config) setStoreConfig(settings.store_config);
                    if (settings.preferences?.defaultPaymentMode) setPaymentMode(settings.preferences.defaultPaymentMode);
                }

            } catch (e) { toast.error("Failed to load data."); } finally { setLoadingData(false); }
        };
        // Use timeout to ensure main thread renders UI first
        setTimeout(loadMasterData, 0);
    }, []);

    // Save state to LocalStorage
    useEffect(() => {
        localStorage.setItem('pos_cart', JSON.stringify(cart));
        if (selectedCustomer) localStorage.setItem('pos_customer', JSON.stringify(selectedCustomer));
        else localStorage.removeItem('pos_customer');
        localStorage.setItem('pos_mode', mode);
    }, [cart, selectedCustomer, mode]);

    useEffect(() => { if (selectedVariant) setPrice(selectedVariant.price); }, [selectedVariant]);

    const handleQuickCreate = (name) => {
        setMode("new");
        setNewCustomer(prev => ({ ...prev, name: name }));
        toast.info(`Creating: ${name}`, { autoClose: 2000, hideProgressBar: true });
        setTimeout(() => { if (mobileRef.current) mobileRef.current.focus(); }, 100);
    };

    const triggerReset = () => { if (cart.length > 0) setIsResetOpen(true); else performReset(); };

    const performReset = () => {
        setCart([]);
        setSelectedCustomer(null);
        setMode("existing");
        setPaidNow("");
        setPromiseDate("");
        setNewCustomer({ name: "", mobile: "", address: "" });
        localStorage.removeItem('pos_cart');
        localStorage.removeItem('pos_customer');
        localStorage.removeItem('pos_mode');
        setIsResetOpen(false);
        toast.info("Sale reset");
    };

    const addToCart = () => {
        if (!selectedVariant) return toast.warning("Select a product");

        const requestedQty = Number(qty);
        const availableStock = selectedVariant.current_stock ?? 0;

        // Check how much of this variant is already in cart
        const alreadyInCart = cart
            .filter(item => item.variant === selectedVariant.id)
            .reduce((sum, item) => sum + item.qty, 0);

        if (requestedQty + alreadyInCart > availableStock) {
            const remaining = Math.max(0, availableStock - alreadyInCart);
            return toast.error(
                `Insufficient stock for ${selectedVariant.full_name}. Available: ${availableStock}, In Cart: ${alreadyInCart}, Can add: ${remaining}`
            );
        }

        const newItem = {
            variant: selectedVariant.id,
            name: selectedVariant.full_name,
            qty: requestedQty,
            price: Number(price)
        };

        setCart(prev => {
            const existingIndex = prev.findIndex(item => item.variant === newItem.variant && item.price === newItem.price);
            if (existingIndex > -1) {
                const newCart = [...prev];
                newCart[existingIndex].qty += newItem.qty;
                return newCart;
            } else {
                return [...prev, newItem];
            }
        });

        setSelectedVariant(null); setQty(1); setPrice("");
    };

    const total = cart.reduce((sum, item) => sum + (item.qty * item.price), 0);
    const balanceToAdd = total - (Number(paidNow) || 0);
    const showDatePicker = balanceToAdd > 0;

    const triggerPrint = (data) => {
        setPrintData(data);
        setIsPreviewOpen(true);
    };

    const handlePrintCart = () => {
        if (cart.length === 0) return toast.warning("Cart is empty");
        triggerPrint({
            id: "DRAFT",
            date: new Date().toLocaleString(),
            customerName: mode === "new" ? newCustomer.name : (selectedCustomer?.name || "Walk-in"),
            items: cart,
            total: total
        });
    };

    const handleSubmit = async () => {
        if (cart.length === 0) return toast.error("Cart is empty");
        let finalCustomerId = selectedCustomer?.id;
        try {
            if (mode === "new") {
                if (!newCustomer.name) return toast.error("Name required");
                const res = await window.api.createCustomer(newCustomer);
                if (res.error) throw new Error(res.error);
                finalCustomerId = res.id;
            } else if (!finalCustomerId) return toast.error("Select customer");

            const itemsPayload = cart.map(i => ({ variant: i.variant, quantity: i.qty, price_at_sale: i.price }));
            const paidVal = Number(paidNow) || 0;

            const res = await window.api.createFullTransaction({
                customerId: Number(finalCustomerId),
                items: itemsPayload,
                paidAmount: paidVal,
                nextPaymentDate: showDatePicker ? promiseDate : null,
                paymentMode: paymentMode
            });

            if (res.error) throw new Error(res.error);

            toast.success("Sale Recorded!");
            window.dispatchEvent(new Event('refresh-notifications'));
            performReset();

        } catch (e) { toast.error(e.message); }
    };

    // Removed Blocking Return here to fix "0.1s delay"

    return (
        <div className="max-w-[1600px] mx-auto space-y-6 animate-in fade-in duration-500 p-6 pb-20">
            <div className="hidden print:block fixed inset-0 bg-white z-[9999] overflow-hidden">
                <PrintReceiptContent data={printData} storeConfig={storeConfig} />
            </div>

            {/* --- HEADER (UNBOXED & CLEAN) --- */}
            <div className="flex flex-col md:flex-row justify-between items-end gap-4 print:hidden">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground">New Sale</h1>
                    <p className="text-muted-foreground mt-1">POS Terminal & Billing</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="ghost" className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 h-9" onClick={triggerReset}>
                        <RefreshCw size={16} className="mr-2" /> Reset
                    </Button>
                    <Button variant="outline" className="h-9" onClick={handlePrintCart}>
                        <Printer size={16} className="mr-2" /> Draft Print
                    </Button>
                    <Button variant="outline" className="h-9" onClick={async () => { const last = await window.api.getLastSale(); if (last) triggerPrint({ id: "#" + last.id, date: last.sale_date, customerName: last.customer?.name, items: last.items.map(i => ({ name: i.variant_name || i.product_name, qty: i.quantity, price: i.price_at_sale })), total: last.items.reduce((s, i) => s + (i.quantity * i.price_at_sale), 0) }); }}>
                        <History size={16} className="mr-2" /> Reprint Last
                    </Button>
                </div>
            </div>

            {/* --- MAIN GRID --- */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 print:hidden">

                {/* --- LEFT COL (Forms) --- */}
                <div className="lg:col-span-4 space-y-6">
                    <Card className="shadow-sm border-border">
                        <CardHeader className="pb-3 border-b border-border">
                            <CardTitle className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-2">
                                <User size={16} className="text-muted-foreground" /> Customer Details
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-4">
                            <Tabs value={mode} onValueChange={setMode} className="w-full">
                                <TabsList className="grid w-full grid-cols-2 mb-4 h-9">
                                    <TabsTrigger value="existing" className="text-xs">Existing Customer</TabsTrigger>
                                    <TabsTrigger value="new" className="text-xs">New Walk-in</TabsTrigger>
                                </TabsList>
                                <TabsContent value="existing" className="space-y-3">
                                    <Label className="text-xs font-medium text-muted-foreground">Select Customer</Label>
                                    <SmartSearchSelect
                                        data={allCustomers}
                                        labelKey="name"
                                        subLabelKey="mobile"
                                        placeholder="Search by Name or Mobile..."
                                        valueDisplay={selectedCustomer?.name}
                                        onSelect={setSelectedCustomer}
                                        allowCreate={true}
                                        onCreate={handleQuickCreate}
                                        isLoading={loadingData} // Pass loading state
                                    />
                                </TabsContent>
                                <TabsContent value="new" className="space-y-3">
                                    <Input className="h-9 shadow-sm" placeholder="Full Name" value={newCustomer.name} onChange={e => setNewCustomer({ ...newCustomer, name: e.target.value })} />
                                    <Input className="h-9 shadow-sm" ref={mobileRef} placeholder="Mobile Number" value={newCustomer.mobile} onChange={e => setNewCustomer({ ...newCustomer, mobile: e.target.value })} />
                                    <Input className="h-9 shadow-sm" placeholder="Address / Area" value={newCustomer.address} onChange={e => setNewCustomer({ ...newCustomer, address: e.target.value })} />
                                </TabsContent>
                            </Tabs>
                        </CardContent>
                    </Card>

                    <Card className="shadow-sm border-border">
                        <CardHeader className="pb-3 border-b border-border">
                            <CardTitle className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-2">
                                <Package size={16} className="text-muted-foreground" /> Add Products
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4 pt-4">
                            <div className="space-y-2">
                                <Label className="text-xs font-medium text-muted-foreground">Product Search</Label>
                                <SmartSearchSelect
                                    data={allProducts}
                                    labelKey="full_name"
                                    subLabelKey="current_stock_label"
                                    placeholder="Scan barcode or type name..."
                                    valueDisplay={selectedVariant ? selectedVariant.full_name : ""}
                                    onSelect={setSelectedVariant}
                                    nextRef={qtyRef}
                                    isLoading={loadingData} // Pass loading state
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-xs font-medium text-muted-foreground">Quantity</Label>
                                    <Input className="h-10 shadow-sm" ref={qtyRef} type="number" value={qty} onChange={e => setQty(e.target.value)} onKeyDown={e => e.key === "Enter" && priceRef.current?.focus()} />
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-medium text-muted-foreground">Unit Price (₹)</Label>
                                    <Input className="h-10 shadow-sm" ref={priceRef} type="number" value={price} onChange={e => setPrice(e.target.value)} onKeyDown={e => e.key === "Enter" && addToCart()} />
                                </div>
                            </div>
                            <Button className="w-full" onClick={addToCart} ref={addBtnRef}>
                                <Plus size={16} className="mr-2" /> Add to Cart
                            </Button>
                        </CardContent>
                    </Card>
                </div>

                {/* --- RIGHT COL (Cart & Payment) --- */}
                <div className="lg:col-span-8 flex flex-col h-full gap-6">
                    <Card className="flex-1 shadow-sm border-border flex flex-col overflow-hidden">

                        {/* Cart Header (Standardized) */}
                        <div className="flex justify-between items-center px-6 py-4 border-b border-border">
                            <div className="flex items-center gap-2">
                                <ShoppingCart size={16} className="text-muted-foreground" />
                                <h3 className="font-semibold text-sm tracking-tight text-foreground">Current Order</h3>
                            </div>
                            <Badge variant="secondary" className="font-normal">{cart.length} items</Badge>
                        </div>

                        <div className="flex-1 p-0 overflow-auto min-h-[300px] max-h-[500px]">
                            <Table>
                                <TableHeader className="bg-muted/30 sticky top-0 z-10">
                                    <TableRow className="border-border hover:bg-transparent">
                                        <TableHead className="w-[40%] text-xs font-medium text-muted-foreground">Item Name</TableHead>
                                        <TableHead className="w-20 text-center text-xs font-medium text-muted-foreground">Qty</TableHead>
                                        <TableHead className="w-24 text-right text-xs font-medium text-muted-foreground">Price</TableHead>
                                        <TableHead className="w-24 text-right text-xs font-medium text-muted-foreground">Total</TableHead>
                                        <TableHead className="w-12"></TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {cart.length === 0 ? (
                                        <TableRow>
                                            <TableCell colSpan={5} className="h-48 text-center border-none">
                                                <div className="flex flex-col items-center justify-center text-muted-foreground gap-2">
                                                    <ShoppingCart size={32} className="opacity-20" />
                                                    <p className="text-sm">Cart is empty. Add items to begin.</p>
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    ) : (
                                        cart.map((item, i) => (
                                            <TableRow key={i} className="hover:bg-muted/50 border-border">
                                                <TableCell className="font-medium text-foreground py-3">{item.name}</TableCell>
                                                <TableCell className="text-center py-3 text-sm">{item.qty}</TableCell>
                                                <TableCell className="text-right py-3 text-muted-foreground text-sm">₹{Number(item.price).toFixed(2)}</TableCell>
                                                <TableCell className="text-right font-medium text-foreground py-3 text-sm">₹{(item.qty * item.price).toFixed(2)}</TableCell>
                                                <TableCell className="text-right py-3">
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10" onClick={() => setCart(c => c.filter((_, idx) => idx !== i))}>
                                                        <Trash2 size={14} />
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    )}
                                </TableBody>
                            </Table>
                        </div>

                        {/* Payment Footer (Cleaned Up) */}
                        <div className="p-6 bg-muted/10 border-t border-border space-y-5">
                            <div className="flex justify-between items-end">
                                <span className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Total Amount</span>
                                <span className="text-3xl font-bold text-foreground">₹{total.toFixed(2)}</span>
                            </div>

                            <Separator />

                            <div className="grid grid-cols-12 gap-6 items-start">
                                {/* Payment Inputs */}
                                <div className="col-span-12 md:col-span-8 grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label className="text-xs font-medium text-muted-foreground">Paid Now (₹)</Label>
                                        <div className="relative">
                                            {/* Neutral but emphasized input */}
                                            <Input
                                                type="number"
                                                placeholder="0.00"
                                                className="bg-background text-lg font-bold h-12 shadow-sm"
                                                value={paidNow}
                                                onChange={e => setPaidNow(e.target.value)}
                                            />
                                        </div>
                                    </div>

                                    <div className="space-y-2">
                                        <Label className="text-xs font-medium text-muted-foreground">Payment Mode</Label>
                                        <div className="relative">
                                            <select
                                                className="flex h-12 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 shadow-sm appearance-none"
                                                value={paymentMode}
                                                onChange={e => setPaymentMode(e.target.value)}
                                            >
                                                <option value="Cash">Cash</option>
                                                <option value="UPI">UPI</option>
                                                <option value="Card">Card</option>
                                            </select>
                                            <CreditCard className="absolute right-3 top-3.5 h-5 w-5 text-muted-foreground pointer-events-none" />
                                        </div>
                                    </div>

                                    {showDatePicker && (
                                        <div className="space-y-2 animate-in fade-in slide-in-from-top-2 col-span-2 bg-muted/30 p-3 rounded-lg border border-border">
                                            <Label className="text-xs font-semibold text-destructive flex items-center gap-2">
                                                <Calendar size={14} /> Due Amount: ₹{balanceToAdd.toFixed(2)}
                                            </Label>
                                            <div className="flex items-center gap-2 mt-1">
                                                <span className="text-xs text-muted-foreground">Promise Date:</span>
                                                <Input
                                                    type="date"
                                                    className="bg-background h-8 w-full"
                                                    value={promiseDate}
                                                    onChange={e => setPromiseDate(e.target.value)}
                                                />
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Complete Button */}
                                <div className="col-span-12 md:col-span-4 h-full">
                                    <Button size="lg" className="w-full h-full min-h-[48px] text-lg shadow-sm" onClick={handleSubmit}>
                                        <div className="flex flex-col items-center">
                                            <span className="flex items-center gap-2"><Check size={20} strokeWidth={3} /> Complete</span>
                                            {showDatePicker && <span className="text-[10px] opacity-80 font-normal">with credit due</span>}
                                        </div>
                                    </Button>
                                </div>
                            </div>
                        </div>
                    </Card>
                </div>
            </div>

            <Dialog open={isResetOpen} onOpenChange={setIsResetOpen}><DialogContent><DialogHeader><DialogTitle className="flex items-center gap-2 text-destructive"><AlertTriangle size={20} /> Reset Sale?</DialogTitle><DialogDescription>Are you sure you want to clear the current sale?</DialogDescription></DialogHeader><DialogFooter><Button variant="outline" onClick={() => setIsResetOpen(false)}>Cancel</Button><Button variant="destructive" onClick={performReset}>Confirm Reset</Button></DialogFooter></DialogContent></Dialog>
            <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}><DialogContent className="max-w-4xl h-[90vh] flex flex-col p-0 overflow-hidden"><DialogHeader className="p-4 border-b border-border flex-shrink-0"><DialogTitle>Print Preview</DialogTitle></DialogHeader><div className="flex-1 overflow-y-auto bg-muted/30 p-8 flex justify-center"><div className="shadow-xl bg-white scale-90 origin-top"><PrintReceiptContent data={printData} storeConfig={storeConfig} /></div></div><DialogFooter className="p-4 border-t border-border bg-background flex-shrink-0"><Button variant="outline" onClick={() => setIsPreviewOpen(false)}>Close</Button><Button onClick={() => window.print()} className="gap-2"><Printer size={16} /> Print Now</Button></DialogFooter></DialogContent></Dialog>
        </div>
    );
}