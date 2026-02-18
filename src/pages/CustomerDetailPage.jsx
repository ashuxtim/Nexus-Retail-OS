import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { Virtuoso } from 'react-virtuoso'; 
import { 
  Phone, MapPin, Wallet, Trash2, Printer, ArrowLeft, Loader2, 
  ShoppingBag, Banknote, Calendar, Clock, FileText, ChevronRight 
} from "lucide-react";

// --- SHADCN IMPORTS ---
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription 
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

// --- Safer Polyfill for Drag Events ---
if (typeof window !== 'undefined') {
    if (!("dragEvent" in window)) {
        Object.defineProperty(window, "dragEvent", { get: () => undefined });
    }
}

const PAGE_SIZE = 50; 

// --- PRINT PREVIEW COMPONENT ---
const PrintStatementContent = React.forwardRef(({ customer, history, storeConfig }, ref) => {
    if (!customer) return null;
    return (
        <div ref={ref} className="p-8 font-mono text-black bg-white w-full max-w-[800px] mx-auto">
            <div className="text-center mb-6 border-b border-black pb-4">
                <h1 className="text-xl font-bold">{storeConfig?.name || "NEXUS RETAIL OS"}</h1>
                {storeConfig?.address && <p className="text-xs">{storeConfig.address}</p>}
                {storeConfig?.phone && <p className="text-xs">Ph: {storeConfig.phone}</p>}
                <p className="text-sm mt-1 font-bold border-t border-black pt-1 inline-block">Customer Statement</p>
            </div>
            <div className="mb-6 flex justify-between text-sm">
                <div><p><strong>Customer:</strong> {customer.name}</p><p><strong>Mobile:</strong> {customer.mobile || '-'}</p></div>
                <div className="text-right"><p><strong>Date:</strong> {new Date().toLocaleDateString()}</p><p><strong>ID:</strong> #{customer.id}</p></div>
            </div>
            <table className="w-full text-xs mb-6">
                <thead>
                    <tr className="border-b border-black text-left">
                        <th className="py-2">Date</th>
                        <th className="py-2">Transaction</th>
                        <th className="py-2 text-right">Amount</th>
                    </tr>
                </thead>
                <tbody>
                {history.map((row, i) => (
                    <tr key={i} className="border-b border-dotted border-gray-400">
                    <td className="py-1">{new Date(row.date).toLocaleDateString()}</td>
                    <td className="py-1">
                        <div className="font-bold">{row.type === 'SALE' ? `Sale #${row.id}` : 'Payment Received'}</div>
                        {row.items && (<div className="text-[10px] text-gray-500">{row.items.map(item => `${item.variant_name} (x${item.quantity})`).join(', ')}</div>)}
                    </td>
                    <td className="py-1 text-right">{row.type === 'SALE' ? '+' : '-'}{Number(row.amount).toFixed(2)}</td>
                    </tr>
                ))}
                </tbody>
            </table>
            <div className="flex justify-between items-center border-t-2 border-black pt-4 font-bold text-base">
                <span>BALANCE DUE:</span>
                <span>₹{customer.balance?.toFixed(2)}</span>
            </div>
            <div className="text-center mt-12 text-xs">{storeConfig?.footerMessage || "Thank You!"}</div>
        </div>
    );
});

