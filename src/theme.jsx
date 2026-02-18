import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    primary: {
      main: '#7E57C2', 
    },
    secondary: {
      main: '#6C757D',
    },
    // --- NEW SECTION ---
    // We add a custom color object for things like the sidebar
    neutral: {
      dark: '#1E293B', // A professional dark blue/grey
      main: '#64748B',
      light: '#F1F5F9',
    },
    background: {
      default: '#F4F6F8',
      paper: '#FFFFFF',
    },
    success: {
        main: '#28A745',
    },
    error: {
        main: '#DC3545',
    },
  },
  typography: {
    fontFamily: '"Public Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Helvetica", "Arial", sans-serif',
    h2: {
      fontSize: '1.75rem',
      fontWeight: 700,
      marginBottom: '1rem',
    },
    h3: {
        fontSize: '1.25rem',
        fontWeight: 700,
    }
  },
  components: {
    MuiCard: {
        styleOverrides: {
            root: {
                boxShadow: '0px 0px 15px 0px rgba(0,0,0,0.05)',
                borderRadius: 12,
            }
        }
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 8,
          fontWeight: 600,
        },
      },
    },
    MuiAppBar: {
        styleOverrides: {
            root: {
                backgroundColor: '#FFFFFF',
                color: '#000000',
                boxShadow: 'none',
                borderBottom: '1px solid #E0E0E0',
            }
        }
    },
    MuiDrawer: {
        styleOverrides: {
            paper: {
                borderRight: 'none',
            }
        }
    }
  },
});

export default theme;