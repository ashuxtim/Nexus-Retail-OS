import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart, PieChart, Pie, Cell } from 'recharts';
import { Virtuoso } from 'react-virtuoso';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  TrendingUp, Users, Package, DollarSign, AlertTriangle, Activity, 
  Sparkles, ArrowUpRight, ArrowDownRight, LayoutDashboard, 
  AlertCircle, Zap, Clock, Download, Settings, ShoppingCart,
  TrendingDown, Minus, Brain, RefreshCw, CheckCircle
} from 'lucide-react';

// --- SHADCN UI IMPORTS ---
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// ============================================================================
// UTILITY FUNCTIONS (PRESERVED)
// ============================================================================
const safeNum = (val) => {
  const n = Number(val);
  return isNaN(n) ? 0 : n;
};

const safeString = (val) => (val === null || val === undefined) ? "" : String(val);

const safeDate = (dateStr) => {
  try {
    if (!dateStr) return new Date();
    const d = new Date(dateStr);
    return isNaN(d.getTime()) ? new Date() : d;
  } catch {
    return new Date();
  }
};

const formatCurrency = (val) => {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(safeNum(val));
};

const formatCompactNumber = (val) => {
  const num = safeNum(val);
  if (num >= 10000000) return `₹${(num / 10000000).toFixed(1)}Cr`;
  if (num >= 100000) return `₹${(num / 100000).toFixed(1)}L`;
  if (num >= 1000) return `₹${(num / 1000).toFixed(1)}K`;
  return `₹${num}`;
};

// ============================================================================
// NEW UTILITY COMPONENTS
// ============================================================================

// --- SPARKLINE COMPONENT ---
const Sparkline = ({ data = [], color = "#3b82f6", showArea = false }) => {
  if (!data || data.length === 0) return <div className="h-8 w-full bg-muted/20 rounded" />;
  
  const validData = data.map((val, idx) => ({ x: idx, y: safeNum(val) }));
  
  return (
    <ResponsiveContainer width="100%" height={32}>
      <AreaChart data={validData} margin={{ top: 2, right: 0, left: 0, bottom: 2 }}>
        <defs>
          <linearGradient id={`gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        {showArea && <Area type="monotone" dataKey="y" stroke="none" fill={`url(#gradient-${color})`} />}
        <Line type="monotone" dataKey="y" stroke={color} strokeWidth={1.5} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
};

// --- CONFIDENCE METER (ENHANCED BATTERY) ---
const ConfidenceMeter = ({ level, size = "default" }) => {
  const safeLevel = Math.max(0, Math.min(100, safeNum(level)));
  
  let colorClass, bgClass, label;
  if (safeLevel >= 75) {
    colorClass = "bg-emerald-500";
    bgClass = "bg-emerald-500/10";
    label = "High";
  } else if (safeLevel >= 50) {
    colorClass = "bg-yellow-500";
    bgClass = "bg-yellow-500/10";
    label = "Medium";
  } else {
    colorClass = "bg-red-500";
    bgClass = "bg-red-500/10";
    label = "Low";
  }
  
  const heightClass = size === "small" ? "h-2" : "h-3";
  const textSize = size === "small" ? "text-[10px]" : "text-xs";
  
  return (
    <div className="flex items-center gap-2">
      <div className={`relative w-full ${heightClass} ${bgClass} rounded-full overflow-hidden`}>
        <motion.div
          className={`absolute inset-y-0 left-0 ${colorClass} rounded-full`}
          initial={{ width: 0 }}
          animate={{ width: `${safeLevel}%` }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
      </div>
      <span className={`${textSize} font-medium text-muted-foreground whitespace-nowrap`}>
        {safeLevel.toFixed(0)}% {label}
      </span>
    </div>
  );
};

// --- STATUS DOT ---
const StatusDot = ({ status = "neutral" }) => {
  const colors = {
    critical: "bg-red-500 shadow-red-500/50",
    warning: "bg-yellow-500 shadow-yellow-500/50",
    healthy: "bg-emerald-500 shadow-emerald-500/50",
    neutral: "bg-gray-400"
  };
  
  return (
    <span className={`inline-block w-1.5 h-1.5 rounded-full ${colors[status]} shadow-sm`} />
  );
};

// --- ANIMATED AI SUMMARY CHIP ---
const AISummaryChip = ({ text, isProcessing }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-2 px-3 py-1.5 bg-primary/10 border border-primary/20 rounded-full"
    >
      <motion.div
        animate={isProcessing ? { rotate: 360 } : {}}
        transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
      >
        <Sparkles className="w-3.5 h-3.5 text-primary" />
      </motion.div>
      <span className="text-xs font-medium text-primary">{text}</span>
    </motion.div>
  );
};

// --- DATA FRESHNESS BADGE (SELF-CONTAINED) ---
const FreshnessBadge = ({ initialSeconds = 0 }) => {
  const [seconds, setSeconds] = useState(initialSeconds);
  
  useEffect(() => {
    const ticker = setInterval(() => {
      setSeconds(prev => prev + 1);
    }, 1000);
    
    return () => clearInterval(ticker);
  }, []);
  
  const label = seconds < 60 ? `${seconds}s ago` : `${Math.floor(seconds / 60)}m ago`;
  
  return (
    <Badge variant="outline" className="gap-1.5 text-xs font-normal">
      <Clock className="w-3 h-3" />
      {label}
    </Badge>
  );
};

// ============================================================================
// ANIMATION VARIANTS (PRESERVED + ENHANCED)
// ============================================================================
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.1
    }
  }
};

const cardVariants = {
  hidden: { y: 20, opacity: 0, filter: "blur(5px)" },
  visible: {
    y: 0,
    opacity: 1,
    filter: "blur(0px)",
    transition: {
      type: "spring",
      stiffness: 100,
      damping: 15
    }
  }
};

const hoverVariants = {
  rest: { scale: 1, y: 0 },
  hover: {
    scale: 1.01,
    y: -2,
    transition: { duration: 0.2 }
  }
};

