import React, { useState, useEffect, Suspense, lazy } from 'react';
import { Routes, Route, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import AiAssistant from './components/AiAssistant';
import { BRAND_CONFIG } from './brand_config';
import ErrorBoundary from './components/ErrorBoundary';
import GlobalShortcutListener from './components/GlobalShortcutListener';

// --- ICONS ---
import {
  LayoutDashboard,
  ShoppingCart,
  Users,
  Package,
  Truck,
  Search,
  Settings,
  BookOpen,
  Menu,
  CalendarCheck,
  Bell,
  Calendar,
  DollarSign,
  FileText,
  Store,
  Sun,
  Moon
} from 'lucide-react';

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

// --- LAZY LOADED PAGES ---
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const ProductPage = lazy(() => import('./pages/ProductPage'));
const CustomerPage = lazy(() => import('./pages/CustomerPage'));
const CustomerLedger = lazy(() => import('./pages/CustomerLedger'));
const CustomerDetailPage = lazy(() => import('./pages/CustomerDetailPage'));
const AddSalePage = lazy(() => import('./pages/AddSalePage'));
const PurchasesPage = lazy(() => import('./pages/PurchasesPage'));
const PurchaseLedger = lazy(() => import('./pages/PurchaseLedger'));
const SupplierDetailsPage = lazy(() => import('./pages/SupplierDetailsPage'));
const SearchResultsPage = lazy(() => import('./pages/SearchResultsPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const DaybookPage = lazy(() => import('./pages/DaybookPage'));

// --- NAVIGATION CONFIG ---
const NAV_ITEMS = [
  { text: 'Dashboard', path: '/', icon: LayoutDashboard },
  { text: 'New Sale', path: '/sales', icon: ShoppingCart },
  { text: 'Daybook', path: '/daybook', icon: CalendarCheck },
  { text: 'Products', path: '/products', icon: Package },
  { text: 'Customers', path: '/customers', icon: Users },
  { text: 'Sales Ledger', path: '/ledger', icon: BookOpen },
  { text: 'Purchases', path: '/purchases', icon: Truck },
  { text: 'Purchase Ledger', path: '/purchase-ledger', icon: FileText },
];

function App() {
  // --- GLOBAL STATE ---
  const [searchTerm, setSearchTerm] = useState('');
  const [notifications, setNotifications] = useState([]);
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('nexus-dark-mode') === 'true');

  // --- DARK MODE ---
  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode);
    localStorage.setItem('nexus-dark-mode', darkMode);
  }, [darkMode]);

  // --- QUICK SETTLE STATE ---
  const [settleOpen, setSettleOpen] = useState(false);
  const [settleCustomer, setSettleCustomer] = useState(null);
  const [settleAmount, setSettleAmount] = useState("");
  const [settleDate, setSettleDate] = useState("");

  const navigate = useNavigate();
  const location = useLocation();

  // --- SEARCH SYNC ---
  useEffect(() => {
    if (location.pathname === '/search') {
      const params = new URLSearchParams(location.search);
      const q = params.get('q') || '';
      if (q !== searchTerm) setSearchTerm(q);
    } else if (searchTerm) {
      setSearchTerm('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.search]);

  const handleSearch = (e) => {
    const term = e.target.value;
    setSearchTerm(term);
    if (term.trim()) {
      navigate(`/search?q=${encodeURIComponent(term)}`);
    } else if (location.pathname === '/search') {
      navigate('/');
    }
  };

  // --- NOTIFICATION POLLING ---
  const fetchNotifications = async () => {
    try {
      const due = await window.api.getDueCustomers();
      setNotifications(due || []);
    } catch (e) {
      console.error("Notification Error", e);
    }
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 300000); // 5 mins
    const handleRefresh = () => fetchNotifications();
    window.addEventListener('refresh-notifications', handleRefresh);
    return () => {
      clearInterval(interval);
      window.removeEventListener('refresh-notifications', handleRefresh);
    };
  }, []);

  // --- SETTLE HANDLERS ---
  const openSettle = (c, e) => {
    e.stopPropagation();
    setSettleCustomer(c);
    setSettleAmount("");
    setSettleDate("");
    setSettleOpen(true);
  };

  const handleConfirmSettle = async () => {
    if (!settleCustomer) return;
    const pay = Number(settleAmount) || 0;
    const remaining = settleCustomer.balance - pay;
    if (remaining > 1 && !settleDate) {
      return toast.warning("Please pick a date for the remaining balance.");
    }
    try {
      const nextDate = remaining > 1 ? settleDate : null;
      await window.api.processCollection({ customerId: settleCustomer.id, amount: pay, nextDate: nextDate });
      toast.success("Updated Successfully!");
      setSettleOpen(false);
      fetchNotifications();
    } catch (e) {
      toast.error("Failed to update.");
    }
  };

  // --- SIDEBAR COMPONENT (Standardized & Fixed) ---
  const SidebarContent = () => (
    <div className={cn("flex flex-col h-full transition-colors", darkMode ? "bg-[#0c0c0c] text-slate-300" : "bg-[#f8f9fb] text-slate-700")}>
      {/* 1. BRANDING HEADER */}
      <div className="px-6 py-8">
        <div className="flex items-center gap-4 mb-2">
          {/* Logo Container */}
          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-blue-600 to-blue-700 flex items-center justify-center text-white shadow-xl shadow-blue-900/30 ring-1 ring-white/10">
            <Store size={24} fill="currentColor" className="text-white drop-shadow-sm" />
          </div>
          <div>
            <h1 className={cn("text-2xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r", darkMode ? "from-white via-white to-blue-200" : "from-slate-900 via-slate-800 to-blue-600")}>
              {BRAND_CONFIG.APP_NAME}
            </h1>
          </div>
        </div>
      </div>

      <Separator className={cn("mx-6 w-auto mb-6", darkMode ? "bg-zinc-800/60" : "bg-slate-200")} />

      {/* 2. NAVIGATION */}
      <nav className="flex-1 px-4 space-y-1.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={() => setIsSheetOpen(false)}
            className={({ isActive }) =>
              cn(
                "group flex items-center gap-3 px-3 py-3 rounded-xl text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-blue-600/90 text-white shadow-md shadow-blue-900/20"
                  : darkMode
                    ? "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                    : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
              )
            }
          >
            {({ isActive }) => (
              <>
                <item.icon
                  size={20}
                  strokeWidth={2}
                  className={cn(
                    "transition-colors",
                    isActive ? "text-white" : darkMode ? "text-slate-500 group-hover:text-slate-300" : "text-slate-400 group-hover:text-slate-600"
                  )}
                />
                <span className={cn(isActive ? "font-semibold" : "")}>{item.text}</span>
                {/* Active Dot Indicator */}
                {isActive && (
                  <div className="ml-auto w-1.5 h-1.5 rounded-full bg-white/80 shadow-[0_0_8px_rgba(255,255,255,0.5)]" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* 3. FOOTER */}
      <div className={cn("p-4 border-t", darkMode ? "border-zinc-900 bg-black/50" : "border-slate-200 bg-white/50")}>
        <NavLink
          to="/settings"
          onClick={() => setIsSheetOpen(false)}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 px-3 py-3 rounded-xl text-sm font-medium transition-colors mb-1",
              isActive
                ? darkMode ? "bg-white/10 text-white" : "bg-slate-100 text-slate-900"
                : darkMode ? "text-slate-500 hover:bg-white/5 hover:text-slate-200" : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            )
          }
        >
          {({ isActive }) => (
            <>
              <Settings size={20} />
              <span>Settings</span>
            </>
          )}
        </NavLink>
      </div>
    </div>
  );

  return (
    <div className={cn("flex h-screen overflow-hidden font-sans transition-colors", darkMode ? "bg-[#0a0a0a] selection:bg-blue-900 selection:text-blue-100" : "bg-muted/30 selection:bg-blue-100 selection:text-blue-900")}>
      <GlobalShortcutListener />
      <ToastContainer position="top-right" autoClose={2000} hideProgressBar theme={darkMode ? "dark" : "colored"} />

      {/* DESKTOP SIDEBAR */}
      <aside className={cn("hidden md:block w-72 flex-shrink-0 border-r z-20 transition-colors", darkMode ? "border-slate-800/60 bg-[#0c0c0c]" : "border-slate-200/60 bg-[#f8f9fb]")}>
        <SidebarContent />
      </aside>

      {/* MOBILE HEADER & CONTENT */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className={cn("h-16 backdrop-blur-md border-b flex items-center justify-between px-6 flex-shrink-0 z-10 sticky top-0 transition-colors", darkMode ? "bg-black/80 border-slate-800" : "bg-white/80 border-slate-200/60")}>
          <div className="flex items-center gap-4 w-full max-w-2xl">
            <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className={cn("md:hidden -ml-2", darkMode ? "text-slate-400" : "text-slate-600")}>
                  <Menu size={20} />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className={cn("p-0 w-72 border-none", darkMode ? "bg-[#0c0c0c] text-white" : "bg-[#f8f9fb] text-slate-800")}>
                <SidebarContent />
              </SheetContent>
            </Sheet>

            {/* Global Search Bar */}
            <div className="relative w-full max-w-sm hidden md:block">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
              <Input
                placeholder="Search anything... (Ctrl+K)"
                className={cn("pl-9 border-transparent transition-all h-9 text-sm rounded-lg", darkMode ? "bg-slate-900 text-slate-200 focus:bg-slate-800 focus:border-slate-600" : "bg-slate-100/50 focus:bg-white focus:border-blue-200")}
                value={searchTerm}
                onChange={handleSearch}
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* DARK MODE TOGGLE */}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setDarkMode(!darkMode)}
              className={cn("rounded-full h-9 w-9 transition-colors", darkMode ? "text-yellow-400 hover:bg-slate-800" : "text-slate-500 hover:text-slate-700 hover:bg-slate-100")}
              title={darkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
            >
              {darkMode ? <Sun size={18} /> : <Moon size={18} />}
            </Button>

            <Sheet>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className={cn("relative rounded-full h-9 w-9", darkMode ? "text-slate-400 hover:text-white hover:bg-slate-800" : "text-slate-500 hover:text-slate-700 hover:bg-slate-100")}>
                  <Bell size={18} />
                  {notifications.length > 0 && (
                    <span className={cn("absolute top-2 right-2.5 h-2 w-2 bg-red-500 rounded-full ring-2", darkMode ? "ring-black" : "ring-white")} />
                  )}
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="w-full sm:max-w-sm p-0">
                <SheetHeader className="p-4 border-b">
                  <SheetTitle className="flex items-center gap-2 text-base">
                    <Bell size={16} className="text-blue-600" />
                    Notifications
                  </SheetTitle>
                </SheetHeader>

                <div className="p-4 space-y-3 overflow-y-auto h-[calc(100vh-80px)] bg-slate-50/50">
                  {notifications.length === 0 ? (
                    <div className="flex flex-col items-center justify-center text-slate-400 py-12 gap-2 text-sm">
                      <Bell size={32} className="opacity-10" />
                      <p>No new alerts</p>
                    </div>
                  ) : (
                    notifications.map(due => (
                      <div key={due.id} className="group bg-white border border-slate-200 shadow-sm rounded-lg p-3 hover:shadow-md transition-all relative overflow-hidden">
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-red-500" />
                        <div className="pl-3 flex justify-between items-start">
                          <div>
                            <div className="font-semibold text-sm text-slate-800">{due.name}</div>
                            <div className="text-xs text-slate-500 flex items-center gap-1 mt-1">
                              <Calendar size={10} /> Due: {new Date(due.next_payment_date).toLocaleDateString()}
                            </div>
                          </div>
                          <Badge variant="destructive" className="h-5 px-1.5 text-[10px]">₹{due.balance}</Badge>
                        </div>
                        <div className="mt-3 pl-3">
                          <Button size="sm" variant="outline" className="w-full h-7 text-xs border-slate-200" onClick={(e) => openSettle(due, e)}>
                            Settle Balance
                          </Button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </SheetContent>
            </Sheet>

            <Separator orientation="vertical" className={cn("h-6 mx-1", darkMode ? "bg-slate-700" : "bg-slate-200")} />

            <AiAssistant />
          </div>
        </header>

        {/* MAIN CONTENT WRAPPER */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden relative scroll-smooth">
          <ErrorBoundary>
            <Suspense fallback={
              <div className="flex items-center justify-center h-[calc(100vh-64px)]">
                <div className="flex flex-col items-center gap-3">
                  <div className="h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                  <p className="text-xs font-medium text-slate-400">Loading...</p>
                </div>
              </div>
            }>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/sales" element={<AddSalePage />} />
                <Route path="/daybook" element={<DaybookPage />} />
                <Route path="/products" element={<ProductPage />} />
                <Route path="/customers" element={<CustomerPage />} />
                <Route path="/customer/:customerId" element={<CustomerDetailPage />} />
                <Route path="/ledger" element={<CustomerLedger />} />
                <Route path="/purchases" element={<PurchasesPage />} />
                <Route path="/purchase-ledger" element={<PurchaseLedger />} />
                <Route path="/purchase-ledger/:id" element={<SupplierDetailsPage />} />
                <Route path="/search" element={<SearchResultsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>

      {/* QUICK SETTLE DIALOG */}
      <Dialog open={settleOpen} onOpenChange={setSettleOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Settle Balance</DialogTitle>
            <DialogDescription>
              Record payment for <span className="font-semibold text-foreground">{settleCustomer?.name}</span>.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="flex justify-between items-center bg-slate-50 p-4 rounded-lg border border-slate-100">
              <span className="text-sm font-medium text-slate-500">Current Due</span>
              <span className="font-mono font-bold text-red-600 text-lg">₹{settleCustomer?.balance}</span>
            </div>

            <div className="space-y-2">
              <Label>Amount Collected</Label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  type="number"
                  className="pl-9 font-bold text-lg h-11"
                  placeholder="0.00"
                  value={settleAmount}
                  onChange={(e) => setSettleAmount(e.target.value)}
                  autoFocus
                />
              </div>
            </div>

            {(settleCustomer?.balance - (Number(settleAmount) || 0)) > 1 && (
              <div className="space-y-2 animate-in fade-in slide-in-from-top-1">
                <Label className="text-blue-600 text-xs font-semibold uppercase">Next Reminder Date</Label>
                <Input
                  type="date"
                  value={settleDate}
                  onChange={(e) => setSettleDate(e.target.value)}
                  className="border-blue-200 focus-visible:ring-blue-500"
                />
                <p className="text-[10px] text-slate-400">Required because a balance remains.</p>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setSettleOpen(false)}>Cancel</Button>
            <Button onClick={handleConfirmSettle} className="bg-green-600 hover:bg-green-700 w-full sm:w-auto">
              Confirm Payment
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default App;