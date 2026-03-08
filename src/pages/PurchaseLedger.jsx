import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Virtuoso } from 'react-virtuoso';
import { 
  Search, Plus, Phone, MapPin, ChevronRight, 
  Building2, Pencil, Users, Loader2 
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { toast } from 'react-toastify';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const PAGE_SIZE = 50;

export default function PurchaseLedger() {
  const [suppliers, setSuppliers] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  
  // Dialog States
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  
  // Keyboard Navigation State
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const listRef = useRef(null); 
  const searchInputRef = useRef(null);

  // Form Data
  const [newSupplier, setNewSupplier] = useState({ name: '', mobile: '', address: '' });
  const [editingSupplier, setEditingSupplier] = useState({ id: null, name: '', mobile: '', address: '' });
  const isMounted = useRef(false);

  const navigate = useNavigate();

  // --- LOAD DATA ---
  // REPLACE your existing loadSuppliers with this:
const loadSuppliers = useCallback(async (reset = false) => {
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
        // Calculate Offset: If resetting, 0. Otherwise, page * 50.
        const offset = reset ? 0 : page * PAGE_SIZE;

        // Use the paginated API instead of the worker
        const response = await window.api.getSuppliers({
            search: search,
            limit: PAGE_SIZE,
            offset: offset
        });

        // Handle response (some endpoints return { data: [...] }, others return [...])
        const newData = response.data || response || [];

        if (reset) {
            setSuppliers(newData);
            setLoading(false);
        } else {
            setSuppliers(prev => [...prev, ...newData]);
            setLoadingMore(false);
        }

        // Check if we reached the end
        if (newData.length < PAGE_SIZE) {
            setHasMore(false);
        } else {
            // Increment page counter for the next offset calculation
            setPage(prev => (reset ? 1 : prev + 1));
        }

    } catch (error) {
        console.error(error);
        toast.error("Failed to load suppliers");
        setLoading(false);
        setLoadingMore(false);
    }
}, [search, page, hasMore, loadingMore]);

  // REPLACE your existing useEffect with this:
useEffect(() => {
    if (isMounted.current) {
        const timer = setTimeout(() => {
            loadSuppliers(true); // <--- Pass true to reset list on search change
        }, 500); 
        return () => clearTimeout(timer);
    } else {
        isMounted.current = true;
        loadSuppliers(true); // Initial load instantly
    }
}, [search]); // Removed loadSuppliers from dependency to prevent loops, search is enough

  // --- KEYBOARD NAVIGATION ---
  const handleKeyDown = (e) => {
    if (suppliers.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex(prev => {
        const next = Math.min(prev + 1, suppliers.length - 1);
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
      const selected = suppliers[highlightedIndex];
      if (selected) {
        navigate(`/purchase-ledger/${selected.id}`);
      }
    }
  };

  // --- ACTIONS: CREATE ---
  const handleCreate = async () => {
    if (!newSupplier.name) return toast.warning("Name is required");
    try {
      const res = await window.api.createSupplier(newSupplier);
      if (res.error) {
        toast.error(res.error);
      } else {
        toast.success("Supplier Created Successfully!");
        setIsAddOpen(false);
        setNewSupplier({ name: '', mobile: '', address: '' });
        loadSuppliers();
      }
    } catch (e) {
      toast.error("Creation failed");
    }
  };

  // --- ACTIONS: UPDATE ---
  const openEditModal = (e, supplier) => {
    e.stopPropagation(); // Stop row click navigation
    setEditingSupplier({ 
      id: supplier.id, 
      name: supplier.name, 
      mobile: supplier.mobile || '', 
      address: supplier.address || '' 
    });
    setIsEditOpen(true);
  };

  const handleUpdate = async () => {
    if (!editingSupplier.name) return toast.warning("Name is required");
    try {
      const res = await window.api.updateSupplier(editingSupplier);
      if (res.error) {
        toast.error(res.error);
      } else {
        toast.success("Supplier Updated Successfully!");
        setIsEditOpen(false);
        loadSuppliers();
      }
    } catch (e) {
      console.error(e);
      toast.error("Update failed");
    }
  };

  // --- ROW RENDERER (Standardized) ---
  const Row = ({ index, item }) => {
    const isHighlighted = index === highlightedIndex;

    return (
      <div 
        onClick={() => navigate(`/purchase-ledger/${item.id}`)}
        className={`
          group flex items-center px-6 py-3 border-b border-border cursor-pointer transition-colors relative
          ${isHighlighted ? 'bg-accent text-accent-foreground' : 'hover:bg-muted/50'}
        `}
      >
        {/* Col 1: Name + Avatar */}
        <div className="flex-1 flex items-center gap-3 min-w-0">
            <div className={`
                h-8 w-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold border
                ${isHighlighted ? 'bg-background text-foreground border-border' : 'bg-muted text-muted-foreground border-border'}
            `}>
                {item.name ? item.name.charAt(0).toUpperCase() : '?'}
            </div>
            <div className="min-w-0">
                <div className="text-sm font-medium truncate text-foreground">
                    {item.name}
                </div>
                {/* Mobile view subtitle */}
                <div className="md:hidden text-xs text-muted-foreground truncate">{item.mobile}</div>
            </div>
        </div>

        {/* Col 2: Contact (Hidden on mobile) */}
        <div className="hidden md:flex w-48 text-sm text-muted-foreground items-center gap-2">
            {item.mobile ? (
                <>
                    <Phone size={12} className="opacity-70" />
                    <span className="truncate">{item.mobile}</span>
                </>
            ) : <span className="text-muted-foreground/50 italic text-xs">No Contact</span>}
        </div>

        {/* Col 3: Address (Hidden on tablet) */}
        <div className="hidden lg:flex flex-1 text-sm text-muted-foreground items-center gap-2 truncate px-4">
             {item.address ? (
                <>
                    <MapPin size={12} className="opacity-70" />
                    <span className="truncate">{item.address}</span>
                </>
             ) : <span className="text-muted-foreground/50 italic text-xs">No Address</span>}
        </div>

        {/* Col 4: Action Buttons */}
        <div className="flex items-center justify-end gap-1 w-20">
            {/* Edit Button - Visible on Hover or Highlight */}
            <Button
              variant="ghost"
              size="icon"
              className={`h-8 w-8 text-muted-foreground hover:text-primary opacity-0 group-hover:opacity-100 transition-opacity ${isHighlighted ? 'opacity-100' : ''}`}
              onClick={(e) => openEditModal(e, item)}
              title="Edit Supplier"
            >
              <Pencil size={14} />
            </Button>
            
            <ChevronRight size={16} className={`transition-transform ${isHighlighted ? 'text-foreground translate-x-1' : 'text-muted-foreground/50'}`} />
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-[1600px] mx-auto space-y-6 animate-in fade-in duration-500 p-6 h-[calc(100vh-40px)] flex flex-col pb-20">
      
      {/* 1. Page Header (Unboxed) */}
      <div className="flex flex-col md:flex-row justify-between items-end gap-4 flex-shrink-0">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Purchase Ledger</h1>
          <p className="text-muted-foreground mt-1 flex items-center gap-2">
             Manage supplier directory and accounts.
          </p>
        </div>
        <Button 
          onClick={() => setIsAddOpen(true)} 
          className="gap-2 shadow-sm"
        >
          <Plus size={16} /> Add Supplier
        </Button>
      </div>

      {/* 2. Search Bar */}
      <div className="relative max-w-md flex-shrink-0">
         <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
         <Input 
          ref={searchInputRef}
          className="pl-10 shadow-sm"
          placeholder="Search suppliers... (Use Arrow Keys)" 
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={handleKeyDown} 
          autoFocus
        />
      </div>

      {/* 3. Supplier Table */}
      <div className="flex-1 border border-border rounded-md overflow-hidden shadow-sm bg-background flex flex-col min-h-0">
        
        {/* Table Header */}
        <div className="flex items-center px-6 py-3 bg-muted/30 border-b border-border flex-shrink-0 text-xs font-medium text-muted-foreground">
            <div className="flex-1 pl-11">Supplier Name</div>
            <div className="hidden md:block w-48">Contact</div>
            <div className="hidden lg:block flex-1 px-4">Address</div>
            <div className="w-20"></div>
        </div>

        {/* List Content */}
        <div className="flex-1 bg-background min-h-0">
            {loading && suppliers.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-3">
                <Loader2 className="animate-spin text-muted-foreground" size={24}/>
                <p className="text-sm text-muted-foreground">Loading directory...</p>
            </div>
            ) : suppliers.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-4">
                <div className="h-16 w-16 bg-muted rounded-full flex items-center justify-center">
                    <Building2 size={32} className="opacity-20" />
                </div>
                <p>No suppliers found.</p>
            </div>
            ) : (
            <Virtuoso
                ref={listRef}
                style={{ height: '100%' }}
                data={suppliers}
                itemContent={(index, item) => <Row index={index} item={item} />}

                endReached={() => loadSuppliers(false)} // Load next page on scroll
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

      {/* 4. Add Dialog */}
      <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Add New Supplier</DialogTitle>
            <DialogDescription>
              Create a new vendor profile for purchase tracking.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Name <span className="text-destructive">*</span></Label>
              <Input 
                value={newSupplier.name} 
                onChange={(e) => setNewSupplier({...newSupplier, name: e.target.value})}
                placeholder="e.g. Metro Wholesalers"
              />
            </div>
            <div className="grid gap-2">
              <Label>Mobile Number</Label>
              <Input 
                value={newSupplier.mobile} 
                onChange={(e) => setNewSupplier({...newSupplier, mobile: e.target.value})}
              />
            </div>
            <div className="grid gap-2">
              <Label>Address</Label>
              <Input 
                value={newSupplier.address} 
                onChange={(e) => setNewSupplier({...newSupplier, address: e.target.value})}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate}>Create Profile</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 5. Edit Dialog */}
      <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Edit Supplier</DialogTitle>
            <DialogDescription>
              Update contact information for this vendor.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Name <span className="text-destructive">*</span></Label>
              <Input 
                value={editingSupplier.name} 
                onChange={(e) => setEditingSupplier({...editingSupplier, name: e.target.value})}
              />
            </div>
            <div className="grid gap-2">
              <Label>Mobile Number</Label>
              <Input 
                value={editingSupplier.mobile} 
                onChange={(e) => setEditingSupplier({...editingSupplier, mobile: e.target.value})}
              />
            </div>
            <div className="grid gap-2">
              <Label>Address</Label>
              <Input 
                value={editingSupplier.address} 
                onChange={(e) => setEditingSupplier({...editingSupplier, address: e.target.value})}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditOpen(false)}>Cancel</Button>
            <Button onClick={handleUpdate}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}