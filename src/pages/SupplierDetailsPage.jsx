import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Phone, MapPin, FileText,
  Printer, Search, Truck, ChevronRight
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Virtuoso } from 'react-virtuoso';
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Loader2 } from "lucide-react";

// IMPORT THE SHARED MODAL
import InvoiceDetailModal from "@/components/InvoiceDetailModal";

// --- PRINTABLE COMPONENT (Always white - for printing) ---
const PrintInvoiceContent = React.forwardRef(({ invoice, details, supplier, storeConfig }, ref) => {
  if (!invoice || !details || !supplier) return null;

  const storeName = storeConfig?.name || storeConfig?.store_name || "NEXUS RETAIL OS";
  const storeAddress = storeConfig?.address || storeConfig?.store_address || "";
  const storePhone = storeConfig?.phone || storeConfig?.mobile || "";
  const footer = storeConfig?.footerMessage || "Internal Purchase Record";

  return (
    <div ref={ref} className="p-8 bg-white text-black font-sans max-w-2xl mx-auto h-full">
      <div className="text-center border-b-2 border-black pb-4 mb-6">
        <h1 className="text-2xl font-bold tracking-widest uppercase">{storeName}</h1>
        {storeAddress && <p className="text-sm">{storeAddress}</p>}
        {storePhone && <p className="text-sm">Ph: {storePhone}</p>}
        <p className="text-sm mt-1 font-bold border-t border-black pt-1 inline-block">GOODS RECEIPT NOTE</p>
      </div>

      <div className="flex justify-between mb-8">
        <div className="w-1/2">
          <h3 className="font-bold text-lg mb-1">{supplier.name}</h3>
          {supplier.address && <p className="text-sm">{supplier.address}</p>}
          {supplier.mobile && <p className="text-sm">Ph: {supplier.mobile}</p>}
        </div>
        <div className="w-1/2 text-right">
          <h3 className="font-bold text-lg mb-1">Invoice #{invoice.id}</h3>
          <p className="text-sm">Date: {new Date(invoice.invoicedate || invoice.invoice_date).toLocaleDateString()}</p>
          {invoice.referencenumber && <p className="text-sm font-medium">Ref: {invoice.referencenumber}</p>}
        </div>
      </div>

      <table className="w-full border-collapse mb-8">
        <thead>
          <tr className="border-b-2 border-black">
            <th className="text-left py-2 font-bold">Item Description</th>
            <th className="text-center py-2 font-bold w-20">Qty</th>
            <th className="text-right py-2 font-bold w-24">Unit Cost</th>
            <th className="text-right py-2 font-bold w-24">Total</th>
          </tr>
        </thead>
        <tbody>
          {details.items.map((item, i) => (
            <tr key={i} className="border-b border-gray-200">
              <td className="py-2">
                <div className="font-medium">{item.productname || item.product_name}</div>
                <div className="text-xs text-gray-500">{item.variantname || item.variant_name}</div>
              </td>
              <td className="text-center py-2">{item.quantity}</td>
              <td className="text-right py-2">{Number(item.unitcost || item.unit_cost).toFixed(2)}</td>
              <td className="text-right py-2">{((item.quantity) * (item.unitcost || item.unit_cost)).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex justify-end">
        <div className="w-1/2 border-t-2 border-black pt-4">
          <div className="flex justify-between text-xl font-bold">
            <span>TOTAL AMOUNT:</span>
            <span>₹{Number(invoice.totalamount || invoice.total_amount || 0).toFixed(2)}</span>
          </div>
        </div>
      </div>

      <div className="mt-12 text-center text-xs text-gray-400 border-t pt-4">
        {footer} • {new Date().toLocaleString()}
      </div>
    </div>
  );
});

export default function SupplierDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [supplier, setSupplier] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [storeConfig, setStoreConfig] = useState(null);

  const [selectedInvoiceId, setSelectedInvoiceId] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState(null);

  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const virtuosoRef = useRef(null);
  const searchInputRef = useRef(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const sup = await window.api.getSupplierById(id);
        if (!sup) return navigate('/purchase-ledger');
        setSupplier(sup);

        const hist = await window.api.getSupplierPurchasesPaginated(id, 1, 5000);
        setHistory(hist || []);

        const settings = await window.api.getLocalSettings();
        if (settings) {
          let config = settings.store_config || settings;
          setStoreConfig(config);
        }
      } catch (e) { console.error(e); } finally { setLoading(false); }
    };
    load();
  }, [id, navigate]);

  const handleRowClick = useCallback((invoice) => {
    if (!invoice) return;
    setSelectedInvoiceId(invoice.id);
    setIsModalOpen(true);
  }, []);

  const handlePrintFromModal = (details) => {
    const invoiceBasic = history.find(h => h.id === selectedInvoiceId) || {};
    const invoiceForPrint = { ...invoiceBasic, ...details };
    setPreviewData({ invoice: invoiceForPrint, details: details });
    setIsModalOpen(false);
    setIsPreviewOpen(true);
  };

  const handleFinalPrint = () => { window.print(); };

  const filteredHistory = useMemo(() => {
    if (!searchTerm) return history;
    const lower = searchTerm.toLowerCase();
    const matches = history.filter(h =>
      h.id.toString().includes(lower) ||
      (h.totalamount || h.total_amount || 0).toString().includes(lower) ||
      (h.referencenumber && h.referencenumber.toLowerCase().includes(lower))
    );
    return matches;
  }, [history, searchTerm]);

  useEffect(() => {
    setHighlightedIndex(0);
  }, [searchTerm]);

  const handleKeyDown = (e) => {
    if (filteredHistory.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex(prev => {
        const next = Math.min(prev + 1, filteredHistory.length - 1);
        virtuosoRef.current?.scrollIntoView({ index: next, behavior: 'auto' });
        return next;
      });
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex(prev => {
        const next = Math.max(prev - 1, 0);
        virtuosoRef.current?.scrollIntoView({ index: next, behavior: 'auto' });
        return next;
      });
    } else if (e.key === "Enter") {
      e.preventDefault();
      handleRowClick(filteredHistory[highlightedIndex]);
    }
  };

  const InvoiceRow = ({ index, data }) => {
    const inv = data[index];
    const isHighlighted = index === highlightedIndex;
    const dateStr = inv.invoicedate || inv.invoice_date;
    const date = new Date(dateStr).toLocaleDateString();
    const total = inv.totalamount || inv.total_amount || 0;

    return (
      <div
        onClick={() => handleRowClick(inv)}
        className={`
          flex items-center justify-between px-6 py-3 border-b border-border cursor-pointer transition-colors
          ${isHighlighted
            ? 'bg-blue-500/10 z-10'
            : 'bg-card hover:bg-muted/40'
          }
        `}
      >
        <div className="flex-1 min-w-0 pr-4">
          <div className="flex items-center gap-3 mb-1">
            <span className={`font-mono text-xs px-1.5 py-0.5 rounded border ${isHighlighted ? 'bg-blue-500/10 text-blue-600 border-blue-500/20' : 'bg-muted text-muted-foreground border-border'}`}>
              #{inv.id}
            </span>
            <span className="text-sm font-medium text-foreground">{date}</span>
          </div>
          {inv.referencenumber && (
            <div className="text-xs text-muted-foreground flex items-center gap-1.5 pl-1">
              <FileText size={12} className="text-muted-foreground/50" />
              <span className="truncate">Ref: {inv.referencenumber}</span>
            </div>
          )}
        </div>

        <div className="text-right flex flex-col items-end gap-0.5">
          <div className={`font-bold font-mono ${isHighlighted ? 'text-blue-600' : 'text-foreground'}`}>₹{total.toFixed(2)}</div>
          <Badge variant="outline" className="text-[10px] h-5 px-1.5 text-muted-foreground font-normal border-border">
            {inv.itemcount || 0} items
          </Badge>
        </div>

        <div className="w-8 flex justify-end">
          <ChevronRight size={16} className={`transition-opacity ${isHighlighted ? 'opacity-100 text-blue-500' : 'opacity-0 group-hover:opacity-50 text-muted-foreground/40'}`} />
        </div>
      </div>
    );
  };

  if (loading) return <div className="h-screen flex items-center justify-center space-y-4 flex-col"><Loader2 className="animate-spin text-blue-600 h-10 w-10" /><p className="text-muted-foreground font-medium">Loading Supplier Profile...</p></div>;

  return (
    <>
      <div className="hidden print:block fixed inset-0 bg-white z-[9999] overflow-hidden">
        {previewData && <PrintInvoiceContent invoice={previewData.invoice} details={previewData.details} supplier={supplier} storeConfig={storeConfig} />}
      </div>

      <div className="max-w-7xl mx-auto space-y-6 p-6 pb-6 print:hidden animate-in fade-in duration-500 h-screen flex flex-col overflow-hidden">

        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate('/purchase-ledger')} className="h-10 w-10 rounded-full hover:bg-muted -ml-2 text-muted-foreground">
              <ArrowLeft size={20} />
            </Button>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground">{supplier?.name}</h1>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-sm text-muted-foreground">Supplier Profile &amp; History</span>
                <Badge variant="secondary" className="font-mono text-[10px] text-muted-foreground bg-muted border-border">ID #{supplier?.id}</Badge>
              </div>
            </div>
          </div>
        </div>

        <Separator className="flex-shrink-0" />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 flex-shrink-0">
          <Card className="border-border shadow-sm bg-card">
            <CardContent className="flex items-center gap-4 p-5">
              <div className="p-0 text-muted-foreground"><Phone size={24} strokeWidth={1.5} /></div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Mobile Contact</p>
                <p className="font-semibold text-foreground mt-0.5">{supplier?.mobile || "N/A"}</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-border shadow-sm bg-card">
            <CardContent className="flex items-center gap-4 p-5">
              <div className="p-0 text-muted-foreground"><MapPin size={24} strokeWidth={1.5} /></div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Address</p>
                <p className="font-semibold text-foreground mt-0.5 truncate max-w-[200px]" title={supplier?.address}>{supplier?.address || "N/A"}</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-border shadow-sm bg-card">
            <CardContent className="flex items-center gap-4 p-5">
              <div className="p-0 text-muted-foreground"><Truck size={24} strokeWidth={1.5} /></div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Total Volume</p>
                <p className="text-xl font-bold text-foreground tracking-tight mt-0.5">₹{history.reduce((sum, h) => sum + (h.totalamount || h.total_amount || 0), 0).toFixed(2)}</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="flex-1 border-border shadow-sm flex flex-col overflow-hidden min-h-0 bg-card">
          <CardHeader className="py-4 px-6 border-b border-border bg-card flex flex-row items-center justify-between space-y-0 flex-shrink-0">
            <div className="flex items-center gap-2">
              <FileText className="text-muted-foreground" size={18} />
              <CardTitle className="text-base font-bold text-foreground">Purchase History</CardTitle>
              <Badge variant="secondary" className="ml-2 bg-muted text-muted-foreground border-border">{filteredHistory.length}</Badge>
            </div>

            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={14} />
              <Input
                ref={searchInputRef}
                placeholder="Search invoices..."
                className="pl-9 h-9 bg-muted/50 border-border focus:bg-background transition-all text-sm"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </div>
          </CardHeader>

          <CardContent className="p-0 flex flex-col flex-1 bg-card min-h-0">
            {filteredHistory.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-20 text-muted-foreground gap-3">
                <div className="bg-muted p-4 rounded-full"><Search size={24} className="opacity-50" /></div>
                <p className="text-sm font-medium">No invoices match your search.</p>
              </div>
            ) : (
              <div className="flex flex-col flex-1 min-h-0">
                <div className="grid grid-cols-[1fr_auto_32px] px-6 py-2 bg-muted/30 border-b border-border text-xs font-bold uppercase tracking-wider text-muted-foreground flex-shrink-0">
                  <div>Invoice Details</div>
                  <div className="text-right">Amount</div>
                  <div></div>
                </div>

                <div className="flex-1 min-h-0">
                  <Virtuoso
                    ref={virtuosoRef}
                    style={{ height: '100%' }}
                    data={filteredHistory}
                    itemContent={(index) => <InvoiceRow index={index} data={filteredHistory} />}
                  />
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <InvoiceDetailModal
        isOpen={isModalOpen}
        invoiceId={selectedInvoiceId}
        onClose={() => setIsModalOpen(false)}
        onPrint={handlePrintFromModal}
      />

      <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
        <DialogContent className="max-w-4xl h-[90vh] flex flex-col p-0 overflow-hidden">
          <DialogHeader className="p-4 border-b border-border flex-shrink-0"><DialogTitle>Print Preview</DialogTitle></DialogHeader>
          <div className="flex-1 overflow-y-auto bg-muted/30 p-8 flex justify-center">
            <div className="shadow-xl bg-white scale-90 origin-top">
              {previewData && <PrintInvoiceContent invoice={previewData.invoice} details={previewData.details} supplier={supplier} storeConfig={storeConfig} />}
            </div>
          </div>
          <DialogFooter className="p-4 border-t border-border bg-card flex-shrink-0">
            <Button variant="outline" onClick={() => setIsPreviewOpen(false)}>Close</Button>
            <Button onClick={handleFinalPrint} className="gap-2 bg-blue-600 hover:bg-blue-700"><Printer size={16} /> Print Now</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}