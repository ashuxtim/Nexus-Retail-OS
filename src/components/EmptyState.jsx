import React from 'react';
import { Box, Typography } from '@mui/material';
import InboxIcon from '@mui/icons-material/Inbox';

const EmptyState = ({ title, message }) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        p: 3,
        height: '100%',
        minHeight: 200,
        color: 'text.secondary',
      }}
    >
      <InboxIcon sx={{ fontSize: 60, mb: 2, color: 'neutral.main' }} />
      <Typography variant="h6" component="p" gutterBottom>{title}</Typography>
      <Typography variant="body1">{message}</Typography>
    </Box>
  );
};

export default EmptyState;