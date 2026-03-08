import React, { 
  useEffect, 
  useState, 
  useRef, 
  memo, 
  useCallback, 
  useMemo 
} from "react";
import { toast } from "react-toastify";
import { Virtuoso } from "react-virtuoso";
import { 
  Truck, 
  Plus, 
  Save, 
  History, 
  Trash2, 
  Loader2, 
  X, 
  Printer, 
  Search, 
  ShoppingCart, 
  FileText, 
  ScanLine, 
  AlertTriangle, 
  UserPlus, 
  PackagePlus,
  RefreshCw 
} from "lucide-react";

// --- SHADCN IMPORTS ---
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogFooter, 
  DialogDescription 
} from "@/components/ui/dialog";
import { 
  Sheet, 
  SheetContent, 
  SheetHeader, 
  SheetTitle, 
  SheetDescription 
} from "@/components/ui/sheet";

// IMPORT THE NEW SHARED MODAL
import InvoiceDetailModal from "@/components/InvoiceDetailModal";

// --- SAFER POLYFILL ---
if (typeof window !== "undefined") {
  if (!("dragEvent" in window)) {
    Object.defineProperty(window, "dragEvent", { get: () => undefined });
  }
}

const HISTORY_LIMIT = 50;

// ============================================================================
// COMPONENT: AsyncSupplierSelect (STANDARDIZED)
// ============================================================================
const AsyncSupplierSelect = memo(({ 
  onSelect, 
  selectedId, 
  selectedNameDisplay, 
  onCreateNew 
}) => {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  
  const wrapperRef = useRef(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const abortControllerRef = useRef(null);

  useEffect(() => {
    const timer = setTimeout(async () => {
      if (!query && !isOpen) return;
      
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();
      
      setLoading(true);
      try {
        const list = await window.api.fuzzySearch({ query, type: 'supplier', limit: 20 });
        
        if (query.length > 1 && list.length === 0) {
          list.unshift({ _special: 'create', name: `+ Create "${query}"`, rawName: query });
        }
        setOptions(list);
        setHighlightedIndex(0);
      } catch (e) {
        if (e.name !== 'AbortError') console.error(e);
      } finally {
        setLoading(false);
      }
    }, 200); 

    return () => {
      clearTimeout(timer);
      if (abortControllerRef.current) abortControllerRef.current.abort();
    };
  }, [query, isOpen]);

  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen && listRef.current) {
      const activeItem = listRef.current.children[highlightedIndex];
      if (activeItem) {
        activeItem.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [highlightedIndex, isOpen]);

  const handleSelect = useCallback((item) => {
    if (item._special === 'create') {
      onCreateNew(item.rawName);
      setIsOpen(false);
      setQuery("");
    } else {
      onSelect(item);
      setIsOpen(false);
      setQuery("");
    }
  }, [onSelect, onCreateNew]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex(prev => Math.min(prev + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === "Enter" && isOpen && options.length > 0) {
      e.preventDefault();
      handleSelect(options[highlightedIndex]);
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  }, [options, highlightedIndex, isOpen, handleSelect]);

  return (
    <div ref={wrapperRef} style={{ position: 'relative' }}>
      <div className="relative">
        <Input
          ref={inputRef}
          type="text"
          value={isOpen ? query : selectedNameDisplay || ""}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!isOpen) setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search Vendor..."
          // STANDARD: Neutral input styling only
          className={`pl-9 ${selectedNameDisplay ? "font-medium" : ""}`}
        />
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
        {selectedNameDisplay && (
           <button 
             onClick={(e) => { e.stopPropagation(); onSelect(null); setTimeout(()=>inputRef.current?.focus(), 50); }} 
             className="absolute right-3 top-2.5 text-muted-foreground hover:text-destructive transition-colors"
           >
             <X size={16}/>
           </button>
        )}
      </div>

      {isOpen && (
        <div ref={listRef} className="absolute z-[9999] w-full mt-1 bg-popover border rounded-md shadow-md max-h-60 overflow-y-auto animate-in fade-in zoom-in-95">
          {loading && (
            <div className="p-3 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
              <Loader2 className="animate-spin" size={14} /> Searching...
            </div>
          )}
          {!loading && options.length === 0 && (
            <div className="p-3 text-center text-sm text-muted-foreground">
              {query ? "No suppliers found" : "Start typing..."}
            </div>
          )}
          {!loading && options.map((item, idx) => (
            <div
              key={item.id || item._special}
              onClick={() => handleSelect(item)}
              // STANDARD: Neutral highlight (bg-accent)
              className={`p-2 px-3 text-sm cursor-pointer flex justify-between items-center border-b border-border last:border-0 ${
                idx === highlightedIndex ? 'bg-accent text-accent-foreground' : 'hover:bg-muted/50'
              } ${item._special === 'create' ? 'text-blue-600 font-medium' : ''}`}
            >
              <div className="flex flex-col">
                <span className="font-medium flex items-center">
                   {item._special === 'create' && <UserPlus className="mr-2" size={14} />}
                   {item.name}
                </span>
                {!item._special && (item.mobile || item.address) && (
                    <span className="text-xs text-muted-foreground">
                        {item.mobile} {item.address ? `• ${item.address}` : ""}
                    </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});
AsyncSupplierSelect.displayName = "AsyncSupplierSelect";

// ============================================================================
// COMPONENT: ProductSearchInput (STANDARDIZED)
// ============================================================================
const ProductSearchInput = memo(function ProductSearchInput({ 
  onSelect, 
  selectedName, 
  nextRef 
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  
  const wrapperRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!query) {
      setResults([]);
      return;
    }
    
    let isActive = true;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await window.api.fuzzySearch({ query, type: 'product', limit: 50 });
        if (isActive) {
          const flat = (res || []).map(v => ({ ...v, name: v.variant_name }));
          setResults(flat);
          setIsOpen(true);
          setHighlightedIndex(0);
        }
      } catch (e) {
        console.error(e);
      } finally {
        if (isActive) setLoading(false);
      }
    }, 200);

    return () => {
      clearTimeout(timer);
      isActive = false;
    };
  }, [query]);

  useEffect(() => {
    if (isOpen && listRef.current) {
      const activeItem = listRef.current.children[highlightedIndex];
      if (activeItem) {
        activeItem.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [highlightedIndex, isOpen]);

  const handleSelect = (v) => {
    onSelect(v);
    setIsOpen(false);
    setQuery("");
    setTimeout(() => nextRef?.current?.focus(), 50);
  };

  const handleKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex(prev => Math.min(prev + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === "Enter" && isOpen && results.length > 0) {
      e.preventDefault();
      handleSelect(results[highlightedIndex]);
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  return (
    <div className="relative" ref={wrapperRef}>
      <div className="relative">
        <Input
          placeholder={selectedName || "Search Product (e.g. Rice)..."}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
          // STANDARD: Neutral styling
          className={`pl-9 ${selectedName ? "font-medium" : ""}`}
        />
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
        {selectedName && (
          <button 
            onClick={() => onSelect(null)} 
            className="absolute right-3 top-2.5 text-muted-foreground hover:text-destructive transition-colors"
          >
            <X size={16} />
          </button>
        )}
      </div>
      {isOpen && results.length > 0 && (
        <div ref={listRef} className="absolute z-50 w-full mt-1 bg-popover border rounded-md shadow-md max-h-48 overflow-auto animate-in fade-in zoom-in-95">
          {results.map((v, i) => (
            <div
              key={i}
              // STANDARD: Neutral styling
              className={`p-2 px-3 text-sm cursor-pointer border-b border-border last:border-0 ${
                i === highlightedIndex ? 'bg-accent text-accent-foreground' : 'hover:bg-muted/50'
              }`}
              onClick={() => handleSelect(v)}
            >
              <p className="font-medium text-foreground">{v.product_name} - {v.name}</p>
              <p className="text-xs text-muted-foreground">Stock: {v.current_stock}</p>
            </div>
          ))}
        </div>
      )}
      {loading && (
        <Loader2 size={14} className="absolute right-3 top-3 animate-spin text-muted-foreground" />
      )}
    </div>
  );
});
ProductSearchInput.displayName = "ProductSearchInput";

// ============================================================================
// COMPONENT: PrintGRNContent (Unchanged - Print Logic)
// ============================================================================
const PrintGRNContent = React.forwardRef(function PrintGRNContent({ data, storeConfig }, ref) {
  if (!data) return null;
  const name = storeConfig?.name || storeConfig?.store_name || "NexusRetail OS";
  const address = storeConfig?.address || storeConfig?.store_address || "";
  const phone = storeConfig?.phone || storeConfig?.mobile || "";

  return (
    <div ref={ref} className="p-8 font-mono text-black bg-white w-full max-w-[800px] mx-auto">
      <div className="text-center mb-6 border-b border-black pb-4">
        <h1 className="text-2xl font-bold">{name}</h1>
        {address && <p className="text-xs">{address}</p>}
        {phone && <p className="text-xs">Ph: {phone}</p>}
        <p className="text-sm mt-1 font-bold border-t border-black pt-1 inline-block">GOODS RECEIPT NOTE</p>
      </div>
      <div className="flex justify-between mb-6 text-sm">
        <div><p><strong>Supplier:</strong> {data.supplierName}</p></div>
        <div><p><strong>Date:</strong> {data.date}</p></div>
      </div>
      <table className="w-full text-sm mb-6">
        <thead>
          <tr className="border-b border-black text-left">
             <th className="py-2">Item</th>
             <th className="text-right py-2">Qty</th>
             <th className="text-right py-2">Cost</th>
             <th className="text-right py-2">Total</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((it, i) => (
            <tr key={i} className="border-b border-dotted border-gray-300">
              <td className="py-2">{it.name} <span className="text-xs text-gray-500">{it.variant}</span></td>
              <td className="text-right py-2">{it.qty}</td>
              <td className="text-right py-2">₹{it.price.toFixed(2)}</td>
              <td className="text-right py-2">₹{(it.qty * it.price).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="font-bold border-t-2 border-black">
            <td colSpan="3" className="text-right py-2">TOTAL:</td>
            <td className="text-right py-2">₹{data.total.toFixed(2)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
});

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================
export default function PurchasesPage() {
  const [history, setHistory] = useState([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [hasMoreHistory, setHasMoreHistory] = useState(true);
  
  const [cart, setCart] = useState([]);
  const [selectedSupplier, setSelectedSupplier] = useState(null);
  const [invoiceDate, setInvoiceDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);
  
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isNewSupplierOpen, setIsNewSupplierOpen] = useState(false);
  const [newSupplier, setNewSupplier] = useState({ name: "", mobile: "", address: "" });
  const [creatingSupplier, setCreatingSupplier] = useState(false);
  const [editingSupplierId, setEditingSupplierId] = useState(null);
  
  const [showInvoiceDetail, setShowInvoiceDetail] = useState(false);
  const [selectedInvoiceDetail, setSelectedInvoiceDetail] = useState(null);
  
  const [storeConfig, setStoreConfig] = useState(null);
  const [showPrintPreview, setShowPrintPreview] = useState(false);
  const [printData, setPrintData] = useState(null);
  
  const [scanning, setScanning] = useState(false);
  const [scanStage, setScanStage] = useState("");
  const [scannedItems, setScannedItems] = useState(null); 
  const [missingProducts, setMissingProducts] = useState([]); 
  const [showAddProductsDialog, setShowAddProductsDialog] = useState(false);
  
  const [editingInvoice, setEditingInvoice] = useState(null);
  const [invoiceToDelete, setInvoiceToDelete] = useState(null);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [pendingSupplierSwitch, setPendingSupplierSwitch] = useState(null);
  
  const [draftItem, setDraftItem] = useState({ variantId: null, qty: 1, price: 0 });
  const [selectedVariantDisplay, setSelectedVariantDisplay] = useState(null);

  const printRef = useRef(null);
  const fileInputRef = useRef(null);
  const qtyInputRef = useRef(null);
  const priceInputRef = useRef(null);

  const cartTotal = useMemo(() => {
    return cart.reduce((sum, item) => sum + (item.qty * item.price), 0);
  }, [cart]);

  // --- API LOGIC (Unchanged) ---
  const fetchHistory = useCallback(async (reset = false) => {
    const page = reset ? 1 : historyPage;
    if (!reset && !hasMoreHistory) return;
    try {
      const res = await window.api.getPurchases({ page, limit: HISTORY_LIMIT });
      const data = res?.data || (Array.isArray(res) ? res : []);
      if (reset) { setHistory(data); setHistoryPage(2); } 
      else { setHistory(prev => [...prev, ...data]); setHistoryPage(prev => prev + 1); }
      setHasMoreHistory(data.length === HISTORY_LIMIT);
    } catch (err) { console.error(err); toast.error("Failed to load history"); }
  }, [historyPage, hasMoreHistory]);

  const handleOpenHistory = useCallback(() => {
    setIsHistoryOpen(true);
    if (history.length === 0) fetchHistory(true);
  }, [history.length, fetchHistory]);

  useEffect(() => {
    const savedCart = localStorage.getItem('purchase_draft_cart');
    const savedSupplier = localStorage.getItem('purchase_draft_supplier_obj');
    if (savedCart) try { setCart(JSON.parse(savedCart)); } catch(e) {}
    if (savedSupplier) try { setSelectedSupplier(JSON.parse(savedSupplier)); } catch(e) {}
    setIsLoaded(true);
  }, []);

  useEffect(() => {
    if (!isLoaded) return;
    localStorage.setItem('purchase_draft_cart', JSON.stringify(cart));
    localStorage.setItem('purchase_draft_supplier_obj', JSON.stringify(selectedSupplier));
  }, [cart, selectedSupplier, isLoaded]);

  useEffect(() => {
    const handleGlobalKeys = (e) => {
        if (e.key === 'F2') { e.preventDefault(); fileInputRef.current?.click(); }
        if (e.key === 'F9') { e.preventDefault(); if (cart.length > 0) handlePrint({ items: cart, supplier_name: selectedSupplier?.name || "N/A", invoice_date: new Date().toISOString(), total_amount: cartTotal }); }
        if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); handleSaveInvoice(); }
    };
    window.addEventListener('keydown', handleGlobalKeys);
    return () => window.removeEventListener('keydown', handleGlobalKeys);
  }, [cart, selectedSupplier, cartTotal]);

  useEffect(() => {
    window.api.getLocalSettings().then(s => {
        let config = {};
        if (Array.isArray(s)) { s.forEach(item => { try { config[item.setting_key] = JSON.parse(item.setting_value); } catch(e) { config[item.setting_key] = item.setting_value; } }); } 
        else { config = s || {}; }
        setStoreConfig(config.store_config || config);
    });
  }, []);

  const processScannedProducts = useCallback(async (items) => {
    if (!items || items.length === 0) return;
    setScanStage("Matching products...");
    try {
      const searchPromises = items.map(item => window.api.searchVariantsWorker(item.product_name, 10).then(variants => ({ item, variants })).catch(() => ({ item, variants: null })));
      const searchResults = await Promise.all(searchPromises);
      const itemsToAdd = [];
      const unmatchedProducts = [];
      for (const { item, variants } of searchResults) {
        const match = variants?.[0]; 
        if (match) {
          itemsToAdd.push({ variantId: match.id, name: match.product_name || match.productname, variant: match.variant_name || match.name, price: item.unit_price || match.price, qty: item.quantity || 1, currentStock: match.current_stock || 0 });
        } else {
          unmatchedProducts.push({ name: item.product_name, price: item.unit_price || 0, quantity: item.quantity || 1 });
        }
      }
      if (itemsToAdd.length > 0) setCart(prev => [...prev, ...itemsToAdd]);
      if (unmatchedProducts.length > 0) {
        setMissingProducts(unmatchedProducts); setShowAddProductsDialog(true); toast.warning(`${itemsToAdd.length} matched, ${unmatchedProducts.length} missing from database`);
      } else {
        toast.success(`✓ Scanned ${itemsToAdd.length} items!`);
      }
      setScannedItems(null);
    } catch (err) { console.error(err); toast.error("Failed to process products"); } finally { setScanStage(""); }
  }, []);

  const handleAddToCart = useCallback(() => {
    if (!selectedSupplier) return toast.warning("Select a Supplier first");
    if (!draftItem.variantId || !draftItem.qty || !draftItem.price) return toast.warning("Complete item details");
    const newItem = { ...draftItem, qty: Number(draftItem.qty), price: Number(draftItem.price), name: selectedVariantDisplay?.product_name, variant: selectedVariantDisplay?.name };
    setCart(prev => [...prev, newItem]);
    setDraftItem({ variantId: null, qty: 1, price: 0 });
    setSelectedVariantDisplay(null);
    toast.success(`Added ${newItem.name}`);
  }, [selectedSupplier, draftItem, selectedVariantDisplay]);

  const handleRemoveFromCart = useCallback((index) => { setCart(prev => prev.filter((_, i) => i !== index)); }, []);

  const handleUpdateQty = useCallback((index, newQty) => {
    const qty = parseFloat(newQty); if (isNaN(qty) || qty <= 0) return;
    setCart(prev => prev.map((item, i) => i === index ? { ...item, qty } : item));
  }, []);

  const handleUpdatePrice = useCallback((index, newPrice) => {
    const price = parseFloat(newPrice); if (isNaN(price) || price < 0) return;
    setCart(prev => prev.map((item, i) => i === index ? { ...item, price } : item));
  }, []);

  const handleQuickCreateSupplierDirect = useCallback(async (supplierName) => {
    if (!supplierName?.trim()) { toast.error("Supplier name required"); return; }
    try {
        const res = await window.api.createSupplier({ name: supplierName, mobile: "", address: "" });
        if (res.error) { toast.error(res.error); } 
        else {
            setSelectedSupplier({ id: res.id, name: res.name });
            toast.success(`✓ ${res.name} created!`);
            if (scannedItems && scannedItems.length > 0) setTimeout(() => processScannedProducts(scannedItems), 100);
        }
    } catch (err) { console.error(err); toast.error("Failed to create supplier"); }
  }, [scannedItems, processScannedProducts]);

  const handleSaveSupplier = useCallback(async () => {
    if (!newSupplier.name.trim()) { toast.error("Name required"); return; }
    setCreatingSupplier(true);
    try {
      let res;
      if (editingSupplierId) res = await window.api.updateSupplier({ id: editingSupplierId, ...newSupplier });
      else res = await window.api.createSupplier(newSupplier);
      if (res.error) { toast.error(res.error); } 
      else {
        toast.success(editingSupplierId ? "Updated!" : "Created!");
        if (!editingSupplierId) { setSelectedSupplier({ id: res.id, name: res.name, ...newSupplier }); if (scannedItems && scannedItems.length > 0) setTimeout(() => processScannedProducts(scannedItems), 100); }
        setIsNewSupplierOpen(false); setNewSupplier({ name: "", mobile: "", address: "" }); setEditingSupplierId(null);
      }
    } catch (err) { console.error(err); toast.error("Failed"); } finally { setCreatingSupplier(false); }
  }, [newSupplier, editingSupplierId, scannedItems, processScannedProducts]);

  const handleSaveInvoice = useCallback(async () => {
    if (!selectedSupplier) { toast.error("Select supplier"); return; }
    if (cart.length === 0) { toast.error("Cart empty"); return; }
    setSaving(true);
    try {
      const items = cart.map(item => ({ variantId: item.variantId, quantity: item.qty, price: item.price }));
      if (editingInvoice) await window.api.deletePurchase(editingInvoice.id);
      const res = await window.api.createPurchaseInvoice({ supplierId: selectedSupplier.id, items, totalAmount: cartTotal, date: invoiceDate || null });
      if (res.error) { toast.error(res.error); } 
      else {
        toast.success(editingInvoice ? "Updated!" : "Saved!");
        setCart([]); setSelectedSupplier(null); localStorage.removeItem('purchase_draft_cart'); localStorage.removeItem('purchase_draft_supplier_obj'); setInvoiceDate(""); setEditingInvoice(null); fetchHistory(true);
      }
    } catch (err) { console.error(err); toast.error("Failed"); } finally { setSaving(false); }
  }, [selectedSupplier, cart, cartTotal, invoiceDate, editingInvoice, fetchHistory]);

  const handleViewInvoiceDetail = useCallback((invoice) => { setSelectedInvoiceDetail(invoice); setShowInvoiceDetail(true); }, []);

  const handleEditInvoice = useCallback((invoice) => {
    if (!invoice || !invoice.items) return;
    setEditingInvoice(invoice);
    setSelectedSupplier({ id: invoice.supplier_id || invoice.supplierId, name: invoice.supplier_name || invoice.suppliername });
    setInvoiceDate(invoice.invoice_date?.split(" ")[0] || "");
    const cartItems = invoice.items.map(item => ({ variantId: item.variant_id, name: item.product_name || item.productname, variant: item.variant_name || item.variantname, price: item.unit_cost || item.unitcost, qty: item.quantity, currentStock: 0 }));
    setCart(cartItems);
    setShowInvoiceDetail(false); setIsHistoryOpen(false); toast.info("Editing invoice");
  }, []);

  const handleDeleteInvoice = useCallback(async () => {
    if (!invoiceToDelete) return;
    try {
      const res = await window.api.deletePurchase(invoiceToDelete.id);
      if (res.error) { toast.error(res.error); } 
      else { toast.success("Deleted!"); fetchHistory(true); if (showInvoiceDetail) setShowInvoiceDetail(false); setInvoiceToDelete(null); }
    } catch (err) { console.error(err); toast.error("Failed"); }
  }, [invoiceToDelete, showInvoiceDetail, fetchHistory]);

  const handleScan = useCallback(async (e) => {
    const file = e.target.files?.[0]; if (!file) return;
    setScanning(true); setScanStage("Reading receipt...");
    try {
      const arrayBuffer = await file.arrayBuffer();
      setScanStage("AI extracting data...");
      const result = await window.api.scanReceipt(arrayBuffer);
      if (result.error) { toast.error(result.error); return; }
      if (result.supplier?.name) {
        let suppliers = await window.api.getSuppliers({ page: 1, limit: 10, search: result.supplier.name });
        let existing = suppliers?.find(s => s.name.toLowerCase() === result.supplier.name.toLowerCase());
        if (!existing) {
          const allSuppliers = await window.api.getSuppliers({ page: 1, limit: 1000, search: "" });
          existing = allSuppliers?.find(s => s.name.toLowerCase() === result.supplier.name.toLowerCase());
        }
        if (existing) { setSelectedSupplier(existing); processScannedProducts(result.items); } 
        else { setScannedItems(result.items); setNewSupplier({ name: result.supplier.name, mobile: result.supplier.mobile || "", address: result.supplier.address || "" }); setIsNewSupplierOpen(true); }
      } else {
        if (!selectedSupplier) { toast.warning("No supplier detected. Select manually."); setScannedItems(result.items); return; }
        processScannedProducts(result.items);
      }
    } catch (err) { console.error(err); toast.error("Scan failed"); } finally { setScanning(false); setScanStage(""); if (fileInputRef.current) fileInputRef.current.value = ""; }
  }, [selectedSupplier, processScannedProducts, scannedItems]);

  const handlePrint = useCallback((invoice) => {
    if (!invoice) return;
    const items = invoice.items || []; 
    const data = {
      supplierName: invoice.supplier_name || invoice.suppliername || selectedSupplier?.name,
      date: new Date(invoice.invoice_date || invoice.invoicedate || new Date()).toLocaleString(),
      items: items.map(item => ({ name: item.product_name || item.productname || item.name, variant: item.variant_name || item.variantname || item.variant, qty: item.quantity || item.qty, price: item.unit_cost || item.unitcost || item.price })),
      total: invoice.total_amount || invoice.totalamount || cartTotal
    };
    setPrintData(data); setShowPrintPreview(true);
  }, [cartTotal, selectedSupplier]);

  const handlePrintNow = useCallback(() => {
    if (printRef.current) {
      const w = window.open('', '_blank'); w.document.write('<html><head><title>Print</title></head><body>'); w.document.write(printRef.current.innerHTML); w.document.write('</body></html>'); w.document.close(); w.focus(); setTimeout(() => { w.print(); w.close(); }, 250);
    }
  }, []);

  const triggerReset = useCallback(() => { if (cart.length > 0) { setShowResetConfirm(true); } else { performReset(); } }, [cart]);

  const performReset = useCallback(() => {
    setCart([]); setSelectedSupplier(null); localStorage.removeItem('purchase_draft_cart'); localStorage.removeItem('purchase_draft_supplier_obj'); setInvoiceDate(""); setEditingInvoice(null); setShowResetConfirm(false); toast.info("Invoice cleared");
  }, []);

  const confirmSupplierSwitch = useCallback(() => {
    if (!pendingSupplierSwitch) return;
    setCart([]); setSelectedSupplier(pendingSupplierSwitch); setPendingSupplierSwitch(null); toast.info("Cart cleared, supplier switched");
  }, [pendingSupplierSwitch]);

  // --- GRID DEFINITION ---
  const CART_GRID = "grid grid-cols-[1fr_80px_100px_100px_40px] gap-4 items-center";

  return (
    <div className="max-w-[1600px] mx-auto space-y-6 p-6 pb-20 animate-in fade-in duration-500 h-[calc(100vh-40px)] flex flex-col">
      <input type="file" ref={fileInputRef} onChange={handleScan} className="hidden" accept="image/*" />
      
      {scanning && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="p-6 max-w-md"><div className="flex items-center gap-3"><Loader2 className="animate-spin" size={24} /><span className="text-lg font-medium">{scanStage}</span></div></Card>
        </div>
      )}
      
      {/* HEADER */}
      <div className="flex flex-col md:flex-row justify-between items-end gap-4 flex-shrink-0">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Incoming Stock</h1>
          <p className="text-muted-foreground mt-1">Create new purchase invoices & manage GRN.</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => fileInputRef.current.click()} variant="outline" className="gap-2">
            <ScanLine size={16}/> Scan Receipt
          </Button>
          <Button variant="ghost" className="text-muted-foreground hover:text-destructive hover:bg-destructive/10" onClick={triggerReset}>
            <RefreshCw size={16} className="mr-2"/> Reset
          </Button>
          <Button variant="outline" className="gap-2" onClick={handleOpenHistory}>
            <History size={16}/> Recent History
          </Button>
        </div>
      </div>
      
      {editingInvoice && (
        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md flex justify-between items-center animate-in slide-in-from-top-2 flex-shrink-0">
          <div className="flex items-center gap-2">
            <AlertTriangle size={18} className="text-yellow-600"/>
            <span className="text-yellow-800 font-medium text-sm">Editing Invoice #{editingInvoice.id}</span>
          </div>
          <Button variant="ghost" size="sm" onClick={triggerReset} className="h-8 w-8 p-0 text-yellow-800 hover:text-yellow-900 hover:bg-yellow-100"><X size={16}/></Button>
        </div>
      )}
      
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-0">
        
        {/* Left Panel: Inputs */}
        <Card className="lg:col-span-4 flex flex-col h-full overflow-hidden shadow-sm border-border">
          <CardHeader className="pb-3 border-b flex-shrink-0">
            <CardTitle className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-2">
              <Truck size={16} className="text-muted-foreground"/> Invoice Details
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6 space-y-6 flex-1 overflow-y-auto">
            <div className="space-y-3">
              <Label className="text-xs font-medium text-muted-foreground uppercase">Select Supplier</Label>
              <div className="flex gap-2">
                <div className="flex-1">
                  <AsyncSupplierSelect
                    selectedNameDisplay={selectedSupplier?.name || ""}
                    selectedId={selectedSupplier?.id}
                    onSelect={(s) => {
                      if (cart.length > 0 && selectedSupplier && s && s.id !== selectedSupplier.id) {
                        setPendingSupplierSwitch(s);
                      } else {
                        setSelectedSupplier(s);
                      }
                    }}
                    onCreateNew={handleQuickCreateSupplierDirect}
                  />
                </div>
                <Button 
                  variant="outline" 
                  size="icon" 
                  className="h-9 w-9 shrink-0"
                  onClick={() => {
                    setEditingSupplierId(null);
                    setNewSupplier({ name: "", mobile: "", address: "" });
                    setIsNewSupplierOpen(true);
                  }}
                >
                  <Plus size={16}/>
                </Button>
              </div>
            </div>

            <Separator/>

            <div className="space-y-4">
              <Label className="text-xs font-medium text-muted-foreground uppercase">Add Items</Label>
              <div className="p-4 bg-muted/10 border rounded-xl space-y-4">
                <ProductSearchInput
                  nextRef={qtyInputRef}
                  onSelect={(v) => {
                    if (v) {
                      setDraftItem(p => ({ ...p, variantId: v.id, price: v.price || 0 }));
                      setSelectedVariantDisplay(v);
                    } else {
                      setDraftItem({ variantId: null, qty: 1, price: 0 });
                      setSelectedVariantDisplay(null);
                    }
                  }}
                  selectedName={selectedVariantDisplay ? `${selectedVariantDisplay.product_name} - ${selectedVariantDisplay.name}` : ""}
                />
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground">Quantity</Label>
                    <Input
                      ref={qtyInputRef}
                      type="number"
                      placeholder="0"
                      className="bg-background h-9"
                      value={draftItem.qty}
                      onChange={(e) => setDraftItem({ ...draftItem, qty: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') priceInputRef.current?.focus();
                      }}
                    />
                  </div>
                  
                  <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground">Unit Cost (₹)</Label>
                    <Input
                      ref={priceInputRef}
                      type="number"
                      placeholder="0.00"
                      step="0.01"
                      className="bg-background h-9"
                      value={draftItem.price}
                      onChange={(e) => setDraftItem({ ...draftItem, price: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleAddToCart();
                      }}
                    />
                  </div>
                </div>
                
                <Button 
                  className="w-full" 
                  onClick={handleAddToCart}
                  disabled={!draftItem.variantId}
                >
                  <ShoppingCart size={16} className="mr-2" /> Add to Bill
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
        
        {/* Right Panel: Draft Bill */}
        <Card className="lg:col-span-8 flex flex-col h-full overflow-hidden shadow-sm border-border">
          <div className="flex justify-between items-center px-6 py-4 border-b flex-shrink-0">
            <div className="flex items-center gap-2">
                <FileText size={16} className="text-muted-foreground"/>
                <h3 className="font-semibold text-sm tracking-tight text-foreground">Draft Bill</h3>
            </div>
            <Badge variant="secondary" className="font-normal">{cart.length} items</Badge>
          </div>

          {/* Sticky Header (Standardized) */}
          <div className={`bg-muted/10 border-b border-border px-6 py-2 text-xs font-medium text-muted-foreground flex-shrink-0 ${CART_GRID}`}>
             <div>Item Name</div>
             <div className="text-center">Qty</div>
             <div className="text-right">Cost</div>
             <div className="text-right">Total</div>
             <div></div>
          </div>

          <div className="flex-1 min-h-0 bg-background">
            {cart.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center p-8">
                <ShoppingCart size={48} className="text-muted-foreground/20 mb-4"/>
                <p className="text-muted-foreground font-medium text-sm">Bill is empty. Scan or add items.</p>
              </div>
            ) : (
                 <Virtuoso
                    style={{ height: '100%' }}
                    data={cart}
                    itemContent={(idx, item) => (
                      <div className={`px-6 py-3 border-b border-border hover:bg-muted/50 transition-colors items-center ${CART_GRID}`}>
                         <div className="min-w-0">
                            <div className="font-medium text-sm text-foreground truncate" title={item.name}>{item.name}</div>
                            <div className="text-xs text-muted-foreground truncate">{item.variant}</div>
                         </div>
                         <div className="flex justify-center">
                            <Input
                              type="number"
                              value={item.qty}
                              onChange={(e) => handleUpdateQty(idx, e.target.value)}
                              className="h-8 w-16 text-xs text-center px-1"
                              min="0.01"
                            />
                         </div>
                         <div className="flex justify-end">
                            <Input
                              type="number"
                              value={item.price}
                              onChange={(e) => handleUpdatePrice(idx, e.target.value)}
                              className="h-8 w-20 text-xs text-right px-1"
                              min="0"
                            />
                         </div>
                         <div className="text-right text-sm font-mono font-medium text-foreground">
                            ₹{(item.qty * item.price).toFixed(2)}
                         </div>
                         <div className="text-right flex justify-end">
                            <Button variant="ghost" size="icon" onClick={() => handleRemoveFromCart(idx)} className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10">
                                <Trash2 size={14} />
                            </Button>
                         </div>
                      </div>
                    )}
                 />
            )}
          </div>
            
          {/* Footer */}
          <div className="p-6 border-t bg-muted/10 space-y-4 flex-shrink-0">
              <div className="flex justify-between items-end">
                <span className="text-sm font-medium text-muted-foreground uppercase tracking-wide">Grand Total</span>
                <span className="text-3xl font-bold text-foreground">₹{cartTotal.toFixed(2)}</span>
              </div>
              
              <Separator />

              <div className="grid grid-cols-2 gap-4">
                <Button 
                  variant="outline" 
                  className="h-11 text-base" 
                  onClick={() => handlePrint({
                    items: cart,
                    supplier_name: selectedSupplier?.name || "N/A",
                    invoice_date: new Date().toISOString(),
                    total_amount: cartTotal
                  })}
                  disabled={cart.length === 0}
                >
                  <Printer size={18} className="mr-2"/> Print (F9)
                </Button>
                <Button 
                  className="h-11 text-base" 
                  onClick={handleSaveInvoice} 
                  disabled={saving || !selectedSupplier || cart.length === 0}
                >
                  {saving ? (
                    <><Loader2 className="animate-spin mr-2" size={18}/> Saving...</> 
                  ) : (
                    <><Save className="mr-2" size={18}/> Save Invoice (Ctrl+S)</>
                  )}
                </Button>
              </div>
          </div>
        </Card>
      </div>
      
      {/* History Sheet */}
      <Sheet open={isHistoryOpen} onOpenChange={setIsHistoryOpen}>
        <SheetContent side="right" className="w-full sm:max-w-xl overflow-y-auto p-0 flex flex-col">
          <SheetHeader className="p-6 border-b bg-muted/20">
            <SheetTitle>Recent History</SheetTitle>
            <SheetDescription>View purchase invoices</SheetDescription>
          </SheetHeader>
          <div className="flex-1">
            <Virtuoso
              style={{ height: '100%' }}
              data={history}
              endReached={() => fetchHistory()}
              itemContent={(_, inv) => (
                <div key={inv.id} className="p-4 border-b hover:bg-muted/50 transition-colors">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-medium flex items-center gap-2">Invoice #{inv.id} <Badge variant="outline" className="text-[10px] font-normal">GRN</Badge></div>
                      <div className="text-sm text-foreground mt-1">{inv.supplier_name}</div>
                      <div className="text-xs text-muted-foreground">{new Date(inv.invoice_date).toLocaleDateString()}</div>
                      <div className="font-medium text-primary mt-1">₹{inv.total_amount}</div>
                    </div>
                    <div className="flex flex-col gap-1">
                      <Button variant="outline" size="sm" onClick={() => handleViewInvoiceDetail(inv)}>
                        View
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            />
          </div>
        </SheetContent>
      </Sheet>
      
      {/* SHARED INVOICE DETAIL MODAL */}
      <InvoiceDetailModal
        isOpen={showInvoiceDetail}
        invoiceId={selectedInvoiceDetail?.id}
        onClose={() => setShowInvoiceDetail(false)}
        onEdit={(details) => handleEditInvoice(details)}
        onPrint={(details) => handlePrint(details)}
        onDelete={(details) => {
            setInvoiceToDelete(details);
            setShowInvoiceDetail(false);
        }}
      />
      
      {/* New Supplier Dialog */}
      {isNewSupplierOpen && (
        <Dialog 
          open={isNewSupplierOpen} 
          onOpenChange={(open) => {
            setIsNewSupplierOpen(open);
            if (!open && scannedItems) {
              setScannedItems(null);
              toast.info("Scan cancelled");
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editingSupplierId ? "Edit" : "Create"} Supplier</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label>Name *</Label>
                <Input value={newSupplier.name} onChange={(e) => setNewSupplier(p => ({...p, name: e.target.value}))}/>
              </div>
              <div>
                <Label>Mobile</Label>
                <Input value={newSupplier.mobile} onChange={(e) => setNewSupplier(p => ({...p, mobile: e.target.value}))}/>
              </div>
              <div>
                <Label>Address</Label>
                <Input value={newSupplier.address} onChange={(e) => setNewSupplier(p => ({...p, address: e.target.value}))}/>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsNewSupplierOpen(false)} disabled={creatingSupplier}>
                Cancel
              </Button>
              <Button onClick={handleSaveSupplier} disabled={creatingSupplier || !newSupplier.name.trim()}>
                {creatingSupplier ? <><Loader2 className="animate-spin mr-2"/> Saving...</> : "Save"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
      
      {/* Print Preview */}
      {showPrintPreview && (
        <Dialog open={showPrintPreview} onOpenChange={setShowPrintPreview}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Print Preview</DialogTitle>
            </DialogHeader>
            <div className="border rounded overflow-hidden">
              <PrintGRNContent ref={printRef} data={printData} storeConfig={storeConfig}/>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowPrintPreview(false)}>Close</Button>
              <Button onClick={handlePrintNow}><Printer size={16} className="mr-2"/> Print</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!invoiceToDelete} onOpenChange={() => setInvoiceToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Invoice?</DialogTitle>
            <DialogDescription>
              This will delete invoice #{invoiceToDelete?.id} and revert stock changes. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setInvoiceToDelete(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteInvoice}>
              <Trash2 size={16} className="mr-2"/> Delete Invoice
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reset Cart Confirmation */}
      <Dialog open={showResetConfirm} onOpenChange={setShowResetConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear Cart?</DialogTitle>
            <DialogDescription>
              This will clear {cart.length} item(s) from your cart and reset the invoice. Continue?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowResetConfirm(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={performReset}>
              <X size={16} className="mr-2"/> Clear Cart
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Switch Supplier Confirmation */}
      <Dialog open={!!pendingSupplierSwitch} onOpenChange={() => setPendingSupplierSwitch(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Switch Supplier?</DialogTitle>
            <DialogDescription>
              Switching to "{pendingSupplierSwitch?.name}" will clear your current cart ({cart.length} items). Continue?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingSupplierSwitch(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmSupplierSwitch}>
              <AlertTriangle size={16} className="mr-2"/> Switch & Clear Cart
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Missing Products Dialog */}
      <Dialog open={showAddProductsDialog} onOpenChange={setShowAddProductsDialog}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Add Missing Products</DialogTitle>
            <DialogDescription>
              These products were not found in your database. Add them now or skip.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-3 py-4">
            {missingProducts.map((product, idx) => (
              <Card key={idx} className="p-3">
                <div className="space-y-2">
                  <div>
                    <Label className="text-xs text-muted-foreground">Product Name</Label>
                    <Input 
                      value={product.name}
                      onChange={(e) => {
                        const updated = [...missingProducts];
                        updated[idx].name = e.target.value;
                        setMissingProducts(updated);
                      }}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <Label className="text-xs text-muted-foreground">Quantity</Label>
                      <Input 
                        type="number"
                        value={product.quantity}
                        onChange={(e) => {
                          const updated = [...missingProducts];
                          updated[idx].quantity = Number(e.target.value);
                          setMissingProducts(updated);
                        }}
                      />
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Price (₹)</Label>
                      <Input 
                        type="number"
                        step="0.01"
                        value={product.price}
                        onChange={(e) => {
                          const updated = [...missingProducts];
                          updated[idx].price = Number(e.target.value);
                          setMissingProducts(updated);
                        }}
                      />
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
          
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => {
                setShowAddProductsDialog(false);
                setMissingProducts([]);
                toast.info("Skipped missing products");
              }}
            >
              Skip
            </Button>
            <Button 
              onClick={async () => {
                toast.info("Adding products to database...");
                try {
                  const createdItems = [];
                  for (const p of missingProducts) {
                    const newProd = await window.api.createProduct({
                      name: p.name,
                      category: "General" 
                    });
                    
                    if (newProd.id) {
                      const newVariant = await window.api.createVariant({
                        productId: newProd.id,
                        name: "Standard",
                        price: p.price,
                        stock: 0,
                        unit: "unit"
                      });
                      
                      if (newVariant.id) {
                        createdItems.push({
                          variantId: newVariant.id,
                          name: p.name,
                          variant: "Standard",
                          price: p.price,
                          qty: p.quantity || 1,
                          currentStock: 0
                        });
                      }
                    }
                  }
                  
                  if (createdItems.length > 0) {
                    setCart(prev => [...prev, ...createdItems]);
                    toast.success(`✓ Added ${createdItems.length} products to database and cart!`);
                  } else {
                    toast.success(`Added ${missingProducts.length} products to database!`);
                  }
                  
                  setShowAddProductsDialog(false);
                  setMissingProducts([]);
                } catch (err) {
                  console.error(err);
                  toast.error("Failed to add products");
                }
              }}
            >
              <PackagePlus size={16} className="mr-2"/> Add All to Database
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}