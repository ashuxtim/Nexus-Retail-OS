import React, { useEffect, useState } from "react";
import { 
  Loader2, Printer, Pencil, Trash2, FileText, Calendar, User, 
  Building2, Receipt, X 
} from "lucide-react";

// --- SHADCN IMPORTS ---
import { 
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription 
} from "@/components/ui/dialog";
import { 
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow 
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export default function InvoiceDetailModal({ 
  invoiceId, 
  isOpen, 
  onClose, 
  onPrint, 
  onEdit, 
  onDelete 
}) {
  const [loading, setLoading] = useState(false);
  const [details, setDetails] = useState(null);

  useEffect(() => {
    if (isOpen && invoiceId) {
      loadDetails();
    } else {
      setDetails(null);
    }
  }, [isOpen, invoiceId]);

  const loadDetails = async () => {
    setLoading(true);
    try {
      const data = await window.api.getInvoiceDetails(invoiceId);
      setDetails(data);
    } catch (err) {
      console.error("Failed to load invoice details", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col p-0 overflow-hidden gap-0">
        
        {/* HEADER */}
        <DialogHeader className="p-6 border-b bg-muted/20 flex-shrink-0">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <DialogTitle className="flex items-center gap-2 text-xl">
                <FileText className="h-5 w-5 text-blue-600" />
                Purchase Invoice #{invoiceId}
              </DialogTitle>
              <DialogDescription>
                Details of stock received and payment status.
              </DialogDescription>
            </div>
            {details && (
              <Badge variant="outline" className="bg-background font-mono">
                {new Date(details.invoicedate || details.invoice_date).toLocaleDateString()}
              </Badge>
            )}
          </div>
        </DialogHeader>

        {/* BODY */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground space-y-4">
              <Loader2 className="animate-spin h-10 w-10 text-primary/20" />
              <p className="text-sm">Retrieving invoice records...</p>
            </div>
          ) : details ? (
            <div className="space-y-6">
              
              {/* INFO CARDS */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="flex items-start gap-4 p-4 rounded-xl border bg-card text-card-foreground shadow-sm">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600 border border-blue-100">
                    <Building2 className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Supplier</p>
                    <p className="font-semibold text-lg leading-tight mt-0.5">
                      {details.suppliername || details.supplier_name}
                    </p>
                    <div className="flex items-center gap-1.5 mt-1.5 text-xs text-muted-foreground">
                       <User className="h-3 w-3" /> 
                       {details.contact_person || "Primary Contact"}
                    </div>
                  </div>
                </div>

                <div className="flex items-start justify-between p-4 rounded-xl border bg-card text-card-foreground shadow-sm">
                  <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50 text-green-600 border border-green-100">
                      <Receipt className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Total Amount</p>
                      <p className="font-bold text-2xl text-green-700 font-mono mt-0.5">
                        ₹{Number(details.totalamount || details.total_amount).toFixed(2)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <Separator />

              {/* ITEMS TABLE */}
              <div className="rounded-md border overflow-hidden">
                <Table>
                  <TableHeader className="bg-muted/50">
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="w-[40%] text-xs font-bold uppercase tracking-wider">Item Description</TableHead>
                      <TableHead className="text-right text-xs font-bold uppercase tracking-wider">Qty</TableHead>
                      <TableHead className="text-right text-xs font-bold uppercase tracking-wider">Unit Cost</TableHead>
                      <TableHead className="text-right text-xs font-bold uppercase tracking-wider">Total</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {details.items?.map((item, idx) => (
                      <TableRow key={idx} className="hover:bg-muted/30">
                        <TableCell>
                          <div className="font-medium text-sm text-foreground">
                            {item.productname || item.product_name}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {item.variantname || item.variant_name}
                          </div>
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {item.quantity}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm text-muted-foreground">
                          ₹{Number(item.unitcost || item.unit_cost).toFixed(2)}
                        </TableCell>
                        <TableCell className="text-right font-bold font-mono text-sm">
                          ₹{(item.quantity * (item.unitcost || item.unit_cost)).toFixed(2)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground space-y-2 opacity-60">
              <FileText className="h-16 w-16 stroke-1" />
              <p>No details found.</p>
            </div>
          )}
        </div>

        {/* FOOTER Actions */}
        <DialogFooter className="p-4 border-t bg-muted/10 flex-shrink-0 flex-col sm:flex-row gap-2">
           <Button variant="outline" onClick={onClose} className="w-full sm:w-auto text-muted-foreground">
             Close
           </Button>
           <div className="flex gap-2 w-full sm:w-auto sm:ml-auto">
               {onEdit && (
                   <Button 
                     variant="outline" 
                     onClick={() => onEdit(details)} 
                     disabled={loading || !details} 
                     className="flex-1 sm:flex-none"
                   >
                       <Pencil className="mr-2 h-4 w-4"/> Edit Invoice
                   </Button>
               )}
               {onPrint && (
                   <Button 
                     variant="outline" 
                     onClick={() => onPrint(details)} 
                     disabled={loading || !details} 
                     className="flex-1 sm:flex-none"
                   >
                       <Printer className="mr-2 h-4 w-4"/> Print GRN
                   </Button>
               )}
               {onDelete && (
                   <Button 
                     variant="destructive" 
                     onClick={() => onDelete(details)} 
                     disabled={loading || !details} 
                     className="flex-1 sm:flex-none"
                   >
                       <Trash2 className="mr-2 h-4 w-4"/> Delete
                   </Button>
               )}
           </div>
        </DialogFooter>
        
      </DialogContent>
    </Dialog>
  );
}