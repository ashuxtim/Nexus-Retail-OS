import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { toast } from 'react-toastify';

// --- SENIOR FIX: Safer Polyfill ---
if (typeof window !== 'undefined') {
    if (!("dragEvent" in window)) {
        Object.defineProperty(window, "dragEvent", {
            get: () => undefined,
        });
    }
}
// ----------------------------------

export default function GlobalShortcutListener() {
    const navigate = useNavigate();
    const location = useLocation();
    const [shortcuts, setShortcuts] = useState({});

    // 1. Load Shortcuts on Mount
    const loadShortcuts = useCallback(async () => {
        try {
            const settings = await window.api.getLocalSettings();
            if (settings && settings.shortcuts) {
                setShortcuts(settings.shortcuts);
            }
        } catch (e) {
            console.error("Failed to load shortcuts", e);
        }
    }, []);

    useEffect(() => {
        loadShortcuts();
        const handleUpdate = () => loadShortcuts();
        window.addEventListener('shortcuts-updated', handleUpdate);
        return () => window.removeEventListener('shortcuts-updated', handleUpdate);
    }, [loadShortcuts]);

    // 2. The Global Key Listener
    useEffect(() => {
        const handleKeyDown = (e) => {
            // Ignore if user is typing in an input field (unless it's a function key like F1)
            const isInput = ['INPUT', 'TEXTAREA'].includes(e.target.tagName);
            if (isInput && !e.key.startsWith('F')) return;

            // --- BUILD THE KEY STRING ---
            const keys = [];
            if (e.ctrlKey) keys.push("Ctrl");
            if (e.altKey) keys.push("Alt");
            if (e.shiftKey) keys.push("Shift");
            if (e.metaKey) keys.push("Cmd"); 

            // Ignore modifier-only presses
            if (["Control", "Alt", "Shift", "Meta"].includes(e.key)) return;

            // Normalize key
            let key = e.key.toUpperCase();
            if (key === " ") key = "SPACE";
            if (key.length === 1) key = key.toUpperCase();
            
            keys.push(key);
            const combo = keys.join("+");

            // --- CHECK FOR MATCHES & NAVIGATE ---
            // Using exact paths from your App.js routes
            
            const handleNav = (path, name) => {
                if (location.pathname !== path) {
                    e.preventDefault();
                    navigate(path);
                    toast.info(`Jumped to ${name}`, { autoClose: 1000, hideProgressBar: true, position: "bottom-right" });
                }
            };

            if (combo === shortcuts.nav_dashboard) handleNav("/", "Dashboard");
            if (combo === shortcuts.nav_newsale) handleNav("/sales", "New Sale"); 
            if (combo === shortcuts.nav_products) handleNav("/products", "Inventory");
            if (combo === shortcuts.nav_customers) handleNav("/customers", "Customers");
            if (combo === shortcuts.nav_purchases) handleNav("/purchases", "Purchases");
            
            if (combo === shortcuts.nav_ledger) handleNav("/ledger", "Customer Ledger");
            if (combo === shortcuts.nav_daybook) handleNav("/daybook", "Daybook");
            
            // --- ADDED NEW LISTENER ---
            if (combo === shortcuts.nav_purchase_ledger) handleNav("/purchase-ledger", "Purchase Ledger");

            // Global Actions
            if (combo === shortcuts.action_print) {
                e.preventDefault();
                window.print(); 
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [shortcuts, navigate, location]);

    return null; 
}