export default function CustomerDetailPage() {
  const { customerId } = useParams();
  const navigate = useNavigate();
  
  const [customer, setCustomer] = useState(null);
  const [sales, setSales] = useState([]);
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Printing State
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [storeConfig, setStoreConfig] = useState(null);

  // Pagination State
  const [salesPage, setSalesPage] = useState(1);
  const [hasMoreSales, setHasMoreSales] = useState(true);
  const [loadingSales, setLoadingSales] = useState(false);

  const [paymentsPage, setPaymentsPage] = useState(1);
  const [hasMorePayments, setHasMorePayments] = useState(true);
  const [loadingPayments, setLoadingPayments] = useState(false);

  // Dialog States
  const [deleteItem, setDeleteItem] = useState(null);
  const [selectedSale, setSelectedSale] = useState(null);
  const [isSaleOpen, setIsSaleOpen] = useState(false);
  const [selectedPayment, setSelectedPayment] = useState(null);
  const [isPaymentOpen, setIsPaymentOpen] = useState(false);

  useEffect(() => { loadInitialData(); }, [customerId]);

  const loadInitialData = async () => {
    setLoading(true);
    try {
      const found = await window.api.getCustomerById(Number(customerId));
      if (!found) return navigate('/customers');
      setCustomer(found);

      const sData = await window.api.getSalesByCustomerPaginated(Number(customerId), PAGE_SIZE, 0);
      setSales(sData || []);
      if(sData.length < PAGE_SIZE) setHasMoreSales(false);

      const pData = await window.api.getPaymentsByCustomerPaginated(Number(customerId), PAGE_SIZE, 0);
      setPayments(pData || []);
      if(pData.length < PAGE_SIZE) setHasMorePayments(false);

      const settings = await window.api.getLocalSettings();
      if(settings?.store_config) setStoreConfig(settings.store_config);

    } catch (e) { toast.error("Error loading data"); }
    finally { setLoading(false); }
  };

  // Replace your existing combinedHistory useMemo with this:
const combinedHistory = useMemo(() => {
  if (!customer) return [];
  
  return [
    ...sales, 
    ...payments
  ].sort((a,b) => new Date(b.date) - new Date(a.date));
}, [sales, payments, customer]);

  const handlePrint = () => { window.print(); };

  const loadMoreSales = useCallback(async () => {
      if(loadingSales || !hasMoreSales) return;
      setLoadingSales(true);
      try {
          const offset = salesPage * PAGE_SIZE;
          const more = await window.api.getSalesByCustomerPaginated(Number(customerId), PAGE_SIZE, offset);
          if (more.length > 0) {
              setSales(prev => [...prev, ...more]);
              setSalesPage(prev => prev + 1);
          }
          if (more.length < PAGE_SIZE) setHasMoreSales(false);
      } catch(e) { console.error(e); }
      finally { setLoadingSales(false); }
  }, [salesPage, hasMoreSales, loadingSales, customerId]);

  const loadMorePayments = useCallback(async () => {
      if(loadingPayments || !hasMorePayments) return;
      setLoadingPayments(true);
      try {
          const offset = paymentsPage * PAGE_SIZE;
          const more = await window.api.getPaymentsByCustomerPaginated(Number(customerId), PAGE_SIZE, offset);
          if (more.length > 0) {
              setPayments(prev => [...prev, ...more]);
              setPaymentsPage(prev => prev + 1);
          }
          if (more.length < PAGE_SIZE) setHasMorePayments(false);
      } catch(e) { console.error(e); }
      finally { setLoadingPayments(false); }
  }, [paymentsPage, hasMorePayments, loadingPayments, customerId]);

  const handleDelete = async () => {
    if(!deleteItem) return;
    try {
        if(deleteItem.type === 'customer') {
            await window.api.deleteCustomer(Number(customerId));
            navigate('/customers');
            toast.success("Customer Deleted");
        } else if(deleteItem.type === 'sale') {
            await window.api.deleteSale(deleteItem.id);
            toast.success("Sale Deleted");
            setSales(prev => prev.filter(s => s.id !== deleteItem.id)); 
        } else {
            await window.api.deletePayment(deleteItem.id);
            toast.success("Payment Deleted");
            setPayments(prev => prev.filter(p => p.id !== deleteItem.id)); 
        }
    } catch(e) { toast.error("Failed"); }
    finally { setDeleteItem(null); }
  };

  // --- GRID DEFINITIONS ---
  const SALES_GRID = "grid grid-cols-[80px_1fr_100px_40px] gap-4 items-center";
  const PAYMENTS_GRID = "grid grid-cols-[100px_1fr_100px_40px] gap-4 items-center";

  // --- ROW COMPONENTS (Dense & Clean) ---
  const SaleRow = (index, sale) => {
      if (!sale) return null;
      const totalAmount = sale.items.reduce((sum, i) => sum + (i.price_at_sale * i.quantity), 0);
      return (
        <div 
            onClick={() => { setSelectedSale(sale); setIsSaleOpen(true); }} 
            className={`border-b border-slate-100 hover:bg-slate-50/80 cursor-pointer transition-colors group px-4 py-2.5 text-sm ${SALES_GRID}`}
        >
            <div className="font-medium text-blue-600">#{sale.id}</div>
            <div className="truncate min-w-0">
                <span className="text-slate-900 font-medium block truncate">{sale.items?.map(i => i.variant_name).join(', ')}</span>
                <span className="text-[11px] text-slate-400 block mt-0.5">
                    {new Date(sale.date).toLocaleDateString()}
                </span>
            </div>
            <div className="text-right font-bold text-slate-900">₹{totalAmount.toFixed(2)}</div>
            <div className="text-right flex justify-end">
                <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={(e) => { e.stopPropagation(); setDeleteItem({type: 'sale', id: sale.id}); }} 
                    className="h-7 w-7 text-slate-300 hover:text-red-600 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                    <Trash2 size={14}/>
                </Button>
            </div>
        </div>
      );
  };

  const PaymentRow = (index, payment) => {
      if (!payment) return null;
      return (
        <div 
            onClick={() => { setSelectedPayment(payment); setIsPaymentOpen(true); }} 
            className={`border-b border-slate-100 hover:bg-slate-50/80 cursor-pointer transition-colors group px-4 py-2.5 text-sm ${PAYMENTS_GRID}`}
        >
            <div className="text-xs text-slate-500 font-medium">
                {new Date(payment.date).toLocaleDateString()}
            </div>
            <div>
                <Badge variant="secondary" className="bg-green-50 text-green-700 hover:bg-green-100 border-green-100 font-normal px-2 py-0.5 text-[10px]">
                    Collection
                </Badge>
            </div>
            <div className="text-right font-bold text-green-600">-₹{Number(payment.amount).toFixed(2)}</div>
            <div className="text-right flex justify-end">
                <Button 
                    variant="ghost" 
                    size="icon" 
                    onClick={(e) => { e.stopPropagation(); setDeleteItem({type: 'payment', id: payment.id}); }} 
                    className="h-7 w-7 text-slate-300 hover:text-red-600 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                    <Trash2 size={14}/>
                </Button>
            </div>
        </div>
      );
  };

  if (loading || !customer) return (
    <div className="h-screen flex items-center justify-center">
        <Loader2 className="animate-spin text-blue-600 w-8 h-8"/>
    </div>
  );

  return (
    <>
      <div className="hidden print:block fixed inset-0 bg-white z-[9999] overflow-hidden">
          <PrintStatementContent customer={customer} history={combinedHistory} storeConfig={storeConfig} />
      </div>

      <div className="max-w-7xl mx-auto space-y-6 p-6 pb-20 print:hidden animate-in fade-in duration-500 h-screen flex flex-col overflow-hidden">
        
        {/* --- HEADER --- */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 flex-shrink-0">
          <div className="flex items-center gap-4">
             <Button variant="ghost" size="icon" onClick={() => navigate('/customers')} className="h-10 w-10 -ml-2 text-slate-400 hover:text-slate-900 hover:bg-slate-100 rounded-full">
                <ArrowLeft className="h-5 w-5"/>
             </Button>
             <div>
                <h1 className="text-3xl font-bold tracking-tight text-slate-900">{customer.name}</h1>
                <div className="flex items-center gap-2 mt-1">
                    <Badge variant="secondary" className="bg-slate-100 text-slate-500 hover:bg-slate-100 border-slate-200 font-mono text-[10px] px-2">ID #{customer.id}</Badge>
                </div>
             </div>
          </div>
          <div className="flex gap-3">
             <Button variant="outline" onClick={() => setIsPreviewOpen(true)} className="gap-2 border-slate-300 text-slate-700 bg-white shadow-sm hover:bg-slate-50">
                <Printer size={16}/> Statement
             </Button>
             <Button variant="outline" onClick={() => setDeleteItem({type:'customer'})} className="gap-2 border-red-200 text-red-600 bg-white shadow-sm hover:bg-red-50 hover:text-red-700">
                <Trash2 size={16}/> Delete Customer
             </Button>
          </div>
        </div>

        {/* --- KPI CARDS (Matches Screenshot Exactly) --- */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 flex-shrink-0">
          <Card className="shadow-sm border-slate-200 bg-white">
              <CardContent className="flex items-center gap-5 p-6">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-50 text-blue-600 border border-blue-100">
                      <Phone className="h-6 w-6"/>
                  </div>
                  <div>
                      <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Mobile</p>
                      <p className="text-xl font-bold text-slate-900 mt-0.5">{customer.mobile || "N/A"}</p>
                  </div>
              </CardContent>
          </Card>
          <Card className="shadow-sm border-slate-200 bg-white">
              <CardContent className="flex items-center gap-5 p-6">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-purple-50 text-purple-600 border border-purple-100">
                      <MapPin className="h-6 w-6"/>
                  </div>
                  <div>
                      <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Address</p>
                      <p className="text-xl font-bold text-slate-900 mt-0.5 truncate max-w-[200px]" title={customer.address}>
                          {customer.address || "N/A"}
                      </p>
                  </div>
              </CardContent>
          </Card>
          <Card className="shadow-sm border-slate-200 bg-white">
              <CardContent className="flex items-center gap-5 p-6">
                  <div className={`flex h-12 w-12 items-center justify-center rounded-lg border ${customer.balance > 0 ? 'bg-red-50 text-red-600 border-red-100' : 'bg-green-50 text-green-600 border-green-100'}`}>
                      <Wallet className="h-6 w-6"/>
                  </div>
                  <div>
                      <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Balance Due</p>
                      <p className={`text-2xl font-bold mt-0.5 ${customer.balance > 0 ? 'text-slate-900' : 'text-green-600'}`}>
                          ₹{customer.balance?.toFixed(2)}
                      </p>
                  </div>
              </CardContent>
          </Card>
        </div>

        {/* --- DUAL LISTS --- */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0">
           
           {/* SALES LIST */}
           <Card className="flex flex-col overflow-hidden shadow-sm border-slate-200 h-full bg-white">
               <CardHeader className="px-6 py-4 border-b border-slate-100 bg-white flex flex-row items-center justify-between space-y-0 flex-shrink-0">
                   <CardTitle className="flex items-center gap-2 text-base font-bold text-slate-800">
                       <ShoppingBag className="h-4 w-4 text-slate-500"/> Sales History
                   </CardTitle>
                   <Badge variant="secondary" className="bg-slate-100 text-slate-600 font-mono">{sales.length} Records</Badge>
               </CardHeader>
               
               <div className={`bg-slate-50 border-b border-slate-200 px-4 py-2 text-[11px] font-bold text-slate-500 uppercase tracking-wider flex-shrink-0 ${SALES_GRID}`}>
                   <div>ID</div>
                   <div>Items</div>
                   <div className="text-right">Total</div>
                   <div className="text-right">Action</div>
               </div>

               <CardContent className="p-0 flex-1 min-h-0 bg-white">
                   {sales.length === 0 ? (
                       <div className="flex h-full items-center justify-center text-slate-400 text-sm flex-col gap-2">
                           <ShoppingBag className="h-8 w-8 opacity-20"/>
                           No sales recorded
                       </div>
                   ) : (
                    <Virtuoso 
                        style={{ height: '100%' }} 
                        data={sales} 
                        itemContent={SaleRow} 
                        endReached={loadMoreSales} 
                        components={{ 
                            Footer: () => loadingSales ? <div className="p-2 text-center text-xs text-muted-foreground border-t"><Loader2 className="animate-spin h-3 w-3 inline mr-2"/>Loading...</div> : null 
                        }}
                    />
                   )}
               </CardContent>
           </Card>

           {/* PAYMENTS LIST */}
           <Card className="flex flex-col overflow-hidden shadow-sm border-slate-200 h-full bg-white">
               <CardHeader className="px-6 py-4 border-b border-slate-100 bg-white flex flex-row items-center justify-between space-y-0 flex-shrink-0">
                   <CardTitle className="flex items-center gap-2 text-base font-bold text-slate-800">
                       <Banknote className="h-4 w-4 text-green-600"/> Payment History
                   </CardTitle>
                   <Badge variant="secondary" className="bg-slate-100 text-slate-600 font-mono">{payments.length} Records</Badge>
               </CardHeader>

               <div className={`bg-slate-50 border-b border-slate-200 px-4 py-2 text-[11px] font-bold text-slate-500 uppercase tracking-wider flex-shrink-0 ${PAYMENTS_GRID}`}>
                   <div>Date</div>
                   <div>Type</div>
                   <div className="text-right">Amount</div>
                   <div className="text-right">Action</div>
               </div>

               <CardContent className="p-0 flex-1 min-h-0 bg-white">
                   {payments.length === 0 ? (
                       <div className="flex h-full items-center justify-center text-slate-400 text-sm flex-col gap-2">
                           <Banknote className="h-8 w-8 opacity-20"/>
                           No payments recorded
                       </div>
                   ) : (
                    <Virtuoso 
                        style={{ height: '100%' }} 
                        data={payments} 
                        itemContent={PaymentRow} 
                        endReached={loadMorePayments}
                        components={{ 
                            Footer: () => loadingPayments ? <div className="p-2 text-center text-xs text-muted-foreground border-t"><Loader2 className="animate-spin h-3 w-3 inline mr-2"/>Loading...</div> : null 
                        }}
                    />
                   )}
               </CardContent>
           </Card>
        </div>

        {/* --- DIALOGS (Unchanged Logic, Standardized Look) --- */}
        <Dialog open={!!deleteItem} onOpenChange={() => setDeleteItem(null)}>
            <DialogContent className="sm:max-w-[400px]">
                <DialogHeader>
                    <DialogTitle className="text-red-600 flex items-center gap-2">
                        <Trash2 className="h-5 w-5"/> Confirm Deletion
                    </DialogTitle>
                    <DialogDescription>
                        Are you sure you want to delete this {deleteItem?.type}? This action cannot be undone.
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button variant="outline" onClick={() => setDeleteItem(null)}>Cancel</Button>
                    <Button variant="destructive" onClick={handleDelete}>Delete Permanently</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
        
        <Dialog open={isSaleOpen} onOpenChange={setIsSaleOpen}>
            <DialogContent className="max-w-lg max-h-[80vh] flex flex-col p-0 overflow-hidden">
                <DialogHeader className="p-6 border-b border-slate-100 bg-white flex-shrink-0">
                    <DialogTitle className="flex items-center gap-2 text-xl font-bold text-slate-900">
                        <FileText className="h-5 w-5 text-blue-600"/> Sale Invoice #{selectedSale?.id}
                    </DialogTitle>
                    <div className="flex items-center gap-4 text-sm text-slate-500 mt-2 font-medium">
                        <span className="flex items-center gap-1"><Calendar size={14}/> {selectedSale && new Date(selectedSale.sale_date).toLocaleDateString()}</span>
                        <span className="flex items-center gap-1"><Clock size={14}/> {selectedSale && new Date(selectedSale.sale_date).toLocaleTimeString()}</span>
                    </div>
                </DialogHeader>
                <div className="flex-1 overflow-y-auto p-6 bg-slate-50/50">
                    <div className="space-y-3">
                        {selectedSale?.items.map((item, idx) => (
                            <div key={idx} className="flex justify-between items-center p-4 bg-white rounded-lg border border-slate-200 shadow-sm">
                                <div>
                                    <p className="font-bold text-sm text-slate-800">{item.variant_name}</p>
                                    <p className="text-xs text-slate-500 mt-1 font-medium">Qty: {item.quantity} × ₹{item.price_at_sale}</p>
                                </div>
                                <p className="font-bold text-slate-900">₹{(item.quantity * item.price_at_sale).toFixed(2)}</p>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="p-6 border-t border-slate-200 bg-white flex justify-between items-center">
                    <span className="font-bold text-slate-500 uppercase text-xs tracking-wider">Total Sale Value</span>
                    <span className="font-bold text-2xl text-slate-900">
                        ₹{selectedSale?.items.reduce((s, i) => s + (i.price_at_sale * i.quantity), 0).toFixed(2)}
                    </span>
                </div>
            </DialogContent>
        </Dialog>
        
        <Dialog open={isPaymentOpen} onOpenChange={setIsPaymentOpen}>
            <DialogContent className="sm:max-w-sm">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Banknote className="h-5 w-5 text-green-600"/> Payment Received
                    </DialogTitle>
                </DialogHeader>
                <div className="py-6 space-y-4">
                    <div className="flex justify-between items-center p-3 rounded-lg border bg-slate-50">
                        <span className="text-sm font-medium text-slate-500">Date</span>
                        <span className="font-bold text-slate-900">{selectedPayment && new Date(selectedPayment.payment_date).toLocaleDateString()}</span>
                    </div>
                    <div className="flex justify-between items-center p-4 bg-green-50 border border-green-100 rounded-lg">
                        <span className="text-green-800 font-bold uppercase text-xs tracking-wider">Amount Paid</span>
                        <span className="font-bold text-3xl text-green-700">₹{selectedPayment?.amount.toFixed(2)}</span>
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => setIsPaymentOpen(false)}>Close</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
        
        {/* --- PRINT PREVIEW --- */}
        <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
            <DialogContent className="max-w-4xl h-[90vh] flex flex-col p-0 overflow-hidden">
                <DialogHeader className="p-4 border-b flex-shrink-0">
                    <DialogTitle>Print Preview</DialogTitle>
                </DialogHeader>
                <div className="flex-1 overflow-y-auto bg-slate-100 p-8 flex justify-center">
                    <div className="shadow-xl bg-white scale-90 origin-top">
                        <PrintStatementContent customer={customer} history={combinedHistory} storeConfig={storeConfig} />
                    </div>
                </div>
                <DialogFooter className="p-4 border-t bg-white flex-shrink-0">
                    <Button variant="outline" onClick={() => setIsPreviewOpen(false)}>Close</Button>
                    <Button onClick={handlePrint} className="gap-2 bg-blue-600 hover:bg-blue-700"><Printer size={16}/> Print Now</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
      </div>
    </>
  );
}