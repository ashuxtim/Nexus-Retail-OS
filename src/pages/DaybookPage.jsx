import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import { Virtuoso } from 'react-virtuoso';
import {
    Loader2, Calendar, TrendingUp, TrendingDown,
    RefreshCw, ShoppingBag, Printer, ChevronLeft, ChevronRight,
    Wallet
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";

// Polyfill
if (typeof window !== 'undefined') { if (!("dragEvent" in window)) { Object.defineProperty(window, "dragEvent", { get: () => undefined }); } }

// --- PRINT COMPONENT (UNCHANGED) ---
const PrintDaybookContent = React.forwardRef(({ data, date }, ref) => {
    if (!data) return null;
    return (
        <div ref={ref} className="p-8 font-mono text-black bg-white w-full max-w-[800px] mx-auto">
            <div className="text-center mb-6 border-b border-black pb-4">
                <h1 className="text-2xl font-bold">DAYBOOK REPORT</h1>
                <p className="text-sm">Financial Summary</p>
            </div>
            <div className="flex justify-between mb-6 text-sm">
                <p><strong>Date:</strong> {new Date(date).toLocaleDateString()}</p>
                <p><strong>Generated:</strong> {new Date().toLocaleTimeString()}</p>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-6 text-sm border-b border-black pb-6">
                <div>
                    <span className="block text-gray-500">Money In</span>
                    <span className="font-bold text-lg">₹{data.cashIn?.toFixed(2)}</span>
                </div>
                <div>
                    <span className="block text-gray-500">Money Out</span>
                    <span className="font-bold text-lg">₹{data.cashOut?.toFixed(2)}</span>
                </div>
                <div className="text-right">
                    <span className="block text-gray-500">Net Cash</span>
                    <span className="font-bold text-lg">₹{data.netCash?.toFixed(2)}</span>
                </div>
            </div>

            <div className="mb-4">
                <h3 className="font-bold border-b border-gray-300 mb-2 pb-1">Item Sales</h3>
                <table className="w-full text-sm">
                    <thead>
                        <tr className="text-left">
                            <th className="py-1">Item Name</th>
                            <th className="text-center py-1">Qty</th>
                            <th className="text-right py-1">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.items?.map((item, i) => (
                            <tr key={i} className="border-b border-dotted border-gray-200">
                                <td className="py-1">{item.name}</td>
                                <td className="text-center py-1">{item.qty}</td>
                                <td className="text-right py-1">₹{item.total.toFixed(2)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <div className="text-center mt-12 text-xs">-- End of Report --</div>
        </div>
    );
});

export default function DaybookPage() {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [isPreviewOpen, setIsPreviewOpen] = useState(false);

    useEffect(() => { loadDaybook(); }, [date]);

    const loadDaybook = async () => {
        setLoading(true);
        try {
            const res = await window.api.getDaybook(date);
            setData(res);
        } catch (e) {
            console.error(e);
            toast.error("Failed to load daybook");
        } finally {
            setLoading(false);
        }
    };

    // --- DATE NAVIGATION LOGIC ---
    const changeDate = (days) => {
        const current = new Date(date);
        current.setDate(current.getDate() + days);
        setDate(current.toISOString().split('T')[0]);
    };

    const goToToday = () => {
        setDate(new Date().toISOString().split('T')[0]);
    };

    const isToday = date === new Date().toISOString().split('T')[0];

    // --- UI: ROW RENDERER (Standardized Table Look) ---
    const ItemRow = (index, item) => (
        <div className="flex justify-between items-center px-6 py-3 border-b border-border hover:bg-muted/50 transition-colors">
            {/* Column 1: Product Name */}
            <div className="flex-1 font-medium text-sm text-foreground truncate pr-4">{item.name}</div>

            {/* Column 2: Quantity (Centered) */}
            <div className="w-24 text-center">
                <span className="font-mono text-xs text-muted-foreground bg-muted px-2 py-1 rounded border border-border">
                    {item.qty}
                </span>
            </div>

            {/* Column 3: Total (Right Aligned) */}
            <div className="w-32 text-right font-medium text-sm text-foreground">₹{item.total.toFixed(2)}</div>
        </div>
    );

    if (loading) return <div className="h-[calc(100vh-4rem)] flex justify-center items-center"><Loader2 className="animate-spin text-muted-foreground h-8 w-8" /></div>;

    return (
        <div className="max-w-[1600px] mx-auto space-y-6 animate-in fade-in duration-500 p-6 pb-20 h-[calc(100vh-40px)] flex flex-col">

            {/* --- HIDDEN PRINT AREA --- */}
            <div className="hidden print:block fixed inset-0 bg-white z-[9999] overflow-hidden">
                <PrintDaybookContent data={data} date={date} />
            </div>

            {/* --- HEADER (UNBOXED & CLEAN) --- */}
            <div className="flex flex-col md:flex-row justify-between items-end gap-4 flex-shrink-0">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground">Daybook</h1>
                    <p className="text-muted-foreground mt-1">Daily financial summary & transaction log.</p>
                </div>

                <div className="flex items-center gap-3">
                    {/* Date Navigation */}
                    <div className="flex items-center gap-1 bg-background p-1 rounded-md border shadow-sm">
                        <Button
                            variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground"
                            onClick={() => changeDate(-1)} title="Previous Day"
                        >
                            <ChevronLeft size={16} />
                        </Button>

                        <div className="relative">
                            <input
                                type="date"
                                className="bg-transparent font-medium text-sm text-foreground outline-none px-2 w-[120px] cursor-pointer text-center"
                                value={date}
                                onChange={e => setDate(e.target.value)}
                            />
                        </div>

                        <Button
                            variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground"
                            onClick={() => changeDate(1)} title="Next Day"
                        >
                            <ChevronRight size={16} />
                        </Button>
                    </div>

                    {!isToday && (
                        <Button variant="outline" size="sm" onClick={goToToday} className="h-9">
                            Today
                        </Button>
                    )}

                    <Separator orientation="vertical" className="h-6" />

                    <Button variant="outline" size="sm" className="h-9 gap-2" onClick={() => setIsPreviewOpen(true)}>
                        <Printer size={16} /> Print
                    </Button>

                    <Button variant="ghost" size="icon" onClick={loadDaybook} className="h-9 w-9 text-muted-foreground hover:text-primary">
                        <RefreshCw size={16} />
                    </Button>
                </div>
            </div>

            {/* --- METRICS (Standardized KPI Style) --- */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 flex-shrink-0">
                <Card className="shadow-sm border-border">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Money In</CardTitle>
                        <div className="h-8 w-8 rounded-md flex items-center justify-center bg-emerald-500/10">
                            <TrendingUp size={16} className="text-emerald-600" />
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-foreground">₹{data?.cashIn?.toFixed(2)}</div>
                    </CardContent>
                </Card>

                <Card className="shadow-sm border-border">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Money Out</CardTitle>
                        <div className="h-8 w-8 rounded-md flex items-center justify-center bg-red-500/10">
                            <TrendingDown size={16} className="text-red-600" />
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-foreground">₹{data?.cashOut?.toFixed(2)}</div>
                    </CardContent>
                </Card>

                <Card className="shadow-sm border-border">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Net Cash</CardTitle>
                        <div className="h-8 w-8 rounded-md flex items-center justify-center bg-blue-500/10">
                            <Wallet size={16} className="text-blue-600" />
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-foreground">₹{data?.netCash?.toFixed(2)}</div>
                    </CardContent>
                </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
                {/* --- OVERVIEW CARD --- */}
                <Card className="lg:col-span-1 shadow-sm border-border h-full">
                    <CardHeader className="pb-3 border-b border-border">
                        <CardTitle className="text-base font-semibold text-foreground">Financial Overview</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6 pt-6">
                        <div className="flex justify-between items-center p-4 bg-muted/20 rounded-lg border border-border">
                            <span className="text-sm font-medium text-muted-foreground">Total Sales Value</span>
                            <span className="font-bold text-lg text-foreground">₹{data?.totalSales?.toFixed(2)}</span>
                        </div>
                        <div className="space-y-4">
                            <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">Collected</span>
                                <span className="font-medium text-emerald-600">₹{data?.cashIn?.toFixed(2)}</span>
                            </div>
                            <Separator />
                            <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">Credit Given</span>
                                <span className="font-medium text-red-600">₹{(Math.max(0, data?.totalSales - data?.cashIn)).toFixed(2)}</span>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* --- ITEM MOVEMENT (Standardized Table Look) --- */}
                <Card className="lg:col-span-2 border-border flex flex-col h-full overflow-hidden shadow-sm">
                    {/* Header Row */}
                    <div className="flex items-center justify-between px-6 py-4 border-b border-border flex-shrink-0">
                        <div className="flex items-center gap-2">
                            <ShoppingBag size={16} className="text-muted-foreground" />
                            <span className="font-semibold text-sm text-foreground">Item Movement</span>
                        </div>
                        <Badge variant="secondary" className="font-normal">
                            {data?.items?.length} items
                        </Badge>
                    </div>

                    {/* Table Column Headers */}
                    <div className="flex items-center px-6 py-2 bg-muted/30 border-b border-border text-xs font-medium text-muted-foreground">
                        <div className="flex-1">Product Name</div>
                        <div className="w-24 text-center">Qty</div>
                        <div className="w-32 text-right">Total</div>
                    </div>

                    <div className="flex-1 bg-background min-h-0">
                        {!data?.items || data.items.length === 0 ? (
                            <div className="flex h-full items-center justify-center text-muted-foreground text-sm flex-col gap-2">
                                <ShoppingBag size={32} className="opacity-20" />
                                No items sold on this date.
                            </div>
                        ) : (
                            <Virtuoso style={{ height: '100%' }} data={data.items} itemContent={ItemRow} />
                        )}
                    </div>
                </Card>
            </div>

            {/* --- PREVIEW MODAL --- */}
            <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
                <DialogContent className="max-w-4xl h-[90vh] flex flex-col p-0 overflow-hidden">
                    <DialogHeader className="p-4 border-b border-border flex-shrink-0"><DialogTitle>Print Preview</DialogTitle></DialogHeader>
                    <div className="flex-1 overflow-y-auto bg-muted/30 p-8 flex justify-center">
                        <div className="shadow-xl bg-white scale-90 origin-top">
                            <PrintDaybookContent data={data} date={date} />
                        </div>
                    </div>
                    <DialogFooter className="p-4 border-t border-border bg-background flex-shrink-0">
                        <Button variant="outline" onClick={() => setIsPreviewOpen(false)}>Close</Button>
                        <Button onClick={() => window.print()} className="gap-2"><Printer size={16} /> Print Now</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

        </div>
    );
}