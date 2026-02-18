import React, { useState, useEffect, useRef } from 'react';
import { 
  Plus, Search, Edit2, Trash2, ChevronDown, ChevronRight, 
  Package, AlertTriangle, Box, Tag, Loader2 
} from 'lucide-react';
import { toast } from 'react-toastify';
import { Virtuoso } from 'react-virtuoso';

// --- SHADCN IMPORTS ---
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription 
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const PAGE_SIZE = 50;

const ProductPage = () => {
  // Data States
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true); // Initial load
  const [loadingMore, setLoadingMore] = useState(false); // Pagination load
  const [searchTerm, setSearchTerm] = useState('');
  
  // Pagination States
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  // UI States
  const [expandedRow, setExpandedRow] = useState(null);
  
  // --- KEYBOARD NAVIGATION STATE ---
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const listRef = useRef(null); 
  
  // --- FORM STATES ---
  const [showModal, setShowModal] = useState(false);
  const [isEdit, setIsEdit] = useState(false);
  
  // --- DELETE CONFIRMATION STATES ---
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [productToDelete, setProductToDelete] = useState(null);

  const [isVariantMode, setIsVariantMode] = useState(false);
  const [selectedParent, setSelectedParent] = useState(null);

  const [variantDeleteDialogOpen, setVariantDeleteDialogOpen] = useState(false);
  const [variantToDelete, setVariantToDelete] = useState(null);

  // Form Data
  const [formData, setFormData] = useState({
    name: '',
    category: '',
    variantName: 'Standard',
    price: '',
    unit: 'pcs',
    stock: ''
  });

  // Initial Load & Search Effect
  // Ref to track if the component has mounted
  const isMounted = useRef(false);

  // 1. INITIAL LOAD (Instant)
  useEffect(() => {
    loadProducts(true);
  }, []);

  // 2. SEARCH LISTENER (Debounced)
  useEffect(() => {
    // Skip the first run so we don't double-fetch or delay the initial load
    if (isMounted.current) {
      const timer = setTimeout(() => {
        loadProducts(true);
      }, 500);
      return () => clearTimeout(timer);
    } else {
      isMounted.current = true;
    }
  }, [searchTerm]);

  const loadProducts = async (reset = false) => {
    // Prevent duplicate fetches
    if (!reset && (loadingMore || !hasMore)) return;

    if (reset) {
      setLoading(true);
      setPage(1);
      setHasMore(true);
      setHighlightedIndex(0); // Reset keyboard selection on new search
    } else {
      setLoadingMore(true);
    }

    try {
      const currentPage = reset ? 1 : page;
      
      const data = await window.api.getProducts({ 
        page: currentPage, 
        limit: PAGE_SIZE,
        search: searchTerm 
      });
      
      const newData = Array.isArray(data) ? data : [];

      if (reset) {
        setProducts(newData);
        setLoading(false);
      } else {
        setProducts(prev => [...prev, ...newData]);
        setLoadingMore(false);
      }

      // Check if we reached the end
      if (newData.length < PAGE_SIZE) {
        setHasMore(false);
      } else {
        // Increment page only if we successfully loaded a full batch
        setPage(prev => (reset ? 2 : prev + 1));
      }

    } catch (error) {
      console.error("Failed to load products:", error);
      toast.error("Failed to load inventory");
      setLoading(false);
      setLoadingMore(false);
    }
  };

  // --- KEYBOARD NAVIGATION HANDLER ---
  const handleKeyDown = (e) => {
    if (products.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex(prev => {
        const next = Math.min(prev + 1, products.length - 1);
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
      const selected = products[highlightedIndex];
      if (selected) {
        toggleRow(selected.id);
      }
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (isEdit) {
        // SCENARIO 1: Edit Parent Product (Warning Removed)
        await window.api.updateProduct({
          id: selectedParent.id,
          name: formData.name,
          category: formData.category
        });
        toast.success("Product Updated!");

      } else if (isVariantMode) {
        // SCENARIO 2: Quick Add Variant
        await window.api.createVariant({
          productId: selectedParent.id,
          name: formData.variantName,
          price: parseFloat(formData.price),
          unit: formData.unit,
          stock: parseInt(formData.stock)
        });
        toast.success("Variant Added!");

      } else {
        // SCENARIO 3: Create Brand New Product
        await window.api.createFullProduct({
          name: formData.name,
          category: formData.category,
          variantName: formData.variantName,
          price: parseFloat(formData.price),
          unit: formData.unit,
          stock: parseInt(formData.stock)
        });
        toast.success("Product Created!");
      }

      setShowModal(false);
      resetForm();
      loadProducts(true);
    } catch (error) {
      console.error("Operation failed:", error);
      toast.error("Failed: " + error.message);
    }
  };

  const confirmDelete = (product) => {
    setProductToDelete(product);
    setDeleteDialogOpen(true);
  };

  const executeDelete = async () => {
    if (!productToDelete) return;
    try {
      await window.api.deleteProduct(productToDelete.id);
      toast.success("Product Deleted");
      setDeleteDialogOpen(false);
      setProductToDelete(null);
      loadProducts(true); // Reset list on delete
    } catch (error) {
      console.error("Delete failed:", error);
      toast.error("Failed to delete. Product may have sales history.");
    }
  };

  // 1. Opens the smooth dialog
  const confirmVariantDelete = (variantId) => {
    setVariantToDelete(variantId);
    setVariantDeleteDialogOpen(true);
  };

  // 2. Actually performs the delete when confirmed
  const executeVariantDelete = async () => {
    if (!variantToDelete) return;
    try {
      await window.api.deleteVariant(variantToDelete);
      toast.success("Variant deleted successfully");
      setVariantDeleteDialogOpen(false);
      setVariantToDelete(null);
      loadProducts(false); // Refresh list
    } catch (e) {
      toast.error("Failed to delete variant");
    }
  };

  const handleEditClick = (e, product) => {
    e.stopPropagation();
    setIsEdit(true);
    setIsVariantMode(false); // Ensure we are not in variant mode
    setSelectedParent(product);
    setFormData(prev => ({...prev, name: product.name, category: product.category}));
    setShowModal(true);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      category: '',
      variantName: 'Standard',
      price: '',
      unit: 'pcs',
      stock: ''
    });
    setIsEdit(false);
    setIsVariantMode(false); // Reset this too
    setSelectedParent(null);
  };

  const toggleRow = (id) => {
    setExpandedRow(expandedRow === id ? null : id);
  };

  const handleOpenChange = (open) => {
    setShowModal(open);
    if (!open) resetForm();
  };

  // NEW: Trigger "Quick Add Variant" mode
  const handleAddVariantClick = (e, product) => {
    e.stopPropagation();
    setIsVariantMode(true);
    setSelectedParent(product);
    
    // Pre-fill parent data but keep other fields empty for new variant
    setFormData({
      name: product.name,
      category: product.category,
      variantName: '',
      price: '',
      unit: 'pcs',
      stock: ''
    });
    setShowModal(true);
  };

  // NEW: Handle deleting a specific variant
  const handleDeleteVariant = async (variantId) => {
    if (!confirm("Are you sure you want to delete this variant?")) return;
    try {
      await window.api.deleteVariant(variantId);
      toast.success("Variant deleted");
      loadProducts(false); // Refresh list
    } catch (e) {
      toast.error("Failed to delete variant");
    }
  };

  // --- GRID DEFINITION ---
  // 50px (Chevron) | 1fr (Name) | 150px (Category) | 100px (Stock) | 100px (Variants) | 100px (Actions)
  const GRID_CLASS = "grid grid-cols-[50px_1fr_150px_100px_100px_100px] gap-4 items-center";

  return (
    <div className="max-w-[1600px] mx-auto space-y-6 p-6 animate-in fade-in duration-500 pb-20 h-[calc(100vh-40px)] flex flex-col">
      
      {/* HEADER & ACTIONS */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 flex-shrink-0">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Inventory</h1>
          <p className="text-muted-foreground mt-1">
            Manage your catalog, stock levels, and product variants.
          </p>
        </div>
        <Button onClick={() => { resetForm(); setShowModal(true); }}>
          <Plus className="mr-2 h-4 w-4" /> Add Product
        </Button>
      </div>

      <Separator className="flex-shrink-0" />

      {/* FILTER & DATA CARD */}
      <Card className="flex-1 flex flex-col overflow-hidden shadow-sm border-border">
        <CardHeader className="p-4 pb-2 flex-shrink-0">
          <div className="flex items-center justify-between">
            <div className="relative w-full max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search products... (Use Arrow Keys)"
                className="pl-9"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={handleKeyDown} // Attached Keyboard Listener
                autoFocus
              />
            </div>
            <div className="text-sm text-muted-foreground">
               {loading ? '...' : products.length} Loaded
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0 flex-1 min-h-0">
          {loading ? (
            <div className="h-full flex items-center justify-center text-muted-foreground">
               <Loader2 className="animate-spin mr-2 h-4 w-4" /> Loading inventory...
            </div>
          ) : products.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground gap-2">
              <Package className="h-10 w-10 opacity-20" />
              <p>No products found</p>
            </div>
          ) : (
            <div className="h-full">
              {/* VIRTUALIZED LIST HEADER (Sticky) */}
              <div className={`bg-muted/50 border-b border-border px-4 py-3 text-xs font-medium text-muted-foreground ${GRID_CLASS}`}>
                <div></div>
                <div>Product Name</div>
                <div>Category</div>
                <div className="text-right">Total Stock</div>
                <div className="text-right">Variants</div>
                <div className="text-right">Actions</div>
              </div>

              {/* VIRTUALIZED ROWS */}
              <Virtuoso
                ref={listRef} // Attached Ref
                style={{ height: 'calc(100% - 45px)' }}
                data={products}
                endReached={() => loadProducts(false)}
                overscan={200}
                components={{
                  Footer: () => loadingMore ? (
                    <div className="py-4 flex justify-center text-sm text-muted-foreground bg-muted/20 border-t border-border">
                      <Loader2 className="animate-spin mr-2 h-4 w-4" /> Loading more...
                    </div>
                  ) : null
                }}
                itemContent={(index, product) => {
                  const isHighlighted = index === highlightedIndex;
                  return (
                    <div className="border-b border-border">
                      <div 
                        className={`
                          px-4 py-3 cursor-pointer transition-colors group ${GRID_CLASS}
                          ${isHighlighted ? "bg-accent text-accent-foreground" : "hover:bg-muted/50"}
                          ${expandedRow === product.id && !isHighlighted ? "bg-muted/30" : ""}
                        `}
                        onClick={() => toggleRow(product.id)}
                      >
                        <div>
                          <Button variant="ghost" size="icon" className="h-6 w-6">
                            {expandedRow === product.id ? (
                              <ChevronDown className="h-4 w-4" />
                            ) : (
                              <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            )}
                          </Button>
                        </div>
                        <div className="font-medium text-sm text-foreground">
                          {product.name}
                        </div>
                        <div>
                          <Badge variant="secondary" className="font-normal">
                            {product.category || 'Uncategorized'}
                          </Badge>
                        </div>
                        <div className="text-right font-mono text-sm text-muted-foreground">
                          {product.variants?.reduce((sum, v) => sum + (v.current_stock || 0), 0) || 0}
                        </div>
                        <div className="text-right text-sm text-muted-foreground">
                          {product.variants?.length || 0}
                        </div>
                        <div className="text-right flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
  {/* NEW: Plus Button for Quick Add */}
  <Button 
    variant="ghost" 
    size="icon" 
    title="Add Variant"
    className="h-8 w-8 text-muted-foreground hover:text-green-600"
    onClick={(e) => handleAddVariantClick(e, product)}
  >
    <Plus className="h-4 w-4" />
  </Button>

  <Button 
    variant="ghost" 
    size="icon" 
    title="Edit Product Details"
    className="h-8 w-8 text-muted-foreground hover:text-primary"
    onClick={(e) => handleEditClick(e, product)}
  >
    <Edit2 className="h-4 w-4" />
  </Button>
  
  <Button 
    variant="ghost" 
    size="icon" 
    className="h-8 w-8 text-muted-foreground hover:text-destructive"
    onClick={(e) => { e.stopPropagation(); confirmDelete(product); }}
  >
    <Trash2 className="h-4 w-4" />
  </Button>
</div>
                      </div>

                      {/* EXPANDED SECTION */}
                      {expandedRow === product.id && (
                        <div className="bg-muted/20 px-4 py-4 pl-16 border-t border-border shadow-inner">
                          <div className="space-y-3 max-w-3xl">
                            <h4 className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
                              <Tag className="h-3 w-3" /> Variant Details
                            </h4>
                            <div className="rounded-md border border-border bg-background overflow-hidden shadow-sm">
                              <Table>
                                <TableHeader className="bg-muted/30">
                                  <TableRow className="hover:bg-transparent">
                                    <TableHead className="h-8 text-xs font-medium">Variant Name</TableHead>
                                    <TableHead className="h-8 text-xs font-medium text-right">Price</TableHead>
                                    <TableHead className="h-8 text-xs font-medium text-right">Stock Level</TableHead>
                                    <TableHead className="h-8 text-xs font-medium text-right">Unit</TableHead>
                                  </TableRow>
                                </TableHeader>
                                <TableBody>
  {product.variants?.map((variant) => (
    <TableRow key={variant.id} className="hover:bg-transparent">
      <TableCell className="py-2 text-sm font-medium text-foreground">{variant.name}</TableCell>
      <TableCell className="py-2 text-right font-mono text-sm text-primary font-medium">
        ₹{variant.price}
      </TableCell>
      <TableCell className="py-2 text-right">
        <Badge 
          variant={variant.current_stock < 10 ? "destructive" : "outline"}
          className={variant.current_stock >= 10 ? "bg-green-50/50 text-green-700 border-green-200" : ""}
        >
          {variant.current_stock}
        </Badge>
      </TableCell>
      <TableCell className="py-2 text-right text-muted-foreground text-sm">
        {variant.unit}
      </TableCell>
      {/* NEW: Surgical Delete for Variant */}
      <TableCell className="py-2 text-right">
         <Button 
           variant="ghost" size="icon" className="h-6 w-6 text-red-400 hover:text-red-600"
           onClick={() => confirmVariantDelete(variant.id)}
         >
           <Trash2 className="h-3 w-3" />
         </Button>
      </TableCell>
    </TableRow>
  ))}
</TableBody>
                              </Table>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                }}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* --- ADD/EDIT MODAL --- */}
      <Dialog open={showModal} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>{isEdit ? 'Edit Product' : 'Add New Product'}</DialogTitle>
            <DialogDescription>
              {isEdit ? 'Update product details.' : 'Create a new product with initial stock.'}
            </DialogDescription>
          </DialogHeader>
          
          <form onSubmit={handleSubmit} className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
  <Label>Product Name <span className="text-red-500">*</span></Label>
  <Input
    name="name"
    required
    placeholder="e.g. Basmati Rice"
    value={formData.name}
    onChange={handleInputChange}
    // NEW: Lock if adding variant OR editing
    disabled={isVariantMode || isEdit} 
    className={(isVariantMode || isEdit) ? "bg-muted" : ""}
  />
</div>
<div className="space-y-2">
  <Label>Category</Label>
  <Input
    name="category"
    placeholder="e.g. Grains"
    value={formData.category}
    onChange={handleInputChange}
    // NEW: Lock if adding variant (optional: keep editable if you want to allow changing category while adding variant)
    disabled={isVariantMode}
    className={isVariantMode ? "bg-muted" : ""}
  />
</div>
            </div>

            {/* Initial Stock Fields (Hidden on Edit) */}
            {!isEdit && (
              <div className="rounded-lg border bg-muted/30 p-4 space-y-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <Box className="h-4 w-4" /> Initial Stock Setup
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs">Variant Name</Label>
                    <Input name="variantName" className="h-8 bg-background" required value={formData.variantName} onChange={handleInputChange} />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Unit</Label>
                    <select
                      name="unit"
                      className="flex h-8 w-full rounded-md border border-input bg-background px-3 text-xs ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      value={formData.unit}
                      onChange={handleInputChange}
                    >
                      <option value="pcs">Pieces (pcs)</option>
                      <option value="kg">Kilogram (kg)</option>
                      <option value="ltr">Liter (ltr)</option>
                      <option value="box">Box</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Selling Price (₹)</Label>
                    <Input name="price" type="number" step="0.01" className="h-8 bg-background" required placeholder="0.00" value={formData.price} onChange={handleInputChange} />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Initial Quantity</Label>
                    <Input name="stock" type="number" className="h-8 bg-background" required placeholder="0" value={formData.stock} onChange={handleInputChange} />
                  </div>
                </div>
              </div>
            )}

            

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" onClick={() => setShowModal(false)}>Cancel</Button>
              <Button type="submit">{isEdit ? 'Save Changes' : 'Create Product'}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* --- DELETE CONFIRMATION MODAL --- */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="h-5 w-5" />
              Delete Product
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete <span className="font-semibold text-foreground">{productToDelete?.name}</span>? 
              <br/>This action cannot be undone and will remove all associated variants.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
            <Button 
              variant="destructive" 
              onClick={executeDelete}
            >
              Delete Product
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* --- VARIANT DELETE CONFIRMATION MODAL --- */}
      <Dialog open={variantDeleteDialogOpen} onOpenChange={setVariantDeleteDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="h-5 w-5" />
              Delete Variant
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this variant option? 
              <br/>This will remove it from stock but keep the main product "<strong>{products.find(p => p.variants?.some(v => v.id === variantToDelete))?.name}</strong>".
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setVariantDeleteDialogOpen(false)}>Cancel</Button>
            <Button 
              variant="destructive" 
              onClick={executeVariantDelete}
            >
              Delete Variant
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
    </div>
  );
};

export default ProductPage;