// ============================================================================
// MAIN DASHBOARD COMPONENT
// ============================================================================
export default function DashboardPage() {
  // --- STATE (PRESERVED) ---
  const [stats, setStats] = useState({
    total_outstanding_credit: 0,
    total_product_variants: 0,
    total_customers: 0,
    top_customers_by_credit: [],
    low_stock_items: []
  });
  
  const [forecast, setForecast] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [analyticsStatus, setAnalyticsStatus] = useState('processing');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [backendError, setBackendError] = useState(false);
  const [isExpertMode, setIsExpertMode] = useState(false);
  const pollingIntervalRef = useRef(null);
  const fetchAnalyticsRef = useRef(null);
  const lastForecastHashRef = useRef(null);
  
  // --- UI STATE ---
  const [activePanelTab, setActivePanelTab] = useState('debt');
  const [activeMainTab, setActiveMainTab] = useState('overview');
  
  const processForecast = useCallback((fData) => {
    if (!fData || fData.error) return;
    
    const merged = [];
    const recentHistory = fData.history?.slice(-90) || [];
    
    // Process historical data
    recentHistory.forEach(h => {
      merged.push({
        date: safeDate(h.date),
        actual: safeNum(h.sales),
        predicted: null,
        lower_80: null,
        upper_80: null,
        lower_95: null,
        upper_95: null
      });
    });
    
    // Connect last historical point to first forecast
    if (merged.length > 0) {
      const lastIdx = merged.length - 1;
      merged[lastIdx].predicted = merged[lastIdx].actual;
    }
    
    // Process forecast data with confidence intervals
    if (Array.isArray(fData.forecast)) {
      fData.forecast.forEach(f => {
        const fDate = safeDate(f.date);
        if (merged.length === 0 || fDate > merged[merged.length - 1].date) {
          merged.push({
            date: fDate,
            actual: null,
            predicted: safeNum(f.predicted_sales),  // ✅ FIXED: was predictedsales
            lower_80: safeNum(f.lower_bound_80),
            upper_80: safeNum(f.upper_bound_80),
            lower_95: safeNum(f.lower_bound_95),
            upper_95: safeNum(f.upper_bound_95)
          });
        }
      });
    }
    
    // Calculate accuracy from MAPE
    const mape = fData.metrics?.mape || 0;
    const accuracy = mape ? Math.max(0, (100 * (1 - mape))).toFixed(1) : 'N/A';
    
    setForecast({
      chartData: merged,
      trend: safeString(fData.trend),
      mape: mape,
      accuracy: accuracy,
      // ✅ NEW: Include all expert mode metrics
      metrics: {
        mape: safeNum(fData.metrics?.mape || 0),
        mae: safeNum(fData.metrics?.mae || 0),
        rmse: safeNum(fData.metrics?.rmse || 0),
        r_squared: safeNum(fData.metrics?.r_squared || 0),
        aic: safeNum(fData.metrics?.aic || 0),
        bic: safeNum(fData.metrics?.bic || 0)
      },
      // ✅ NEW: Model metadata for expert mode
      model_metadata: fData.model_metadata || null
    });
  }, []);

  // --- DATA FETCHING (PRESERVED) ---
  useEffect(() => {
    let isMounted = true;
    
    const fetchQuickStats = async () => {
      try {
        const s = await window.api.getDashboardStats();
        if (isMounted && s) {
          setStats(s);
        }
      } catch (e) {
        console.warn("Stats IPC failed:", e);
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    
    const fetchAnalytics = async () => {
      try {
        const aData = await window.api.getAnalytics();
        if (!isMounted) return;

        if (aData && !aData.error && aData.status !== 'Inactive') {
          const status = aData.status || 'ready';
          const innerData = aData.data || aData;

          setAnalyticsStatus(prev => prev !== status ? status : prev);
          setAnalytics(prev => {
            // Only update if status changed or key count changed
            // This prevents re-render on every poll when data is identical
            const prevKeys = Object.keys(prev || {}).sort().join(',');
            const nextKeys = Object.keys(innerData || {}).sort().join(',');
            if (prevKeys === nextKeys) return prev;
            return innerData;
          });

          if (innerData.forecast) {
            const forecastHash = innerData.forecast.trend + '_' + 
              (innerData.forecast.history?.length || 0) + '_' + 
              (innerData.forecast.forecast?.length || 0);
            if (forecastHash !== lastForecastHashRef.current) {
              lastForecastHashRef.current = forecastHash;
              processForecast(innerData.forecast);
            }
          }

          if (status !== 'processing') {
            // Data is ready or errored — stop polling
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current);
              pollingIntervalRef.current = null;
            }
            setIsRefreshing(false);
          } else {
            // Still processing — start polling if not already running
            if (!pollingIntervalRef.current) {
              pollingIntervalRef.current = setInterval(fetchAnalytics, 4000);
            }
          }
        } else if (!aData || aData.error || aData.status === 'Inactive') {
          // Python booting or unreachable — treat same as catch
          if (isMounted) {
            setAnalyticsStatus('processing');
            if (!pollingIntervalRef.current) {
              pollingIntervalRef.current = setInterval(() => fetchAnalyticsRef.current?.(), 4000);
            }
          }
        }
      } catch (e) {
        console.warn("Analytics fetch failed:", e);
        if (isMounted) {
          setAnalyticsStatus('processing');
          // Python not running yet — keep retrying every 4s until it responds
          if (!pollingIntervalRef.current) {
            pollingIntervalRef.current = setInterval(fetchAnalytics, 4000);
          }
        }
      }
    };
    
    fetchAnalyticsRef.current = fetchAnalytics;


    const onAnalyticsReady = () => {
      fetchAnalytics();
    };
    
    fetchQuickStats();
    fetchAnalytics();
    
    if (window.api?.on) window.api.on("analytics:ready", onAnalyticsReady);
    
    return () => {
      isMounted = false;
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
      if (window.api?.off) window.api.off("analytics:ready", onAnalyticsReady);
    };
  }, [processForecast]);

  const handleForceRefresh = async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    setAnalyticsStatus('processing');
    // DO NOT setAnalytics(null) — keep existing data visible while refreshing
    try {
      await window.api.forceRefreshAnalytics();
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      // Start polling using fetchAnalytics — same function, same scope, processForecast works
      pollingIntervalRef.current = setInterval(() => fetchAnalyticsRef.current?.(), 4000);
    } catch (e) {
      console.warn("Force refresh failed:", e);
      setIsRefreshing(false);
      setAnalyticsStatus('error');
    }
  };
  
  // --- MEMOIZED DATA PARSING ---
  const marketBasketRules = useMemo(() => {
  if (!analytics?.market_basket?.rules) return [];
  
  // Backend now sends structured JSON with rules array
  return analytics.market_basket.rules.map(rule => ({
    ...rule,
    // Ensure all fields exist for safe rendering
    description: rule.description || '',
    antecedent: Array.isArray(rule.antecedent) ? rule.antecedent : [],
    consequent: Array.isArray(rule.consequent) ? rule.consequent : [],
    confidence: safeNum(rule.confidence),
    support: safeNum(rule.support),
    lift: safeNum(rule.lift),
    conviction: safeNum(rule.conviction),
    leverage: safeNum(rule.leverage),
    zhangs_metric: rule.zhangs_metric !== null ? safeNum(rule.zhangs_metric) : null
  }));
}, [analytics]);

