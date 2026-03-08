import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { Virtuoso } from 'react-virtuoso';
import {
    Search, Package, User, ShoppingBag, Truck, ArrowRight, Loader2,
    Eye, FileText, ArrowLeftRight, CornerDownLeft, PlusCircle, Command,
    ArrowUp, ArrowDown, UserPlus
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

// --- Safer Polyfill ---
if (typeof window !== 'undefined') {
    if (!("dragEvent" in window)) {
        Object.defineProperty(window, "dragEvent", { get: () => undefined });
    }
}

export default function SearchResultsPage() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const q = searchParams.get('q') || '';

    const [results, setResults] = useState({ products: [], customers: [], suppliers: [], sales: [], purchases: [] });
    const [loading, setLoading] = useState(false);

    // --- ZONE-BASED NAVIGATION STATE ---
    const [activeZoneIndex, setActiveZoneIndex] = useState(0);
    const [selectedItemIndex, setSelectedItemIndex] = useState(0);

    const containerRef = useRef(null);
    const zoneRefs = useRef({});
    const virtuosoRefs = useRef({});

    // Dialog States
    const [selectedSale, setSelectedSale] = useState(null);
    const [isSaleOpen, setIsSaleOpen] = useState(false);
    const [selectedProduct, setSelectedProduct] = useState(null);
    const [isProductOpen, setIsProductOpen] = useState(false);
    const [selectedInvoice, setSelectedInvoice] = useState(null);
    const [isInvoiceOpen, setIsInvoiceOpen] = useState(false);

    useEffect(() => {
        if (!q) { setResults({ products: [], customers: [], suppliers: [], sales: [], purchases: [] }); return; }

        let active = true;
        setLoading(true);

        setActiveZoneIndex(0);
        setSelectedItemIndex(0);

        const timer = setTimeout(async () => {
            try {
                const [products, customers, suppliers, globalData] = await Promise.all([
                    window.api.fuzzySearch({ query: q, type: 'product', limit: 20 }),
                    window.api.fuzzySearch({ query: q, type: 'customer', limit: 20 }),
                    window.api.fuzzySearch({ query: q, type: 'supplier', limit: 20 }),
                    window.api.searchGlobal(q)
                ]);
                if (active) {
                    setResults({ 
                        products, 
                        customers, 
                        suppliers, 
                        sales: globalData?.sales || [], 
                        purchases: globalData?.purchases || [] 
                    });
                }
            } catch (e) { console.error(e); }
            finally { if (active) setLoading(false); }
        }, 400);

        return () => { active = false; clearTimeout(timer); };
    }, [q]);

    const availableZones = useMemo(() => {
        const zones = [];
        if (results.customers?.length > 0) zones.push({ id: 'customers', data: results.customers, label: 'Customers', icon: User, color: 'text-blue-600', bgColor: 'bg-blue-500/10' });
        if (results.suppliers?.length > 0) zones.push({ id: 'suppliers', data: results.suppliers, label: 'Suppliers', icon: UserPlus, color: 'text-indigo-600', bgColor: 'bg-indigo-500/10' });
        if (results.products?.length > 0) zones.push({ id: 'products', data: results.products, label: 'Products', icon: Package, color: 'text-purple-600', bgColor: 'bg-purple-500/10' });
        if (results.sales?.length > 0) zones.push({ id: 'sales', data: results.sales, label: 'Sales', icon: ShoppingBag, color: 'text-green-600', bgColor: 'bg-green-500/10' });
        if (results.purchases?.length > 0) zones.push({ id: 'purchases', data: results.purchases, label: 'Purchases', icon: Truck, color: 'text-orange-600', bgColor: 'bg-orange-500/10' });
        return zones;
    }, [results]);

    const total = (results.customers?.length || 0) + (results.products?.length || 0) + (results.suppliers?.length || 0) + (results.sales?.length || 0) + (results.purchases?.length || 0);

    // --- AUTO-SCROLL PAGE TO ACTIVE ZONE ---
    useEffect(() => {
        const currentZoneId = availableZones[activeZoneIndex]?.id;
        if (currentZoneId && zoneRefs.current[currentZoneId]) {
            zoneRefs.current[currentZoneId].scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
        }
    }, [activeZoneIndex, availableZones]);

    // --- AUTO-SCROLL LIST TO SELECTED ITEM ---
    useEffect(() => {
        const currentZone = availableZones[activeZoneIndex];
        if (currentZone && virtuosoRefs.current[currentZone.id]) {
            virtuosoRefs.current[currentZone.id].scrollIntoView({
                index: selectedItemIndex,
                behavior: 'auto',
                align: 'start'
            });
        }
    }, [selectedItemIndex, activeZoneIndex, availableZones]);

    // --- KEYBOARD HANDLER ---
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (availableZones.length === 0) return;

            const currentZone = availableZones[activeZoneIndex];
            const currentDataLength = currentZone.data.length;

            if (e.key === 'ArrowRight') {
                e.preventDefault();
                setActiveZoneIndex(prev => (prev + 1) % availableZones.length);
                setSelectedItemIndex(0);
            } else if (e.key === 'ArrowLeft') {
                e.preventDefault();
                setActiveZoneIndex(prev => (prev - 1 + availableZones.length) % availableZones.length);
                setSelectedItemIndex(0);
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                setSelectedItemIndex(prev => {
                    const next = prev + 1;
                    if (next >= currentDataLength) return prev;
                    return next;
                });
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setSelectedItemIndex(prev => {
                    const next = prev - 1;
                    if (next < 0) return 0;
                    return next;
                });
            } else if (e.key === 'Enter') {
                e.preventDefault();
                const item = currentZone.data[selectedItemIndex];
                if (!item) return;

                if (currentZone.id === 'customers') navigate(`/customer/${item.id}`);
                else if (currentZone.id === 'suppliers') navigate(`/suppliers`);
                else if (currentZone.id === 'products') { setSelectedProduct(item); setIsProductOpen(true); }
                else if (currentZone.id === 'sales') { setSelectedSale(item); setIsSaleOpen(true); }
                else if (currentZone.id === 'purchases') handlePurchaseClick(item);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [availableZones, activeZoneIndex, selectedItemIndex, navigate]);

    const handlePurchaseClick = async (p) => {
        try {
            const details = await window.api.getInvoiceDetails(p.invoice_id);
            setSelectedInvoice(details);
            setIsInvoiceOpen(true);
        } catch (e) { console.error("Failed to load invoice", e); }
    };

    // --- ROW RENDERERS ---
    const renderRow = (type, item, index) => {
        const currentZoneId = availableZones[activeZoneIndex]?.id;
        const isZoneActive = currentZoneId === type;
        const isSelected = isZoneActive && index === selectedItemIndex;

        const activeStyle = isSelected
            ? 'bg-blue-500/10 border-l-4 border-l-blue-600 pl-3 z-10'
            : 'bg-card border-l-4 border-l-transparent pl-3 hover:bg-muted/40';

        const commonClasses = `flex justify-between items-center py-3 pr-4 border-b border-border transition-colors cursor-pointer ${activeStyle}`;

        if (type === 'customers') {
            return (
                <div onClick={() => navigate(`/customer/${item.id}`)} className={commonClasses}>
                    <div>
                        <p className={`font-medium text-sm ${isSelected ? 'text-blue-600' : 'text-foreground'}`}>{item.name}</p>
                        <p className="text-xs text-muted-foreground">{item.mobile || "No Contact"}</p>
                    </div>
                    {isSelected && <ArrowRight size={14} className="text-blue-600 animate-in slide-in-from-left-2 fade-in" />}
                </div>
            );
        }
        if (type === 'suppliers') {
            return (
                <div onClick={() => navigate(`/suppliers`)} className={commonClasses}>
                    <div>
                        <p className={`font-medium text-sm ${isSelected ? 'text-indigo-600' : 'text-foreground'}`}>{item.name}</p>
                        <p className="text-xs text-muted-foreground">{item.mobile || "No Contact"}</p>
                    </div>
                    {isSelected && <ArrowRight size={14} className="text-indigo-600 animate-in slide-in-from-left-2 fade-in" />}
                </div>
            );
        }
        if (type === 'products') {
            return (
                <div onClick={() => { setSelectedProduct(item); setIsProductOpen(true); }} className={commonClasses}>
                    <div>
                        <p className={`font-medium text-sm ${isSelected ? 'text-blue-600' : 'text-foreground'}`}>{item.product_name}</p>
                        <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                            {item.variant_name}
                            <span className="text-muted-foreground/40">•</span>
                            <span className={item.current_stock < 10 ? "text-red-600 font-bold" : ""}>
                                Stock: {item.current_stock} {item.unit}
                            </span>
                        </p>
                    </div>
                    <div className="text-right">
                        <span className={`font-mono text-xs font-bold px-2 py-1 rounded border ${isSelected ? 'bg-blue-500/10 text-blue-600 border-blue-500/20' : 'bg-muted text-muted-foreground border-border'}`}>
                            ₹{item.price}
                        </span>
                    </div>
                </div>
            );
        }
        if (type === 'sales') {
            return (
                <div onClick={() => { setSelectedSale(item); setIsSaleOpen(true); }} className={commonClasses}>
                    <div>
                        <p className={`font-medium text-sm ${isSelected ? 'text-blue-600' : 'text-foreground'}`}>Sale #{item.id}</p>
                        <p className="text-xs text-muted-foreground">{new Date(item.sale_date).toLocaleDateString()} • {item.customer_name || "Walk-in"}</p>
                    </div>
                    <Badge variant="outline" className={`font-mono ${isSelected ? 'bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'bg-green-500/10 text-green-700 dark:text-green-400'} border-transparent`}>+₹{Number(item.total_amount || 0).toFixed(2)}</Badge>
                </div>
            );
        }
        if (type === 'purchases') {
            return (
                <div onClick={() => handlePurchaseClick(item)} className={commonClasses}>
                    <div>
                        <p className={`font-medium text-sm ${isSelected ? 'text-blue-600' : 'text-foreground'}`}>
                            {item.product_name}
                        </p>
                        <p className="text-xs text-muted-foreground">INV #{item.invoice_id} • {new Date(item.purchase_date).toLocaleDateString()}</p>
                    </div>
                    <Badge variant="outline" className={`font-mono ${isSelected ? 'bg-blue-500/10 text-blue-700 dark:text-blue-400' : 'bg-orange-500/10 text-orange-700 dark:text-orange-400'} border-transparent`}>Qty: {item.quantity}</Badge>
                </div>
            );
        }
    };

    if (loading && total === 0) return <div className="flex justify-center flex-col gap-3 p-20 h-screen items-center"><Loader2 className="animate-spin text-blue-600 h-10 w-10" /><p className="text-muted-foreground text-sm font-medium">Searching across database...</p></div>;

    return (
        <div ref={containerRef} className="max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500 p-6 h-[calc(100vh-10px)] flex flex-col">

            {/* HEADER SECTION */}
            <div className="flex flex-col gap-4 flex-shrink-0">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground h-5 w-5" />
                    <Input
                        readOnly
                        value={q}
                        className="pl-10 h-12 text-lg font-medium border-border shadow-sm bg-background focus-visible:ring-blue-500"
                    />
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
                        <Badge variant="secondary" className="text-[10px] text-muted-foreground bg-muted border-border hidden md:flex items-center gap-1">
                            <Command size={10} /> K
                        </Badge>
                    </div>
                </div>

                <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                        <h1 className="text-xl font-bold tracking-tight text-foreground">Search Results</h1>
                        <span className="text-muted-foreground/50">•</span>
                        <p className="text-sm text-muted-foreground">Found <span className="font-bold text-foreground">{total}</span> matches</p>
                    </div>

                    {total > 0 && (
                        <div className="flex gap-4 text-[11px] font-bold tracking-wider text-muted-foreground">
                            <div className="flex items-center gap-1.5 bg-background px-2.5 py-1.5 rounded-md border border-border shadow-sm">
                                <div className="flex flex-col gap-0.5"><ArrowLeftRight size={10} className="text-blue-500" /></div>
                                SWITCH ZONE
                            </div>
                            <div className="flex items-center gap-1.5 bg-background px-2.5 py-1.5 rounded-md border border-border shadow-sm">
                                <div className="flex flex-col gap-0.5"><ArrowUp size={8} className="text-blue-500" /><ArrowDown size={8} className="text-blue-500" /></div>
                                NAVIGATE
                            </div>
                            <div className="flex items-center gap-1.5 bg-background px-2.5 py-1.5 rounded-md border border-border shadow-sm">
                                <CornerDownLeft size={10} className="text-blue-500" /> SELECT
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {total === 0 && !loading && (
                <div className="flex-1 flex flex-col items-center justify-center text-center text-muted-foreground bg-muted/20 rounded-xl border border-dashed border-border m-4">
                    <div className="w-16 h-16 bg-background rounded-full flex items-center justify-center mb-4 shadow-sm border border-border">
                        <Search className="h-8 w-8 text-muted-foreground/40" />
                    </div>
                    <p className="text-lg font-bold text-foreground">No results found</p>
                    <p className="text-sm text-muted-foreground mb-6 max-w-xs mx-auto">We couldn't find anything matching "{q}" in your customers, products, or sales records.</p>
                    <div className="flex gap-3">
                        <Button variant="outline" onClick={() => navigate('/customers')} className="gap-2"><PlusCircle size={16} /> New Customer</Button>
                        <Button variant="outline" onClick={() => navigate('/products')} className="gap-2"><PlusCircle size={16} /> New Product</Button>
                    </div>
                </div>
            )}

            {/* DYNAMIC GRID */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 flex-1 min-h-0 pb-6 overflow-y-auto pr-1">
                {availableZones.map((zone) => {
                    const isActive = availableZones[activeZoneIndex]?.id === zone.id;
                    return (
                        <div key={zone.id} ref={(el) => (zoneRefs.current[zone.id] = el)}>
                            <Card
                                className={`overflow-hidden transition-all duration-200 flex flex-col h-[450px]
                        ${isActive
                                        ? 'border-blue-500 shadow-md ring-1 ring-blue-500'
                                        : 'border-border shadow-sm opacity-70'
                                    }`}
                            >
                                <CardHeader className={`py-3 px-4 border-b border-border flex-shrink-0 ${isActive ? 'bg-blue-500/5' : 'bg-muted/30'}`}>
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2.5">
                                            <div className={`p-1.5 rounded-md ${zone.bgColor} ${zone.color} border border-black/5`}>
                                                <zone.icon size={16} />
                                            </div>
                                            <CardTitle className={`text-sm font-bold uppercase tracking-wider ${isActive ? 'text-blue-600' : 'text-muted-foreground'}`}>
                                                {zone.label}
                                            </CardTitle>
                                        </div>
                                        <Badge variant="secondary" className="bg-background border-border text-foreground shadow-sm font-mono">{zone.data.length}</Badge>
                                    </div>
                                </CardHeader>

                                <CardContent className="p-0 flex-1 min-h-0 bg-card">
                                    <Virtuoso
                                        ref={(el) => (virtuosoRefs.current[zone.id] = el)}
                                        style={{ height: '100%' }}
                                        data={zone.data}
                                        itemContent={(index, item) => renderRow(zone.id, item, index)}
                                    />
                                </CardContent>
                            </Card>
                        </div>
                    );
                })}
            </div>

            {/* DIALOGS */}
            <Dialog open={isSaleOpen} onOpenChange={setIsSaleOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Sale #{selectedSale?.id}</DialogTitle>
                        <DialogDescription>Recorded on {selectedSale ? new Date(selectedSale.sale_date).toLocaleString() : ''}</DialogDescription>
                    </DialogHeader>
                    <div className="py-2 space-y-4">
                        <div className="flex justify-between items-center p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
                            <span className="text-green-700 dark:text-green-400 font-bold uppercase text-xs tracking-wider">Total Amount</span>
                            <span className="text-2xl font-bold text-green-700 dark:text-green-400">₹{Number(selectedSale?.total_amount || 0).toFixed(2)}</span>
                        </div>
                        {selectedSale?.items_summary && (
                            <div className="text-sm bg-muted/30 p-4 rounded-lg border border-border">
                                <p className="font-bold mb-2 text-muted-foreground text-xs uppercase tracking-wider">Items Sold</p>
                                <p className="whitespace-pre-wrap text-foreground/80 font-mono text-xs">{selectedSale.items_summary}</p>
                            </div>
                        )}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsSaleOpen(false)}>Close</Button>
                        <Button onClick={() => { setIsSaleOpen(false); navigate(`/sales?id=${selectedSale?.id}`); }}>View Full Receipt</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <Dialog open={isProductOpen} onOpenChange={setIsProductOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2"><Package size={20} className="text-purple-600" /> {selectedProduct?.product_name}</DialogTitle>
                        <DialogDescription>{selectedProduct?.variant_name} Variant</DialogDescription>
                    </DialogHeader>
                    <div className="grid grid-cols-2 gap-4 py-4">
                        <div className="space-y-1 p-4 bg-muted/30 rounded-lg border border-border">
                            <span className="text-xs text-muted-foreground uppercase font-bold">Selling Price</span>
                            <p className="text-2xl font-bold text-foreground">₹{selectedProduct?.price}</p>
                        </div>
                        <div className="space-y-1 p-4 bg-muted/30 rounded-lg border border-border">
                            <span className="text-xs text-muted-foreground uppercase font-bold">Current Stock</span>
                            <p className={`text-2xl font-bold ${selectedProduct?.current_stock < 10 ? "text-red-600" : "text-green-600"}`}>
                                {selectedProduct?.current_stock} <span className="text-sm text-muted-foreground font-normal">{selectedProduct?.unit}</span>
                            </p>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsProductOpen(false)}>Close</Button>
                        <Button onClick={() => { setIsProductOpen(false); navigate('/products'); }}>Manage Inventory</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <Dialog open={isInvoiceOpen} onOpenChange={setIsInvoiceOpen}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2"><FileText size={18} className="text-blue-600" /> Invoice #{selectedInvoice?.id}</DialogTitle>
                        <DialogDescription>{selectedInvoice?.supplier_name} • {selectedInvoice && new Date(selectedInvoice.invoice_date).toLocaleString()}</DialogDescription>
                    </DialogHeader>
                    <div className="max-h-[300px] overflow-y-auto border border-border rounded-md mt-2">
                        <Table>
                            <TableHeader className="bg-muted/50">
                                <TableRow>
                                    <TableHead className="h-9 text-xs">Item</TableHead>
                                    <TableHead className="h-9 text-xs text-right">Qty</TableHead>
                                    <TableHead className="h-9 text-xs text-right">Cost</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {selectedInvoice?.items?.map((it, i) => (
                                    <TableRow key={i}>
                                        <TableCell className="py-2 text-xs">
                                            <div className="font-medium text-foreground">{it.product_name}</div>
                                            <div className="text-muted-foreground scale-90 origin-left">{it.variant_name}</div>
                                        </TableCell>
                                        <TableCell className="py-2 text-right text-xs">{it.quantity}</TableCell>
                                        <TableCell className="py-2 text-right text-xs font-bold">₹{it.unit_cost}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                    <div className="flex justify-between items-center pt-4 border-t border-border mt-2">
                        <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground">Invoice Total</span>
                        <span className="font-bold text-xl text-blue-600">₹{selectedInvoice?.total_amount.toFixed(2)}</span>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}