import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("React Crash:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 flex justify-center items-center h-full">
          <Card className="border-red-200 bg-red-50 max-w-lg">
             <CardContent className="pt-6 text-center space-y-4">
                <AlertTriangle className="mx-auto h-12 w-12 text-red-500" />
                <h2 className="text-xl font-bold text-red-700">Dashboard Crashed</h2>
                <p className="text-sm text-red-600 bg-white p-2 rounded border border-red-100 font-mono">
                  {this.state.error?.toString()}
                </p>
                <Button 
                  onClick={() => {
                    sessionStorage.clear(); // Clear bad cache
                    window.location.reload(); 
                  }}
                  variant="destructive"
                >
                  Clear Cache & Reload
                </Button>
             </CardContent>
          </Card>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;