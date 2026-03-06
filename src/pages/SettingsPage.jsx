import React, { useState, useEffect } from "react";
import { toast } from "react-toastify";
import { Key, Store, Keyboard, Save, Loader2, CreditCard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

// --- Safer Polyfill ---
if (typeof window !== 'undefined') {
    if (!("dragEvent" in window)) {
        Object.defineProperty(window, "dragEvent", { get: () => undefined });
    }
}

// --- Shortcut Input Component (Preserved Logic, Updated Visuals) ---
const ShortcutInput = ({ value, onChange }) => {
    const [isRecording, setIsRecording] = useState(false);

    const handleKeyDown = (e) => {
        e.preventDefault();
        e.stopPropagation();

        const keys = [];
        if (e.ctrlKey) keys.push("Ctrl");
        if (e.altKey) keys.push("Alt");
        if (e.shiftKey) keys.push("Shift");
        if (e.metaKey) keys.push("Cmd");

        if (["Control", "Alt", "Shift", "Meta"].includes(e.key)) return;

        let key = e.key.toUpperCase();
        if (key === " ") key = "SPACE";
        if (key.length === 1) key = key.toUpperCase();

        keys.push(key);
        onChange(keys.join("+"));
        setIsRecording(false);
    };

    return (
        <div className="relative group">
            <div
                className={`flex items-center justify-center h-10 w-full rounded-md border text-xs font-bold transition-all cursor-pointer select-none
                ${isRecording
                        ? 'border-blue-500 ring-2 ring-blue-100 bg-white text-blue-700 shadow-sm'
                        : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-white hover:border-slate-300'
                    }`}
                onClick={() => setIsRecording(true)}
                tabIndex={0}
                onBlur={() => setIsRecording(false)}
                onKeyDown={isRecording ? handleKeyDown : undefined}
            >
                {isRecording ? (
                    <span className="animate-pulse">Recording...</span>
                ) : (
                    value ? <kbd className="font-mono">{value}</kbd> : <span className="text-slate-400 italic font-normal">Not Set</span>
                )}
            </div>
            {value && !isRecording && (
                <button
                    onClick={(e) => { e.stopPropagation(); onChange(""); }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                    CLEAR
                </button>
            )}
        </div>
    );
};

export default function SettingsPage() {
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState("general");

    const [apiKeys, setApiKeys] = useState({ google: "", groq: "" });

    const [storeConfig, setStoreConfig] = useState({
        name: "My Grocery Store", address: "", phone: "", gst: "", footerMessage: "Thank you for shopping with us!"
    });

    const [preferences, setPreferences] = useState({
        lowStockLimit: 10, defaultPaymentMode: "Cash"
    });

    const [shortcuts, setShortcuts] = useState({
        "nav_dashboard": "Ctrl+D",
        "nav_newsale": "F1",
        "nav_products": "F2",
        "nav_customers": "F3",
        "nav_purchases": "F4",
        "nav_ledger": "F5",
        "nav_daybook": "F6",
        "nav_purchase_ledger": "F7",
        "action_print": "Ctrl+P",
        "action_save": "Ctrl+S"
    });

    useEffect(() => { loadAllSettings(); }, []);

    const loadAllSettings = async () => {
        setLoading(true);
        try {
            const localData = await window.api.getLocalSettings();
            if (localData) {
                if (localData.store_config) setStoreConfig(prev => ({ ...prev, ...localData.store_config }));
                if (localData.preferences) setPreferences(prev => ({ ...prev, ...localData.preferences }));
                if (localData.shortcuts) setShortcuts(prev => ({ ...prev, ...localData.shortcuts }));
            }

            const remoteData = await window.api.getSettings();
            if (remoteData && !remoteData.error) {
                setApiKeys({ google: remoteData.GOOGLE_API_KEY || "", groq: remoteData.GROQ_API_KEY || "" });
            }
        } catch (e) { console.error("Load failed", e); }
        finally { setLoading(false); }
    };

    const handleSaveGeneral = async () => {
        setLoading(true);
        try {
            await window.api.saveLocalSetting('store_config', storeConfig);
            await window.api.saveLocalSetting('preferences', preferences);
            toast.success("Settings Saved Successfully");
            window.dispatchEvent(new Event('settings-updated'));
        } catch (e) { toast.error("Failed to save"); }
        finally { setLoading(false); }
    };

    const handleSaveShortcuts = async () => {
        setLoading(true);
        try {
            await window.api.saveLocalSetting('shortcuts', shortcuts);
            toast.success("Shortcuts Updated");
            window.dispatchEvent(new Event('shortcuts-updated'));
        } catch (e) { toast.error("Failed to save"); }
        finally { setLoading(false); }
    };

    const handleSaveKeys = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await window.api.saveSettings({ google_api_key: apiKeys.google, groq_api_key: apiKeys.groq });
            if (res.error) throw new Error(res.error);
            toast.success("API Keys Secured");
            window.api.checkBackendHealth();
        } catch (e) { toast.error("Error saving keys: " + e.message); }
        finally { setLoading(false); }
    };

    return (
        <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500 p-6 pb-20">

            {/* HEADER - Clean, matching screenshot */}
            <div className="flex flex-col space-y-1">
                <h1 className="text-3xl font-bold tracking-tight text-slate-900">Settings</h1>
                <p className="text-slate-500">Manage your store profile, preferences, and integrations.</p>
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="grid w-full grid-cols-3 mb-8 h-12 bg-white border border-slate-200 p-1 rounded-xl shadow-sm">
                    <TabsTrigger value="general" className="gap-2 rounded-lg data-[state=active]:bg-slate-100 data-[state=active]:text-slate-900 font-medium text-slate-500">
                        <Store size={16} /> General & Store
                    </TabsTrigger>
                    <TabsTrigger value="shortcuts" className="gap-2 rounded-lg data-[state=active]:bg-slate-100 data-[state=active]:text-slate-900 font-medium text-slate-500">
                        <Keyboard size={16} /> Keyboard Shortcuts
                    </TabsTrigger>
                    <TabsTrigger value="integrations" className="gap-2 rounded-lg data-[state=active]:bg-slate-100 data-[state=active]:text-slate-900 font-medium text-slate-500">
                        <Key size={16} /> AI Integrations
                    </TabsTrigger>
                </TabsList>

                {/* --- GENERAL TAB --- */}
                <TabsContent value="general" className="space-y-6">
                    <Card className="border-slate-200 shadow-sm bg-white">
                        <CardHeader className="pb-0 pt-6 px-6 border-none">
                            <CardTitle className="text-lg font-bold text-slate-900">Store Identity</CardTitle>
                            <CardDescription className="text-slate-500">This information appears on your printed receipts.</CardDescription>
                        </CardHeader>
                        <CardContent className="grid gap-6 pt-6 px-6 pb-8">
                            <div className="space-y-2">
                                <Label className="text-xs font-bold uppercase text-slate-500 tracking-wider">Store Name</Label>
                                <Input className="h-11 border-slate-200 focus:border-blue-500 focus:ring-blue-500" value={storeConfig.name} onChange={e => setStoreConfig({ ...storeConfig, name: e.target.value })} placeholder="e.g. Fresh Mart" />
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase text-slate-500 tracking-wider">Phone Number</Label>
                                    <Input className="h-11 border-slate-200" value={storeConfig.phone} onChange={e => setStoreConfig({ ...storeConfig, phone: e.target.value })} placeholder="+91..." />
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase text-slate-500 tracking-wider">GST / Tax ID</Label>
                                    <Input className="h-11 border-slate-200" value={storeConfig.gst} onChange={e => setStoreConfig({ ...storeConfig, gst: e.target.value })} placeholder="Optional" />
                                </div>
                            </div>
                            <div className="space-y-2">
                                <Label className="text-xs font-bold uppercase text-slate-500 tracking-wider">Address</Label>
                                <Input className="h-11 border-slate-200" value={storeConfig.address} onChange={e => setStoreConfig({ ...storeConfig, address: e.target.value })} placeholder="Shop 12, Main Market..." />
                            </div>
                            <div className="space-y-2">
                                <Label className="text-xs font-bold uppercase text-slate-500 tracking-wider">Receipt Footer</Label>
                                <Input className="h-11 border-slate-200" value={storeConfig.footerMessage} onChange={e => setStoreConfig({ ...storeConfig, footerMessage: e.target.value })} placeholder="Thank you for visiting!" />
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="border-slate-200 shadow-sm bg-white">
                        <CardHeader className="pb-0 pt-6 px-6 border-none">
                            <CardTitle className="text-lg font-bold text-slate-900">Application Preferences</CardTitle>
                            <CardDescription className="text-slate-500">Customize how the application behaves.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6 pt-6 px-6 pb-8">
                            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-100">
                                <div className="space-y-0.5">
                                    <Label className="text-sm font-bold text-slate-800">Low Stock Alert Limit</Label>
                                    <p className="text-xs text-slate-500">Products below this quantity will be flagged red.</p>
                                </div>
                                <Input type="number" className="w-24 h-10 text-center font-bold bg-white" value={preferences.lowStockLimit} onChange={e => setPreferences({ ...preferences, lowStockLimit: Number(e.target.value) })} />
                            </div>

                            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-100">
                                <div className="space-y-0.5">
                                    <Label className="text-sm font-bold text-slate-800">Default Payment Mode</Label>
                                    <p className="text-xs text-slate-500">Pre-select this option on the checkout screen.</p>
                                </div>
                                <select className="flex h-10 w-40 items-center justify-between rounded-md border border-input bg-white px-3 py-2 text-sm ring-offset-background font-medium"
                                    value={preferences.defaultPaymentMode} onChange={e => setPreferences({ ...preferences, defaultPaymentMode: e.target.value })}>
                                    <option value="Cash">Cash</option><option value="UPI">UPI</option><option value="Card">Card</option>
                                </select>
                            </div>
                        </CardContent>
                    </Card>

                    <div className="flex justify-end pt-2">
                        <Button onClick={handleSaveGeneral} disabled={loading} className="w-48 h-11 bg-slate-900 hover:bg-slate-800 text-white shadow-md">
                            {loading ? <Loader2 className="animate-spin mr-2 h-4 w-4" /> : <><Save className="mr-2 h-4 w-4" /> Save Changes</>}
                        </Button>
                    </div>
                </TabsContent>

                {/* --- SHORTCUTS TAB --- */}
                <TabsContent value="shortcuts">
                    <Card className="border-slate-200 shadow-sm bg-white">
                        <CardHeader className="pb-0 pt-6 px-6 border-none">
                            <CardTitle className="text-lg font-bold text-slate-900">Keyboard Shortcuts</CardTitle>
                            <CardDescription className="text-slate-500">Click a box to record a new key combination.</CardDescription>
                        </CardHeader>
                        <CardContent className="pt-8 px-6 pb-8">
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-16 gap-y-10">
                                <div className="space-y-5">
                                    <h4 className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-4 border-b border-blue-100 pb-2">Navigation Keys</h4>
                                    <div className="flex items-center justify-between"><Label className="text-slate-600">Dashboard</Label><div className="w-32"><ShortcutInput value={shortcuts.nav_dashboard} onChange={v => setShortcuts({ ...shortcuts, nav_dashboard: v })} /></div></div>
                                    <div className="flex items-center justify-between"><Label className="text-slate-600">New Sale</Label><div className="w-32"><ShortcutInput value={shortcuts.nav_newsale} onChange={v => setShortcuts({ ...shortcuts, nav_newsale: v })} /></div></div>
                                    <div className="flex items-center justify-between"><Label className="text-slate-600">Products</Label><div className="w-32"><ShortcutInput value={shortcuts.nav_products} onChange={v => setShortcuts({ ...shortcuts, nav_products: v })} /></div></div>
                                    <div className="flex items-center justify-between"><Label className="text-slate-600">Customers</Label><div className="w-32"><ShortcutInput value={shortcuts.nav_customers} onChange={v => setShortcuts({ ...shortcuts, nav_customers: v })} /></div></div>
                                </div>
                                <div className="space-y-5">
                                    <h4 className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-4 border-b border-blue-100 pb-2">Actions & Ledgers</h4>
                                    <div className="flex items-center justify-between"><Label className="text-slate-600">Sales Ledger</Label><div className="w-32"><ShortcutInput value={shortcuts.nav_ledger} onChange={v => setShortcuts({ ...shortcuts, nav_ledger: v })} /></div></div>
                                    <div className="flex items-center justify-between"><Label className="text-slate-600">Purchase Ledger</Label><div className="w-32"><ShortcutInput value={shortcuts.nav_purchase_ledger} onChange={v => setShortcuts({ ...shortcuts, nav_purchase_ledger: v })} /></div></div>
                                    <div className="flex items-center justify-between"><Label className="text-slate-600">Global Save</Label><div className="w-32"><ShortcutInput value={shortcuts.action_save} onChange={v => setShortcuts({ ...shortcuts, action_save: v })} /></div></div>
                                    <div className="flex items-center justify-between"><Label className="text-slate-600">Print Receipt</Label><div className="w-32"><ShortcutInput value={shortcuts.action_print} onChange={v => setShortcuts({ ...shortcuts, action_print: v })} /></div></div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    <div className="flex justify-end pt-6">
                        <Button onClick={handleSaveShortcuts} disabled={loading} className="w-48 h-11 bg-slate-900 hover:bg-slate-800 text-white shadow-md">
                            <Save className="mr-2 h-4 w-4" /> Update Shortcuts
                        </Button>
                    </div>
                </TabsContent>

                {/* --- INTEGRATIONS TAB --- */}
                <TabsContent value="integrations">
                    <Card className="border-slate-200 shadow-sm bg-white">
                        <CardHeader className="pb-0 pt-6 px-6 border-none">
                            <CardTitle className="flex items-center gap-2 text-lg font-bold text-slate-900">
                                API Keys Configuration
                            </CardTitle>
                            <CardDescription className="text-slate-500">Securely store your API keys for AI features. These are stored locally.</CardDescription>
                        </CardHeader>
                        <CardContent className="pt-8 px-6 pb-8">
                            <form onSubmit={handleSaveKeys} className="space-y-6 max-w-2xl">
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase text-slate-500 tracking-wider">Google Gemini API Key</Label>
                                    <Input type="password" className="h-11 font-mono text-sm bg-slate-50 border-slate-200 focus:bg-white" value={apiKeys.google} onChange={e => setApiKeys({ ...apiKeys, google: e.target.value })} placeholder="AIzaSy..." />
                                    <p className="text-[10px] text-slate-400">Used for Chat Assistant and general reasoning.</p>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase text-slate-500 tracking-wider">Groq API Key</Label>
                                    <Input type="password" className="h-11 font-mono text-sm bg-slate-50 border-slate-200 focus:bg-white" value={apiKeys.groq} onChange={e => setApiKeys({ ...apiKeys, groq: e.target.value })} placeholder="gsk_..." />
                                    <p className="text-[10px] text-slate-400">Used for Llama 3 (fast inference) and Whisper (voice commands).</p>
                                </div>
                                <div className="pt-4">
                                    <Button type="submit" className="w-48 h-11 bg-slate-900 hover:bg-slate-800 text-white shadow-md" disabled={loading}>
                                        {loading ? <Loader2 className="animate-spin mr-2" /> : "Securely Save Keys"}
                                    </Button>
                                </div>
                            </form>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}