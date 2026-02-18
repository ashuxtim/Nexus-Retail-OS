import React, { useState, useEffect, useMemo, useRef } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';
import { Virtuoso } from 'react-virtuoso';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  TrendingUp, Users, Package, DollarSign, AlertTriangle, Activity, 
  Sparkles, ArrowUpRight, ArrowDownRight, LayoutDashboard, 
  AlertCircle, Zap, Clock, Download, Settings, ShoppingCart,
  TrendingDown, Minus, Brain
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
  const [loading, setLoading] = useState(true);
  const [backendError, setBackendError] = useState(false);
  const [isExpertMode, setIsExpertMode] = useState(false);
  const pollingIntervalRef = useRef(null);
  
  // --- UI STATE ---
  const [activePanelTab, setActivePanelTab] = useState('debt');
  const [activeMainTab, setActiveMainTab] = useState('overview');
  
  // --- DATA FETCHING (PRESERVED) ---
  useEffect(() => {
    let isMounted = true;
    
    const processForecast = (fData) => {
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
};

    
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
        
        if (aData && !aData.error) {
          const finalData = aData.data || aData;
          setAnalytics(finalData);
          
          if (finalData.forecast) processForecast(finalData.forecast);
          
          if (finalData.status !== 'processing' && pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }
        }
      } catch (e) {
        console.warn("Analytics fetch failed:", e);
      }
    };
    
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
  }, []);
  
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
  const TopRail = () => (
    <div className="flex items-center justify-between h-14 px-6 border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-10">
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
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <Download className="w-4 h-4" />
        </Button>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
          <Settings className="w-4 h-4" />
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
                    <div className="flex items-center gap-2 text-xs">
                      {isPositive ? (
                        <ArrowUpRight className="w-3 h-3 text-emerald-500" />
                      ) : (
                        <ArrowDownRight className="w-3 h-3 text-red-500" />
                      )}
                      <span className={isPositive ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}>
                        {Math.abs(kpi.change)}%
                      </span>
                      <span className="text-muted-foreground">vs last week</span>
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
    <Card className="border-border">
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
        ) : forecast && forecast.chartData && forecast.chartData.length > 0 ? (
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
        ) : (
          <div className="h-64 flex items-center justify-center">
            <div className="text-center space-y-2">
              <AlertCircle className="w-8 h-8 text-muted-foreground mx-auto" />
              <p className="text-sm text-muted-foreground">No forecast data available</p>
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
    <Card className="border-border">
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
    <div className={isExpertMode ? "space-y-4" : "grid grid-cols-1 lg:grid-cols-3 gap-4"}>
      {/* Market Basket Analysis */}
      <Card className="border-border">
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
          <p className="text-xs text-muted-foreground">
            {isExpertMode ? "Association Rules (Confidence)" : "Buying Patterns"}
          </p>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          {marketBasketRules.length > 0 ? (
            <div className="space-y-2 max-h-80 overflow-y-auto">
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
                          <p className="text-sm font-medium text-foreground leading-snug">{rule.description}</p>
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
          ) : (
            <div className="h-80 flex items-center justify-center">
              <p className="text-xs text-muted-foreground text-center">No patterns detected yet</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Churn Risk */}
      <Card className="border-border">
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
        <CardContent className="px-4 pb-4">
          {churnRiskList.length > 0 ? (
            <div className="space-y-2 max-h-80 overflow-y-auto">
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
          ) : (
            <div className="h-80 flex items-center justify-center">
              <p className="text-xs text-muted-foreground text-center">No churn risks detected</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Stockout Alerts */}
      <Card className="col-span-1 border-border shadow-sm flex flex-col h-[400px]">
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
                          <div className="text-[10px] text-muted-foreground">Stock: {stock} units</div>
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
               <Package className="w-8 h-8 opacity-20 mb-2" />
               <p className="text-xs">Inventory levels optimal.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
  
  // ============================================================================
  // RENDER: MAIN CONTENT WITH TABS (FIXED LAYOUT)
  // ============================================================================
  const MainContentGrid = () => (
    <motion.div variants={cardVariants} className="px-6 pb-6">
      <Tabs value={activeMainTab} onValueChange={setActiveMainTab} className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2 h-9 mb-4">
          <TabsTrigger value="overview" className="text-xs">Overview</TabsTrigger>
          <TabsTrigger value="ai" className="text-xs gap-1.5">
            <Brain className="w-3.5 h-3.5" />
            AI Intelligence
          </TabsTrigger>
        </TabsList>
        
        {/* OVERVIEW TAB: 60/40 Split */}
        <TabsContent value="overview" className="mt-0">
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <div className="lg:col-span-3">
              <RevenueForecastCard />
            </div>
            <div className="lg:col-span-2">
              <DebtStockPanel />
            </div>
          </div>
        </TabsContent>
        
        {/* AI TAB: Full Width */}
        <TabsContent value="ai" className="mt-0">
          <AIAnalyticsContent />
        </TabsContent>
      </Tabs>
    </motion.div>
  );
  
  // ============================================================================
  // MAIN RENDER
  // ============================================================================
  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <TopRail />
      
      <div className="flex-1 overflow-y-auto">
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="space-y-4 py-4"
        >
          <KPIGrid />
          <MainContentGrid />
        </motion.div>
      </div>
    </div>
  );
}