const marketBasketMetadata = useMemo(() => {
  if (!analytics?.market_basket?.model_metadata) return null;  // ✅ FIXED
  return analytics.market_basket.model_metadata;
}, [analytics]);

const churnRiskList = useMemo(() => {
  return analytics?.churn_risk || [];  // ✅ FIXED
}, [analytics]);

const inventoryForecastList = useMemo(() => {
  const list = analytics?.stockouts || [];
  // Sort by days_left ASCENDING (Smallest days first = Critical on top)
  return [...list].sort((a, b) => {
    const daysA = safeNum(a.days_left);
    const daysB = safeNum(b.days_left);
    
    // Handle cases where days might be 0 or missing (put them at bottom or top as needed)
    if (daysA === 0 && daysB !== 0) return 1; 
    if (daysB === 0 && daysA !== 0) return -1;
    
    return daysA - daysB;
  });
}, [analytics]);

  
  // --- DERIVED DATA ---
  const aiSummaryText = useMemo(() => {
    if (!forecast || !stats) return "Analyzing patterns...";
    const trend = forecast.trend?.toLowerCase() || "steady";
    const criticalItems = stats.low_stock_items?.length || 0;
    const creditStatus = stats.total_outstanding_credit > 5000000 ? "elevated" : "stable";
    
    return `Revenue ${trend}. ${criticalItems} critical items. Credit ${creditStatus}.`;
  }, [forecast, stats]);
  
  const isProcessing = analytics?.status === 'processing';
  
  const revenueSparklineData = useMemo(() => {
    if (!forecast?.chartData) return [];
    return forecast.chartData
      .filter(d => d.actual !== null)
      .slice(-30)
      .map(d => d.actual);
  }, [forecast]);
  
  // ============================================================================
  // RENDER: COMPACT TOP RAIL
  // ============================================================================
  const TopRail = ({ onForceRefresh, isRefreshing, isExpertMode, setIsExpertMode, aiSummaryText, isProcessing }) => (
    <div className="flex items-center justify-between h-14 px-6 border-b border-border bg-card/50 backdrop-blur-sm">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <LayoutDashboard className="w-4 h-4 text-primary" />
          </div>
          <h1 className="text-base font-semibold tracking-tight">Executive Dashboard</h1>
        </div>
        
        <AISummaryChip text={aiSummaryText} isProcessing={isProcessing} />
        <FreshnessBadge initialSeconds={0} />
      </div>
      
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={onForceRefresh}
          disabled={isRefreshing}
          className="h-7 px-2 text-xs gap-1.5 text-muted-foreground hover:text-foreground"
          title="Refresh AI Models"
        >
          <motion.div
            animate={isRefreshing ? { rotate: 360 } : { rotate: 0 }}
            transition={isRefreshing ? { duration: 1, repeat: Infinity, ease: "linear" } : {}}
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </motion.div>
          <span className="hidden sm:inline">{isRefreshing ? 'Refreshing...' : 'Refresh AI'}</span>
        </Button>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <Download className="w-4 h-4" />
        </Button>
        
        <div className="flex items-center gap-2 ml-2 pl-3 border-l">
          <Zap className="w-3.5 h-3.5 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">Exec View</span>
          <Switch checked={isExpertMode} onCheckedChange={setIsExpertMode} />
        </div>
      </div>
    </div>
  );
  
  // ============================================================================
  // RENDER: KPI BENTO GRID
  // ============================================================================
  const KPIGrid = () => {
  // ✅ FIX: Add safe defaults for all values
  const kpis = [
    {
      id: 'credit',
      label: 'Outstanding Credit',
      value: stats?.totaloutstandingcredit || 0,  // ✅ Safe access
      icon: DollarSign,
      status: (stats?.totaloutstandingcredit || 0) > 5000000 ? 'critical' : 'warning',
      change: -2.4,
      sparklineData: revenueSparklineData,
      color: '#ef4444'
    },
    {
      id: 'inventory',
      label: 'Active Inventory',
      value: stats?.totalproductvariants || 0,  // ✅ Safe access
      icon: Package,
      status: 'healthy',
      change: 5.2,
      sparklineData: [4800, 4850, 4900, 4920, 4950, 5000, 5010],
      color: '#10b981',
      isCount: true
    },
    {
      id: 'customers',
      label: 'Total Customers',
      value: stats?.totalcustomers || 0,  // ✅ Safe access
      icon: Users,
      status: 'healthy',
      change: 3.1,
      sparklineData: [4900, 4920, 4950, 4970, 4980, 4990, 5000],
      color: '#3b82f6',
      isCount: true
    },
    {
      id: 'confidence',
      label: 'AI Confidence',
      value: safeNum(forecast?.accuracy || 0),  // ✅ Already safe
      icon: Sparkles,
      status: (forecast?.accuracy || 0) > 75 ? 'healthy' : 'warning',
      change: 1.2,
      sparklineData: [75, 76, 78, 79, 80, 80.5, 81],
      color: '#8b5cf6',
      isPercentage: true
    }
  ];
    
    return (
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 px-6 py-4"
      >
        {kpis.map((kpi) => {
          const Icon = kpi.icon;
          const isPositive = kpi.change > 0;
          
          return (
            <motion.div
              key={kpi.id}
              variants={cardVariants}
              initial="rest"
              whileHover="hover"
              custom={hoverVariants}
            >
              <Card className={`relative overflow-hidden border-l-4 transition-all duration-200 hover:border-primary/50 ${
                kpi.status === 'critical' ? 'border-l-red-500 bg-red-50/50 dark:bg-red-950/10' :
                kpi.status === 'warning' ? 'border-l-yellow-500 bg-yellow-50/50 dark:bg-yellow-950/10' :
                'border-l-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/10'
              }`}>
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <StatusDot status={kpi.status} />
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          {kpi.label}
                        </p>
                      </div>
                      <p className="text-2xl font-bold tracking-tight">
                        {kpi.isCount ? kpi.value.toLocaleString() :
                         kpi.isPercentage ? `${safeNum(kpi.value).toFixed(1)}%` :
                         formatCompactNumber(kpi.value)}
                      </p>
                    </div>
                    <div className="p-2 bg-background/80 rounded-lg">
                      <Icon className="w-4 h-4 text-muted-foreground" />
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <Sparkline data={kpi.sparklineData} color={kpi.color} showArea />
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex items-center gap-0.5 text-xs font-semibold px-1.5 py-0.5 rounded-full ${
                        isPositive 
                          ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400' 
                          : 'bg-red-500/15 text-red-600 dark:text-red-400'
                      }`}>
                        {isPositive 
                          ? <ArrowUpRight className="w-3 h-3" /> 
                          : <ArrowDownRight className="w-3 h-3" />}
                        {Math.abs(kpi.change)}%
                      </span>
                      <span className="text-xs text-muted-foreground">vs last week</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </motion.div>
    );
  };
  
  // ============================================================================
  // RENDER: REVENUE FORECAST CARD
  // ============================================================================
  const RevenueForecastCard = () => (
    <Card className="h-full border-border">
      <CardHeader className="pb-3">
  <div className="flex items-center justify-between">
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-primary" />
        <CardTitle className="text-sm font-semibold">Revenue Forecast</CardTitle>
      </div>
      {forecast && (
        <div className="text-xs text-muted-foreground">
          {isExpertMode ? (
            // ✅ EXPERT MODE: Show ALL metrics
            <div className="space-y-1">
              <div className="flex items-center gap-3">
                <span>MAPE: <strong>{(forecast.metrics.mape * 100).toFixed(2)}%</strong></span>
                <span>MAE: <strong>₹{forecast.metrics.mae.toLocaleString()}</strong></span>
                <span>RMSE: <strong>₹{forecast.metrics.rmse.toLocaleString()}</strong></span>
              </div>
              <div className="flex items-center gap-3 text-muted-foreground/80">
                <span>R²: {forecast.metrics.r_squared.toFixed(3)}</span>
                <span>AIC: {forecast.metrics.aic.toFixed(1)}</span>
                <span>BIC: {forecast.metrics.bic.toFixed(1)}</span>
                {forecast.model_metadata && (
                  <span className="ml-2">
                    <Badge variant="outline" className="text-10px">
                      {forecast.model_metadata.algorithm}
                    </Badge>
                  </span>
                )}
              </div>
              {forecast.model_metadata && (
                <div className="text-10px text-muted-foreground/70">
                  Seasonality: {(forecast.model_metadata.seasonality_strength * 100).toFixed(1)}% •{' '}
                  Trend: {(forecast.model_metadata.trend_strength * 100).toFixed(1)}% •{' '}
                  Training: {forecast.model_metadata.training_period_days} days
                </div>
              )}
            </div>
          ) : (
            // ✅ NORMAL MODE: Simple display
            <span>
              Trend: <span className="font-medium capitalize flex items-center gap-1 inline-flex">
                {forecast.trend === 'up' ? <TrendingUp className="w-3 h-3 text-emerald-500" /> : 
                 forecast.trend === 'down' ? <TrendingDown className="w-3 h-3 text-red-500" /> : 
                 <Minus className="w-3 h-3 text-gray-500" />}
                {forecast.trend === 'up' ? 'Growing' : forecast.trend === 'down' ? 'Declining' : 'Stable'}
              </span>
            </span>
          )}
        </div>
      )}
    </div>
  </div>
</CardHeader>

      
      <CardContent className="px-4 pb-4">
        {loading ? (
          <div className="h-64 flex items-center justify-center">
            <div className="text-center space-y-2">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              >
                <Activity className="w-8 h-8 text-primary mx-auto" />
              </motion.div>
              <p className="text-sm text-muted-foreground">Loading forecast data...</p>
            </div>
          </div>
        ) : !forecast?.chartData?.length ? (
          <div className="h-64 flex items-center justify-center">
            <div className="text-center space-y-3 px-4">
              {analyticsStatus === 'processing' ? (
                <>
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                    className="mx-auto w-fit"
                  >
                    <TrendingUp className="w-8 h-8 text-blue-500" />
                  </motion.div>
                  <p className="text-sm font-medium text-blue-500">Building Revenue Forecast</p>
                  <p className="text-xs text-muted-foreground">Prophet model analyzing 90-day patterns...</p>
                </>
              ) : analyticsStatus === 'error' ? (
                <>
                  <AlertCircle className="w-8 h-8 text-amber-500 mx-auto" />
                  <p className="text-sm font-medium text-amber-500">Forecast Unavailable</p>
                  <p className="text-xs text-muted-foreground">Try refreshing the AI models</p>
                </>
              ) : (
                <>
                  <AlertCircle className="w-8 h-8 text-muted-foreground mx-auto" />
                  <p className="text-sm text-muted-foreground">No forecast data yet</p>
                  <p className="text-xs text-muted-foreground">Needs at least 30 days of sales history</p>
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={forecast.chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorPredicted" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f97316" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="date"
                  tickFormatter={(d) => new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}
                  tick={{ fontSize: 11 }}
                  stroke="hsl(var(--muted-foreground))"
                  strokeWidth={0.5}
                />
                <YAxis
                  tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}K`}
                  tick={{ fontSize: 11 }}
                  stroke="hsl(var(--muted-foreground))"
                  strokeWidth={0.5}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    fontSize: '12px'
                  }}
                  labelFormatter={(d) => new Date(d).toLocaleDateString('en-IN', { 
                    day: 'numeric', 
                    month: 'short', 
                    year: 'numeric' 
                  })}
                  formatter={(value) => [formatCurrency(value), '']}
                />
                <Area
                  type="monotone"
                  dataKey="actual"
                  stroke="#3b82f6"
                  strokeWidth={2.5}
                  fill="url(#colorActual)"
                  name="Historical"
                  connectNulls={false}
                />
                <Area
                  type="monotone"
                  dataKey="predicted"
                  stroke="#f97316"
                  strokeWidth={2.5}
                  strokeDasharray="5 5"
                  fill="url(#colorPredicted)"
                  name="AI Forecast"
                  connectNulls={false}
                />
              </AreaChart>
            </ResponsiveContainer>
            
            <div className="flex items-center justify-between pt-2 border-t">
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-blue-500 rounded-sm" />
                  <span className="text-muted-foreground">Historical Sales</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-orange-500 rounded-sm border-2 border-dashed border-orange-500" />
                  <span className="text-muted-foreground">AI Prediction</span>
                </div>
              </div>
              
              <div className="w-48">
                <ConfidenceMeter level={forecast.accuracy} size="small" />
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
  
  // ============================================================================
  // RENDER: DEBT/STOCK PANEL CARD
  // ============================================================================
  const DebtStockPanel = () => (
    <Card className="h-full border-border">
      <CardHeader className="pb-3">
        <Tabs value={activePanelTab} onValueChange={setActivePanelTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2 h-9">
            <TabsTrigger value="debt" className="text-xs gap-1.5">
              <DollarSign className="w-3.5 h-3.5" />
              Debts
            </TabsTrigger>
            <TabsTrigger value="stock" className="text-xs gap-1.5">
              <Package className="w-3.5 h-3.5" />
              Stock
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </CardHeader>
      
      <CardContent className="px-0 pb-4">
        <AnimatePresence mode="wait">
          {activePanelTab === 'debt' ? (
            <motion.div
              key="debt"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              transition={{ duration: 0.2 }}
              className="space-y-1"
            >
              {stats.top_customers_by_credit && stats.top_customers_by_credit.length > 0 ? (
                <Virtuoso
                  style={{ height: '320px' }}
                  data={stats.top_customers_by_credit}
                  itemContent={(index, customer) => {
                    const balance = safeNum(customer.outstanding_balance);
                    const maxBalance = Math.max(...stats.top_customers_by_credit.map(c => safeNum(c.outstanding_balance)));
                    const percentage = (balance / maxBalance) * 100;
                    
                    return (
                      <div className="px-4 py-2.5 hover:bg-accent/50 transition-colors cursor-pointer">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-sm font-medium truncate flex-1">{customer.name}</span>
                          <span className="text-sm font-bold tabular-nums">{formatCurrency(balance)}</span>
                        </div>
                        <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                          <motion.div
                            className={`h-full rounded-full ${
                              balance > 10000 ? 'bg-red-500' : 
                              balance > 5000 ? 'bg-orange-500' : 
                              'bg-yellow-500'
                            }`}
                            initial={{ width: 0 }}
                            animate={{ width: `${percentage}%` }}
                            transition={{ duration: 0.5, delay: index * 0.05 }}
                          />
                        </div>
                      </div>
                    );
                  }}
                />
              ) : (
                <div className="h-80 flex items-center justify-center">
                  <p className="text-sm text-muted-foreground">No outstanding debts</p>
                </div>
              )}
            </motion.div>
          ) : (
            <motion.div
              key="stock"
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2 }}
              className="space-y-1"
            >
              {stats.low_stock_items && stats.low_stock_items.length > 0 ? (
                <Virtuoso
                  style={{ height: '320px' }}
                  data={stats.low_stock_items}
                  itemContent={(index, item) => {
                    const stockLevel = safeNum(item.total_stock);
                    const isCritical = stockLevel === 0;
                    const isLow = stockLevel > 0 && stockLevel <= 5;
                    
                    return (
                      <div className="px-4 py-2.5 hover:bg-accent/50 transition-colors">
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2 flex-1">
                            {isCritical ? (
                              <AlertTriangle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />
                            ) : isLow ? (
                              <AlertCircle className="w-3.5 h-3.5 text-orange-500 flex-shrink-0" />
                            ) : (
                              <Package className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                            )}
                            <span className="text-sm font-medium truncate">{item.product_name}</span>
                          </div>
                          <Badge variant={isCritical ? "destructive" : "secondary"} className="text-xs font-bold">
                            {Math.round(stockLevel)}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground pl-5">
                          Category: {item.category || 'N/A'}
                        </p>
                      </div>
                    );
                  }}
                />
              ) : (
                <div className="h-80 flex items-center justify-center">
                  <p className="text-sm text-muted-foreground">All items well-stocked</p>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
  
  // ============================================================================
  // RENDER: AI ANALYTICS CONTENT (FULL WIDTH 3 CARDS)
  // ============================================================================
  const AIAnalyticsContent = () => (
    <div className={isExpertMode ? "space-y-4" : "space-y-4"}>
      {/* Market Basket Analysis */}
      <Card className="border-border overflow-hidden">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShoppingCart className="w-4 h-4 text-primary" />
              <CardTitle className="text-sm font-semibold">Market Basket</CardTitle>
            </div>
            {isExpertMode && marketBasketMetadata && (
              <div className="flex gap-1.5 items-center">
                <Badge variant="outline" className="text-10px">
                  {marketBasketMetadata.algorithm}
                </Badge>
                <Badge variant="secondary" className="text-10px">
                  {marketBasketMetadata.total_transactions?.toLocaleString()} txns
                </Badge>
              </div>
            )}
          </div>
          <div className="flex items-end justify-between">
            <p className="text-xs text-muted-foreground">
              {isExpertMode ? "Association Rules (Confidence)" : "Buying Patterns"}
            </p>
            {!isExpertMode && marketBasketRules.length > 0 && (
              <p className="text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">{marketBasketRules.length}</span> rules · 
                <span className="font-semibold text-teal-500 ml-1">
                  {(marketBasketRules.reduce((sum, r) => sum + r.confidence, 0) / marketBasketRules.length * 100).toFixed(0)}%
                </span> avg confidence
              </p>
            )}
          </div>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          {marketBasketRules.length > 0 ? (
            <div className="flex gap-4">
              {/* Left — rules list */}
              <div className="flex-1 space-y-2 max-h-80 overflow-y-auto min-w-0">
                {marketBasketRules.map((rule, idx) => (
                  <div key={idx} className="p-2.5 bg-muted/50 rounded border border-border hover:bg-muted transition-colors">
                    {rule.antecedent && rule.antecedent.length > 0 ? (
                      <div className="space-y-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {isExpertMode ? (
                            <div className="w-full">
                              <div className="flex flex-wrap gap-2 items-center mb-2">
                              {rule.antecedent.map((item, i) => (
                                <Badge key={i} variant="secondary" className="text-xs px-2 py-1 font-medium">
                                  {item}
                                </Badge>
                              ))}
                              <span className="text-muted-foreground text-xs">→</span>
                              {rule.consequent.map((item, i) => (
                                <Badge key={i} variant="secondary" className="text-xs px-2 py-1 font-medium">
                                  {item}
                                </Badge>
                              ))}
                              </div>
                              <div className="grid grid-cols-3 gap-4 text-xs pt-1 border-t border-border/50">
                                <div>Conf: <span className="font-medium">{(rule.confidence * 100).toFixed(1)}%</span></div>
                                <div>Lift: <span className="font-medium">{rule.lift.toFixed(2)}x</span></div>
                                <div>Supp: <span className="font-medium">{(rule.support * 100).toFixed(2)}%</span></div>
                              </div>
                            </div>
                          ) : (
                            <div className="space-y-2">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                {rule.antecedent.map((item, i) => (
                                  <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                                    {item}
                                  </span>
                                ))}
                                <span className="text-muted-foreground mx-1">→</span>
                                {rule.consequent.map((item, i) => (
                                  <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20">
                                    {item}
                                  </span>
                                ))}
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="text-[10px] text-muted-foreground">Confidence</span>
                                <div className="flex-1 h-1 rounded-full bg-muted overflow-hidden">
                                  <div 
                                    className="h-full rounded-full bg-teal-500"
                                    style={{ width: `${(rule.confidence * 100)}%` }}
                                  />
                                </div>
                                <span className="text-[10px] font-semibold text-teal-600 dark:text-teal-400">
                                  {(rule.confidence * 100).toFixed(0)}%
                                </span>
                              </div>
                            </div>
                          )}
                        </div>
                        {isExpertMode && (
                          <div className="mt-1 text-xs text-muted-foreground grid grid-cols-3 gap-4">
                              <span>Conv: {rule.conviction.toFixed(2)}</span>
                              <span>Lev: {rule.leverage.toFixed(4)}</span>
                              {rule.zhangs_metric !== null && (
                                <span>Zhang: {rule.zhangs_metric.toFixed(3)}</span>
                              )}
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground">{rule.description || 'No pattern data'}</p>
                    )}
                  </div>
                ))}
              </div>
              {/* Right — summary panel */}
              {!isExpertMode && (
                <div className="w-56 flex-shrink-0 space-y-3 border-l border-border/50 pl-4">
                  {/* Stats strip */}
                  <div className="p-3 rounded-lg bg-muted/40 border border-border/50 space-y-2.5">
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                      Pattern Summary
                    </p>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">Total Rules</span>
                        <span className="text-xs font-bold text-foreground">{marketBasketRules.length}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">Avg Confidence</span>
                        <span className="text-xs font-bold text-teal-500">
                          {(marketBasketRules.reduce((sum, r) => sum + r.confidence, 0) / marketBasketRules.length * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">High Confidence</span>
                        <span className="text-xs font-bold text-foreground">
                          {marketBasketRules.filter(r => r.confidence >= 0.8).length}
                        </span>
                      </div>
                    </div>
                  </div>
                  {/* Top 3 strongest rules */}
                  <div className="space-y-1.5">
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                      Strongest Rules
                    </p>
                    {[...marketBasketRules]
                      .sort((a, b) => b.confidence - a.confidence)
                      .slice(0, 3)
                      .map((rule, i) => (
                        <div key={i} className="p-2 rounded-md bg-muted/30 border border-border/40 space-y-1">
                          <div className="text-[10px] text-foreground font-medium line-clamp-1">
                            {rule.antecedent[0]} → {rule.consequent[0]}
                          </div>
                          <div className="flex items-center gap-1.5">
                            <div className="flex-1 h-1 rounded-full bg-muted overflow-hidden">
                              <div
                                className="h-full rounded-full bg-teal-500"
                                style={{ width: `${rule.confidence * 100}%` }}
                              />
                            </div>
                            <span className="text-[10px] font-semibold text-teal-500">
                              {(rule.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                      ))
                    }
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="h-80 flex items-center justify-center">
              <div className="text-center space-y-3 px-4">
                {analyticsStatus === 'processing' ? (
                  <>
                    <motion.div
                      animate={{ rotate: [0, 10, -10, 0] }}
                      transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                      className="mx-auto w-fit"
                    >
                      <ShoppingCart className="w-8 h-8 text-teal-500" />
                    </motion.div>
                    <p className="text-sm font-medium text-teal-500">Mining Shopping Patterns</p>
                    <p className="text-xs text-muted-foreground">FP-Growth analyzing transaction history...</p>
                    <p className="text-xs text-muted-foreground opacity-70">This may take a few minutes</p>
                  </>
                ) : analyticsStatus === 'error' ? (
                  <>
                    <AlertCircle className="w-8 h-8 text-amber-500 mx-auto" />
                    <p className="text-sm font-medium text-amber-500">Analysis Unavailable</p>
                    <p className="text-xs text-muted-foreground">Try refreshing the AI models</p>
                  </>
                ) : (
                  <>
                    <ShoppingCart className="w-8 h-8 text-muted-foreground/30 mx-auto" />
                    <p className="text-sm text-muted-foreground">No patterns found yet</p>
                    <p className="text-xs text-muted-foreground">Needs more transaction variety to detect patterns</p>
                  </>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-stretch">
      {/* Churn Risk */}
      <Card className="border-border flex flex-col h-[400px] overflow-hidden">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-orange-500" />
              <CardTitle className="text-sm font-semibold">Churn Risk</CardTitle>
            </div>
            {isExpertMode && analytics?.churn_risk_model_info && (
              <div className="flex flex-wrap gap-1.5 items-center justify-end">
                <Badge variant="outline" className="text-10px">
                  {analytics.churn_risk_model_info.algorithm}
                </Badge>
                {analytics.churn_risk_model_info.metrics?.auc_roc && (
                  <Badge variant="secondary" className="text-10px">
                    AUC: {analytics.churn_risk_model_info.metrics.auc_roc.toFixed(3)}
                  </Badge>
                )}
                {analytics.churn_risk_model_info.metrics?.accuracy && (
                  <Badge variant="secondary" className="text-10px">
                    Acc: {(analytics.churn_risk_model_info.metrics.accuracy * 100).toFixed(1)}%
                  </Badge>
                )}
                {analytics.churn_risk_model_info.metrics?.f1_score && (
                  <Badge variant="secondary" className="text-10px">
                    F1: {analytics.churn_risk_model_info.metrics.f1_score.toFixed(3)}
                  </Badge>
                )}
                {analytics.churn_risk_model_info.metrics?.precision && (
                  <Badge variant="secondary" className="text-10px">
                    Prec: {(analytics.churn_risk_model_info.metrics.precision * 100).toFixed(1)}%
                  </Badge>
                )}
                {analytics.churn_risk_model_info.metrics?.recall && (
                  <Badge variant="secondary" className="text-10px">
                    Rec: {(analytics.churn_risk_model_info.metrics.recall * 100).toFixed(1)}%
                  </Badge>
                )}
              </div>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {isExpertMode ? "ML Risk Scores (XGBoost)" : "Customer Activity"}
          </p>
        </CardHeader>
        <CardContent className="px-4 pb-4 flex flex-col overflow-hidden min-h-0 h-full">
          {churnRiskList.length > 0 ? (
            <>
              {/* Risk summary strip */}
              {(() => {
                const highCount = churnRiskList.filter(c => c.risk_score > 80).length;
                const medCount = churnRiskList.filter(c => c.risk_score > 50 && c.risk_score <= 80).length;
                const lowCount = churnRiskList.filter(c => c.risk_score <= 50).length;
                const COLORS = ['#ef4444', '#f97316', '#22c55e'];
                const pieData = [
                  { name: 'High', value: highCount || 0.001 },
                  { name: 'Med', value: medCount || 0.001 },
                  { name: 'Low', value: lowCount || 0.001 },
                ];
                return (
                  <div className="flex items-center gap-3 mb-3 p-2.5 bg-muted/40 rounded-lg border border-border/50">
                    <PieChart width={52} height={52}>
                      <Pie
                        data={pieData}
                        cx={22}
                        cy={22}
                        innerRadius={14}
                        outerRadius={24}
                        dataKey="value"
                        strokeWidth={0}
                      >
                        {pieData.map((_, i) => (
                          <Cell key={i} fill={COLORS[i]} />
                        ))}
                      </Pie>
                    </PieChart>
                    <div className="flex flex-col gap-1 text-xs">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
                        <span className="text-muted-foreground">High Risk</span>
                        <span className="font-semibold text-foreground ml-auto pl-3">{highCount}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-orange-500 inline-block" />
                        <span className="text-muted-foreground">Medium</span>
                        <span className="font-semibold text-foreground ml-auto pl-3">{medCount}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
                        <span className="text-muted-foreground">Low Risk</span>
                        <span className="font-semibold text-foreground ml-auto pl-3">{lowCount}</span>
                      </div>
                    </div>
                    <div className="ml-auto text-right">
                      <p className="text-lg font-bold text-foreground">{churnRiskList.length}</p>
                      <p className="text-[10px] text-muted-foreground">at risk</p>
                    </div>
                  </div>
                );
              })()}
              <div className="space-y-2 overflow-y-auto flex-1 min-h-0 pb-1">
              {churnRiskList.slice(0, 10).map((customer, idx) => (
                <div key={idx} className="p-2.5 bg-muted/50 rounded border border-border hover:bg-muted transition-colors">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium truncate flex-1">{customer.name}</span>
                    <Badge 
                      variant={customer.risk_score > 80 ? "destructive" : "secondary"} 
                      className="text-xs"
                    >
                      {isExpertMode ? `${customer.risk_score}%` : customer.days_inactive > 60 ? "At Risk" : "Warning"}
                    </Badge>
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    {isExpertMode ? (
                      <span>
                        Velocity: {customer.velocity} · Inactive: {customer.days_inactive}d · {customer.trend}
                      </span>
                    ) : (
                      <span className="font-normal opacity-80">
                        Last purchase: {customer.days_inactive} days ago
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
            </>
          ) : (
            <div className="h-80 flex items-center justify-center">
              <div className="text-center space-y-3 px-4">
                {analyticsStatus === 'processing' ? (
                  <>
                    <motion.div
                      animate={{ scale: [1, 1.1, 1] }}
                      transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                      className="mx-auto w-fit"
                    >
                      <Users className="w-8 h-8 text-violet-500" />
                    </motion.div>
                    <p className="text-sm font-medium text-violet-500">Running Churn Analysis</p>
                    <p className="text-xs text-muted-foreground">XGBoost model scoring all customers...</p>
                  </>
                ) : analyticsStatus === 'error' ? (
                  <>
                    <AlertCircle className="w-8 h-8 text-amber-500 mx-auto" />
                    <p className="text-sm font-medium text-amber-500">Analysis Unavailable</p>
                    <p className="text-xs text-muted-foreground">Try refreshing the AI models</p>
                  </>
                ) : (
                  <>
                    <div className="w-10 h-10 rounded-full bg-green-500/10 flex items-center justify-center mx-auto">
                      <CheckCircle className="w-6 h-6 text-green-500" />
                    </div>
                    <p className="text-sm font-medium text-green-600 dark:text-green-400">All Customers Retained</p>
                    <p className="text-xs text-muted-foreground">No churn risk detected right now</p>
                  </>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Stockout Alerts */}
      <Card className="border-border shadow-sm flex flex-col h-[400px]">
        <CardHeader className="pb-2 border-b bg-muted/20">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Package className="w-4 h-4 text-red-500" />
              <CardTitle className="text-sm font-semibold">Stockout Alerts</CardTitle>
            </div>
            {isExpertMode && <Badge variant="outline" className="text-[10px] font-mono">Monte Carlo</Badge>}
          </div>
          <p className="text-xs text-muted-foreground">
             {isExpertMode ? "AI Burn Rate & EOQ" : "Restock Needed"}
          </p>
        </CardHeader>
        <CardContent className="p-0 flex-1 overflow-hidden">
          {inventoryForecastList.length > 0 ? (
            <div className="h-full overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow className="h-8 hover:bg-transparent">
                    <TableHead className="text-[10px] h-8 pl-4 w-[45%]">Product</TableHead>
                    <TableHead className="text-[10px] h-8 text-center w-[25%]">Days Left</TableHead>
                    <TableHead className="text-[10px] h-8 text-right pr-4 w-[30%]">
                      {isExpertMode ? "Metrics" : "Status"}
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {inventoryForecastList.slice(0, 8).map((item, i) => {
                    const daysLeft = safeNum(item.days_left);
                    const stock = safeNum(item.stock);
                    
                    // ✅ READ REAL METRICS FROM BACKEND
                    const metrics = item.metrics || {};
                    const displayBurnRate = metrics.burn_rate !== undefined ? metrics.burn_rate : (stock / (daysLeft || 1)).toFixed(1);
                    const displayEOQ = metrics.eoq || 0;
                    const displayVol = metrics.volatility || 0;

                    return (
                      <TableRow key={i} className="h-12 hover:bg-muted/50">
                        <TableCell className="py-1 pl-4">
                          <div className="font-medium text-xs line-clamp-1">{item.name}</div>
                          <div className="text-[10px] text-muted-foreground mb-1">Stock: {stock} units</div>
                          <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
                            <div 
                              className={`h-full rounded-full transition-all ${
                                daysLeft < 3 ? 'bg-red-500' : 
                                daysLeft < 7 ? 'bg-orange-400' : 
                                'bg-emerald-500'
                              }`}
                              style={{ width: `${Math.min(100, (daysLeft / 30) * 100)}%` }}
                            />
                          </div>
                        </TableCell>
                        <TableCell className="py-1 text-center px-1">
                          <Badge variant={daysLeft < 3 ? "destructive" : "outline"} className="h-5 text-[10px] px-1.5 whitespace-nowrap">
                            {daysLeft.toFixed(1)} days
                          </Badge>
                        </TableCell>
                        <TableCell className="py-1 pr-4 text-right">
                          {isExpertMode ? (
                            <div className="flex flex-col items-end gap-1">
                               <div className="flex items-center justify-end gap-2 text-[10px]">
                                 <span className="text-muted-foreground">EOQ: {displayEOQ}</span>
                                 <span className="font-mono text-orange-600 font-semibold min-w-[30px] text-right">
                                   {displayBurnRate}/d
                                 </span>
                               </div>
                               <div className="text-[10px] text-muted-foreground flex items-center justify-end gap-1">
                                 <span>Var:</span>
                                 <span className={displayVol > 50 ? "text-red-500" : "text-emerald-600"}>
                                   {displayVol}%
                                 </span>
                               </div>
                            </div>
                          ) : (
                            <span className="text-xs font-medium text-red-500 whitespace-nowrap">
                              {daysLeft < 3 ? "Critical" : "Warning"}
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
              {analyticsStatus === 'processing' ? (
                <>
                  <motion.div
                    animate={{ y: [0, -4, 0] }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                  >
                    <Package className="w-8 h-8 text-orange-400 mb-2" />
                  </motion.div>
                  <p className="text-xs font-medium text-orange-400">Running Stockout Simulation</p>
                  <p className="text-xs mt-1 text-center px-4">Monte Carlo model running 10,000 scenarios...</p>
                </>
              ) : analyticsStatus === 'error' ? (
                <>
                  <AlertCircle className="w-8 h-8 text-amber-500 mb-2" />
                  <p className="text-xs font-medium text-amber-500">Prediction Unavailable</p>
                  <p className="text-xs mt-1">Try refreshing the AI models</p>
                </>
              ) : (
                <>
                  <div className="w-10 h-10 rounded-full bg-green-500/10 flex items-center justify-center mb-2">
                    <Package className="w-5 h-5 text-green-500" />
                  </div>
                  <p className="text-xs font-medium text-green-600 dark:text-green-400">Inventory Levels Optimal</p>
                  <p className="text-xs mt-1">No stockout risk in the next 30 days</p>
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>
      </div>
    </div>
  );
  
  // ============================================================================
  // RENDER: MAIN CONTENT (STRIPPED TABS WRAPPER)
  // ============================================================================
  const MainContentGrid = () => (
    <>
        {/* OVERVIEW TAB: 60/40 Split */}
        <TabsContent value="overview" className="mt-0">
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 items-stretch">
            <div className="lg:col-span-3 flex flex-col">
              <RevenueForecastCard />
            </div>
            <div className="lg:col-span-2 flex flex-col">
              <DebtStockPanel />
            </div>
          </div>
        </TabsContent>
        
        {/* AI TAB: Full Width */}
        <TabsContent value="ai" className="mt-0">
          <AIAnalyticsContent />
        </TabsContent>
    </>
  );
  
  // ============================================================================
  // MAIN RENDER
  // ============================================================================
  return (
    <div className="h-full flex flex-col bg-background overflow-hidden">
      <Tabs
        value={activeMainTab}
        onValueChange={setActiveMainTab}
        className="flex flex-col flex-1 min-h-0"
      >
        {/* STICKY ZONE — never scrolls */}
        <div className="flex-none">
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="space-y-4 pt-4"
          >
            <TopRail
              onForceRefresh={handleForceRefresh}
              isRefreshing={isRefreshing}
              isExpertMode={isExpertMode}
              setIsExpertMode={setIsExpertMode}
              aiSummaryText={aiSummaryText}
              isProcessing={isProcessing}
            />
            <KPIGrid />
            <div className="px-6">
              <TabsList className="grid w-full max-w-md grid-cols-2 h-9">
                <TabsTrigger value="overview" className="text-xs">Overview</TabsTrigger>
                <TabsTrigger value="ai" className="text-xs gap-1.5">
                  <Brain className="w-3.5 h-3.5" />
                  AI Intelligence
                </TabsTrigger>
              </TabsList>
            </div>
          </motion.div>
        </div>
        {/* SCROLLABLE ZONE — only content scrolls */}
        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="px-6 pb-6 pt-4">
            <MainContentGrid />
          </div>
        </div>
      </Tabs>
    </div>
  );
}